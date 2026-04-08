"""Inference runtime implementations and runtime factory."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from src.Logging import logger
from src.backend.exceptions import (
    ConfigurationError,
    InferenceExecutionError,
    InferenceNotReadyError,
)
from src.backend.schemas import ChatSocketRequest
from src.config import Chat, Inference, Secrets


class BaseInferenceRuntime(ABC):
    """Abstract interface for streamed text generation backends."""

    def __init__(
        self,
        chat_config: Chat,
        inference_config: Inference,
        secrets_config: Secrets,
    ):
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
    async def stream_text(
        self, request: ChatSocketRequest,
    ) -> AsyncGenerator[str, None]:
        """Stream response chunks for a request."""

    def _set_startup_stage(self, stage: str, detail: str | None = None) -> None:
        if self._startup_started_at is None and stage != "not_started":
            self._startup_started_at = time.monotonic()
        self._startup_stage = stage
        self._startup_detail = detail
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

    async def stream_text(
        self, request: ChatSocketRequest,
    ) -> AsyncGenerator[str, None]:
        latest_user_message = request.messages[-1].content
        scripted_reply = (
            f"Mock backend active. I received: {latest_user_message!r}. "
            "Switch settings.inference.backend to 'ollama' for live responses."
        )
        for token in scripted_reply.split():
            await asyncio.sleep(0.03)
            yield f"{token} "


class OllamaInferenceRuntime(BaseInferenceRuntime):
    """Ollama-backed inference runtime for local LLM serving."""

    def __init__(
        self,
        chat_config: Chat,
        inference_config: Inference,
        secrets_config: Secrets,
    ):
        super().__init__(chat_config, inference_config, secrets_config)
        self._client: object | None = None
        self._ready = False

    @property
    def is_ready(self) -> bool:
        return self._ready

    async def startup(self) -> None:
        self._set_startup_stage("initializing", "Connecting to Ollama server.")
        try:
            import ollama as ollama_lib

            self._client = ollama_lib.AsyncClient(
                host=self.inference_config.ollama_host,
            )

            self._set_startup_stage(
                "checking_model",
                f"Verifying model {self.inference_config.model_name}.",
            )
            models_response = await self._client.list()
            available = [m.model for m in models_response.models]

            model_found = any(
                self.inference_config.model_name in name for name in available
            )
            if not model_found:
                logger.warning(
                    "Model %s not found in Ollama. Available: %s. Attempting to pull...",
                    self.inference_config.model_name,
                    available,
                )
                self._set_startup_stage(
                    "pulling_model",
                    f"Pulling {self.inference_config.model_name}.",
                )
                await self._client.pull(self.inference_config.model_name)

            self._ready = True
            self._set_startup_stage("ready", "Ollama runtime is ready.")
            logger.info(
                "Ollama runtime initialized for model=%s host=%s",
                self.inference_config.model_name,
                self.inference_config.ollama_host,
            )
        except Exception as exc:
            self._startup_error = f"{type(exc).__name__}: {exc}"
            self._set_startup_stage("failed", self._startup_error)
            logger.exception("Ollama runtime failed to initialize")

    async def shutdown(self) -> None:
        self._ready = False
        self._client = None
        self._set_startup_stage("stopped", "Ollama runtime has been stopped.")
        logger.info("Ollama runtime stopped")

    async def stream_text(
        self, request: ChatSocketRequest,
    ) -> AsyncGenerator[str, None]:
        if not self.is_ready or self._client is None:
            raise InferenceNotReadyError(
                self._startup_error or "Ollama runtime is not ready.",
            )

        messages = self._build_messages(request)
        try:
            stream = await self._client.chat(
                model=self.inference_config.model_name,
                messages=messages,
                options={
                    "temperature": self.inference_config.temperature,
                    "top_p": self.inference_config.top_p,
                    "num_predict": self.inference_config.max_tokens,
                },
                stream=True,
            )
            async for chunk in stream:
                token = chunk["message"]["content"]
                if token:
                    yield token
        except Exception as exc:
            logger.exception("Ollama generation failed")
            raise InferenceExecutionError(
                f"{type(exc).__name__}: {exc}",
            ) from exc

    def _build_messages(
        self, request: ChatSocketRequest,
    ) -> list[dict[str, str]]:
        system_prompt = request.system_prompt or self.chat_config.system_prompt
        return [
            {"role": "system", "content": system_prompt},
            *[msg.model_dump() for msg in request.messages],
        ]


class InferenceRuntimeFactory:
    """Construct runtime implementations from static configuration."""

    @staticmethod
    def create(
        chat_config: Chat,
        inference_config: Inference,
        secrets_config: Secrets,
    ) -> BaseInferenceRuntime:
        if inference_config.backend == "mock":
            return MockInferenceRuntime(chat_config, inference_config, secrets_config)
        if inference_config.backend == "ollama":
            return OllamaInferenceRuntime(chat_config, inference_config, secrets_config)
        raise ConfigurationError(
            f"Unsupported inference backend: {inference_config.backend}",
        )
