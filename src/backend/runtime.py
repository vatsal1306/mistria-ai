"""Inference runtime implementations and runtime factory."""

from __future__ import annotations

import asyncio
import os
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from uuid import uuid4

import ollama

from src.Logging import logger
from src.backend.exceptions import ConfigurationError, InferenceExecutionError, InferenceNotReadyError
from src.backend.schemas import ChatSocketRequest
from src.config import Chat, Inference, Secrets


class BaseInferenceRuntime(ABC):
    """Abstract interface for streamed text generation backends."""

    def __init__(self, chat_config: Chat, inference_config: Inference, secrets_config: Secrets):
        self.chat_config = chat_config
        self.inference_config = inference_config
        self.secrets_config = secrets_config
        self._startup_error: str | None = None
        self._startup_stage = "not_started"
        self._startup_detail: str | None = None
        self._startup_started_at: float | None = None

    @property
    def backend_name(self) -> str:
        return self.inference_config.backend

    @property
    def model_name(self) -> str:
        return self.inference_config.model_name

    @property
    def startup_error(self) -> str | None:
        return self._startup_error

    @property
    def startup_stage(self) -> str:
        return self._startup_stage

    @property
    def startup_detail(self) -> str | None:
        return self._startup_detail

    @property
    def startup_elapsed_seconds(self) -> float | None:
        if self._startup_started_at is None:
            return None
        return round(time.monotonic() - self._startup_started_at, 1)

    @property
    @abstractmethod
    def is_ready(self) -> bool:
        """Whether the runtime is ready to accept generation requests."""

    @abstractmethod
    async def startup(self) -> None:
        """Initialize resources needed for inference."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Release inference resources."""

    @abstractmethod
    async def stream_text(self, request: ChatSocketRequest) -> AsyncGenerator[str, None]:
        """Stream response chunks for a request."""

    def _set_startup_stage(self, stage: str, detail: str | None = None) -> None:
        previous_stage = self._startup_stage
        if self._startup_started_at is None and stage != "not_started":
            self._startup_started_at = time.monotonic()
        self._startup_stage = stage
        self._startup_detail = detail
        if stage != previous_stage:
            logger.info(
                "Runtime startup stage=%s elapsed=%.1fs detail=%s",
                stage,
                self.startup_elapsed_seconds or 0.0,
                detail or "n/a",
            )


class MockInferenceRuntime(BaseInferenceRuntime):
    """Runnable local backend for UI and transport smoke tests."""

    @property
    def is_ready(self) -> bool:
        return True

    async def startup(self) -> None:
        self._set_startup_stage("ready", "Mock backend is ready.")
        logger.info("Mock inference runtime initialized")

    async def shutdown(self) -> None:
        self._set_startup_stage("stopped", "Mock backend has been stopped.")
        logger.info("Mock inference runtime stopped")

    async def stream_text(self, request: ChatSocketRequest) -> AsyncGenerator[str, None]:
        latest_user_message = request.messages[-1].content
        scripted_reply = (
            f"Mock backend active. I received: {latest_user_message!r}. "
            "Switch settings.inference.backend to 'ollama' when the target runtime is installed and available."
        )
        for token in scripted_reply.split():
            await asyncio.sleep(self.inference_config.mock_response_delay_seconds)
            yield f"{token} "


