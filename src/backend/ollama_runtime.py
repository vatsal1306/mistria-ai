"""Ollama implementation of the inference runtime."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import ollama

from src.Logging import logger
from src.backend.exceptions import InferenceExecutionError, InferenceNotReadyError
from src.backend.runtime import BaseInferenceRuntime
from src.backend.schemas import ChatSocketRequest
from src.config import Chat, Inference, Secrets


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
