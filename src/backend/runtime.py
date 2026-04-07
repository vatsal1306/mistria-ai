"""Inference runtime implementations and runtime factory."""

from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from uuid import uuid4

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


class MockInferenceRuntime(BaseInferenceRuntime):
    """Runnable local backend for UI and transport smoke tests."""

    @property
    def is_ready(self) -> bool:
        return True

    async def startup(self) -> None:
        logger.info("Mock inference runtime initialized")

    async def shutdown(self) -> None:
        logger.info("Mock inference runtime stopped")

    async def stream_text(self, request: ChatSocketRequest) -> AsyncGenerator[str, None]:
        latest_user_message = request.messages[-1].content
        scripted_reply = (
            f"Mock backend active. I received: {latest_user_message!r}. "
            "Switch settings.inference.backend to 'vllm' when the target runtime is installed and available."
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

    @property
    def is_ready(self) -> bool:
        return self._engine is not None and self._tokenizer is not None and self._startup_error is None

    async def startup(self) -> None:
        if self.secrets_config.hf_token:
            os.environ["HF_TOKEN"] = self.secrets_config.hf_token

        try:
            from transformers import AutoTokenizer
            from vllm import SamplingParams
            from vllm.engine.arg_utils import AsyncEngineArgs
            from vllm.sampling_params import RequestOutputKind
            from vllm.v1.engine.async_llm import AsyncLLM
        except ImportError:
            self._startup_error = (
                "vLLM runtime is not installed. Install the optional inference dependency on a supported host."
            )
            logger.exception("vLLM imports failed during startup")
            return

        try:
            tokenizer_name = self.inference_config.tokenizer_name or self.inference_config.model_name
            self._tokenizer = AutoTokenizer.from_pretrained(
                tokenizer_name,
                trust_remote_code=self.inference_config.trust_remote_code,
                token=self.secrets_config.hf_token or None,
            )

            engine_args = AsyncEngineArgs(
                model=self.inference_config.model_name,
                tokenizer=tokenizer_name,
                tensor_parallel_size=self.inference_config.tensor_parallel_size,
                dtype=self.inference_config.dtype,
                max_model_len=self.inference_config.max_model_len,
                trust_remote_code=self.inference_config.trust_remote_code,
                enforce_eager=self.inference_config.enforce_eager,
            )
            self._engine = AsyncLLM.from_engine_args(engine_args)
            self._sampling_params_cls = SamplingParams
            self._request_output_kind = RequestOutputKind
            self._startup_error = None
            logger.info("Embedded vLLM runtime initialized for model=%s", self.inference_config.model_name)
        except Exception as exc:
            self._startup_error = f"{type(exc).__name__}: {exc}"
            logger.exception("Embedded vLLM runtime failed to initialize")

    async def shutdown(self) -> None:
        if self._engine is not None:
            self._engine.shutdown()
            self._engine = None
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


class InferenceRuntimeFactory:
    """Construct runtime implementations from static configuration."""

    @staticmethod
    def create(chat_config: Chat, inference_config: Inference, secrets_config: Secrets) -> BaseInferenceRuntime:
        if inference_config.backend == "mock":
            return MockInferenceRuntime(chat_config, inference_config, secrets_config)
        if inference_config.backend == "vllm":
            return VLLMInferenceRuntime(chat_config, inference_config, secrets_config)
        raise ConfigurationError(f"Unsupported inference backend: {inference_config.backend}")