class VLLMInferenceRuntime(BaseInferenceRuntime):
    """Embedded vLLM runtime managed inside the FastAPI process."""

    def __init__(self, chat_config: Chat, inference_config: Inference, secrets_config: Secrets):
        super().__init__(chat_config, inference_config, secrets_config)
        self._engine = None
        self._tokenizer = None
        self._sampling_params_cls = None
        self._request_output_kind = None
        self._startup_monitor_task: asyncio.Task | None = None

    @property
    def is_ready(self) -> bool:
        return self._engine is not None and self._tokenizer is not None and self._startup_error is None

    async def startup(self) -> None:
        self._set_startup_stage("initializing", "Preparing embedded vLLM runtime.")
        self._startup_monitor_task = asyncio.create_task(self._startup_monitor())

        if self.secrets_config.hf_token:
            os.environ["HF_TOKEN"] = self.secrets_config.hf_token
        os.environ["VLLM_ENGINE_ITERATION_TIMEOUT_S"] = str(self.inference_config.engine_iteration_timeout_seconds)

        try:
            self._set_startup_stage("importing_runtime", "Importing transformers and vLLM modules.")
            from transformers import AutoTokenizer
            from vllm import SamplingParams
            from vllm.engine.async_llm_engine import AsyncLLMEngine
            from vllm.engine.arg_utils import AsyncEngineArgs
            from vllm.platforms import current_platform
            from vllm.sampling_params import RequestOutputKind
        except Exception as exc:
            self._startup_error = (
                "vLLM runtime import failed. "
                f"{type(exc).__name__}: {exc}"
            )
            self._set_startup_stage("failed", self._startup_error)
            logger.exception("vLLM imports failed during startup")
            await self._stop_startup_monitor()
            return

        try:
            use_v1 = current_platform.device_type != "cpu"
            os.environ["VLLM_USE_V1"] = "1" if use_v1 else "0"
            tokenizer_name = self.inference_config.tokenizer_name or self.inference_config.model_name
            self._set_startup_stage(
                "loading_tokenizer",
                f"Loading tokenizer for {tokenizer_name}.",
            )
            self._tokenizer = AutoTokenizer.from_pretrained(
                tokenizer_name,
                revision=self.inference_config.tokenizer_revision or self.inference_config.model_revision,
                trust_remote_code=self.inference_config.trust_remote_code,
                token=self.secrets_config.hf_token or None,
            )

            self._set_startup_stage(
                "building_engine",
                f"Building vLLM engine on device={current_platform.device_type} (v1={use_v1}).",
            )
            logger.info(
                "Using vLLM engine iteration timeout=%ss",
                self.inference_config.engine_iteration_timeout_seconds,
            )
            engine_args = AsyncEngineArgs(
                model=self.inference_config.model_name,
                revision=self.inference_config.model_revision,
                tokenizer=tokenizer_name,
                tokenizer_revision=self.inference_config.tokenizer_revision or self.inference_config.model_revision,
                tensor_parallel_size=self.inference_config.tensor_parallel_size,
                dtype=self.inference_config.dtype,
                max_model_len=self.inference_config.max_model_len,
                trust_remote_code=self.inference_config.trust_remote_code,
                enforce_eager=self.inference_config.enforce_eager,
            )
            self._set_startup_stage(
                "loading_model",
                "Downloading and loading model weights. This can take several minutes on first CPU startup.",
            )
            self._engine = AsyncLLMEngine.from_engine_args(engine_args)
            self._sampling_params_cls = SamplingParams
            self._request_output_kind = RequestOutputKind
            self._startup_error = None
            self._set_startup_stage("ready", "Embedded vLLM runtime is ready.")
            logger.info(
                "Embedded vLLM runtime initialized for model=%s device=%s v1=%s",
                self.inference_config.model_name,
                current_platform.device_type,
                use_v1,
            )
        except Exception as exc:
            self._startup_error = f"{type(exc).__name__}: {exc}"
            self._set_startup_stage("failed", self._startup_error)
            logger.exception("Embedded vLLM runtime failed to initialize")
        finally:
            await self._stop_startup_monitor()

    async def shutdown(self) -> None:
        await self._stop_startup_monitor()
        if self._engine is not None:
            if hasattr(self._engine, "shutdown"):
                self._engine.shutdown()
            elif hasattr(self._engine, "shutdown_background_loop"):
                self._engine.shutdown_background_loop()
            self._engine = None
            self._set_startup_stage("stopped", "Embedded vLLM runtime has been stopped.")
            logger.info("Embedded vLLM runtime stopped")

    async def stream_text(self, request: ChatSocketRequest) -> AsyncGenerator[str, None]:
        if not self.is_ready:
            raise InferenceNotReadyError(self._startup_error or "Inference runtime is not ready.")

        prompt = self._build_prompt(request)
        request_id = request.request_id or uuid4().hex
        sampling_params = self._sampling_params_cls(
            max_tokens=self.inference_config.max_tokens,
            temperature=self.inference_config.temperature,
            top_p=self.inference_config.top_p,
            output_kind=self._request_output_kind.DELTA,
        )

        try:
            async for output in self._engine.generate(
                    request_id=request_id,
                    prompt=prompt,
                    sampling_params=sampling_params,
            ):
                for completion in output.outputs:
                    if completion.text:
                        yield completion.text
                if output.finished:
                    break
        except asyncio.TimeoutError as exc:
            logger.exception("vLLM generation timed out for request_id=%s", request_id)
            raise InferenceExecutionError(
                "Generation exceeded the configured vLLM engine timeout. "
                "On CPU with this model, increase engine_iteration_timeout_seconds or use a smaller model."
            ) from exc
        except Exception as exc:
            logger.exception("vLLM generation failed for request_id=%s", request_id)
            raise InferenceExecutionError(f"{type(exc).__name__}: {exc}") from exc

    def _build_prompt(self, request: ChatSocketRequest) -> str:
        prompt_messages = [
            {
                "role": "system",
                "content": self._resolve_system_prompt(request.system_prompt),
            },
            *[message.model_dump() for message in request.messages],
        ]
        try:
            return self._tokenizer.apply_chat_template(
                prompt_messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        except Exception as exc:
            logger.exception("Tokenizer chat template application failed")
            raise InferenceExecutionError(f"Tokenizer chat templating failed: {exc}") from exc

    def _resolve_system_prompt(self, override_prompt: str | None) -> str:
        prompt = override_prompt or self.chat_config.system_prompt
        return f"{prompt}\n\n{self.chat_config.pulse_context}"

    async def _startup_monitor(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.inference_config.startup_heartbeat_interval_seconds)
                if self.is_ready or self._startup_stage in {"failed", "stopped"}:
                    return
                logger.info(
                    "Runtime startup in progress stage=%s elapsed=%.1fs detail=%s",
                    self._startup_stage,
                    self.startup_elapsed_seconds or 0.0,
                    self._startup_detail or "n/a",
                )
        except asyncio.CancelledError:
            return

    async def _stop_startup_monitor(self) -> None:
        if self._startup_monitor_task is not None:
            self._startup_monitor_task.cancel()
            try:
                await self._startup_monitor_task
            except asyncio.CancelledError:
                pass
            self._startup_monitor_task = None

class OllamaInferenceRuntime(BaseInferenceRuntime):
    """Runtime using the native Ollama HTTP client."""

    def __init__(self, chat_config: Chat, inference_config: Inference, secrets_config: Secrets):
        super().__init__(chat_config, inference_config, secrets_config)
        self._client = None
        self._startup_monitor_task: asyncio.Task | None = None

    @property
    def is_ready(self) -> bool:
        return self._client is not None and self._startup_error is None

    async def startup(self) -> None:
        self._set_startup_stage("initializing", "Preparing Ollama runtime.")
        self._startup_monitor_task = asyncio.create_task(self._startup_monitor())

        try:
            self._set_startup_stage("connecting_client", "Connecting to local Ollama server.")
            self._client = ollama.AsyncClient()

            # Verify the server is responding
            await self._client.list()

            self._set_startup_stage("verifying_model", f"Checking if {self.inference_config.model_name} is pulled locally.")
            models_response = await self._client.list()
            models = [m.model for m in models_response.models] if hasattr(models_response, "models") else []
            if not models and isinstance(models_response, dict):
                 models = [m.get("model", "") for m in models_response.get("models", [])]

            if self.inference_config.model_name not in models and f"{self.inference_config.model_name}:latest" not in models:
                 self._set_startup_stage("pulling_model", f"Pulling {self.inference_config.model_name} from registry. This may take a minute.")
                 await self._client.pull(self.inference_config.model_name)

            self._startup_error = None
            self._set_startup_stage("ready", "Ollama runtime is ready.")
            logger.info("Ollama runtime initialized for model=%s", self.inference_config.model_name)
        except ollama.ResponseError as exc:
            self._startup_error = f"Ollama rejected the configuration: {exc}"
            self._set_startup_stage("failed", self._startup_error)
            logger.exception("Ollama runtime failed during startup")
        except Exception as exc:
            self._startup_error = f"Ollama local connection failed. Is the app running? Error: {exc}"
            self._set_startup_stage("failed", self._startup_error)
            logger.exception("Ollama runtime failed during startup")
        finally:
            await self._stop_startup_monitor()

    async def shutdown(self) -> None:
        await self._stop_startup_monitor()
        self._client = None
        self._set_startup_stage("stopped", "Ollama runtime has been stopped.")
        logger.info("Ollama runtime stopped")

    async def stream_text(self, request: ChatSocketRequest) -> AsyncGenerator[str, None]:
        if not self.is_ready:
            raise InferenceNotReadyError(self._startup_error or "Inference runtime is not ready.")

        messages = [
            {"role": "system", "content": self._resolve_system_prompt(request.system_prompt)},
            *[{"role": m.role, "content": m.content} for m in request.messages],
        ]

        try:
            async for chunk in await self._client.chat(
                model=self.inference_config.model_name,
                messages=messages,
                stream=True,
                options={
                    "temperature": self.inference_config.temperature,
                    "top_p": self.inference_config.top_p,
                    "num_predict": self.inference_config.max_tokens,
                }
            ):
                if chunk and "message" in chunk and "content" in chunk["message"]:
                    content = chunk["message"]["content"]
                    if content:
                        yield content

        except Exception as exc:
            logger.exception("Ollama generation failed")
            raise InferenceExecutionError(f"{type(exc).__name__}: {exc}") from exc

    def _resolve_system_prompt(self, override_prompt: str | None) -> str:
        prompt = override_prompt or self.chat_config.system_prompt
        return f"{prompt}\n\n{self.chat_config.pulse_context}"

    async def _startup_monitor(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.inference_config.startup_heartbeat_interval_seconds)
                if self.is_ready or self._startup_stage in {"failed", "stopped"}:
                    return
                logger.info(
                    "Runtime startup in progress stage=%s elapsed=%.1fs detail=%s",
                    self._startup_stage,
                    self.startup_elapsed_seconds or 0.0,
                    self._startup_detail or "n/a",
                )
        except asyncio.CancelledError:
            return

    async def _stop_startup_monitor(self) -> None:
        if self._startup_monitor_task is not None:
            self._startup_monitor_task.cancel()
            try:
                await self._startup_monitor_task
            except asyncio.CancelledError:
                pass
            self._startup_monitor_task = None


class InferenceRuntimeFactory:
    """Construct runtime implementations from static configuration."""

    @staticmethod
    def create(chat_config: Chat, inference_config: Inference, secrets_config: Secrets) -> BaseInferenceRuntime:
        if inference_config.backend == "mock":
            return MockInferenceRuntime(chat_config, inference_config, secrets_config)
        if inference_config.backend == "vllm":
            return VLLMInferenceRuntime(chat_config, inference_config, secrets_config)
        if inference_config.backend == "ollama":
            return OllamaInferenceRuntime(chat_config, inference_config, secrets_config)
        raise ConfigurationError(f"Unsupported inference backend: {inference_config.backend}")
