"""Inference runtime implementations and runtime factory."""

from __future__ import annotations

import asyncio
import os
import time
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





class InferenceRuntimeFactory:
    """Construct runtime implementations from static configuration."""

    @staticmethod
    def create(chat_config: Chat, inference_config: Inference, secrets_config: Secrets) -> BaseInferenceRuntime:

        if inference_config.backend == "ollama":
            from src.backend.ollama_runtime import OllamaInferenceRuntime
            return OllamaInferenceRuntime(chat_config, inference_config, secrets_config)
        raise ConfigurationError(f"Unsupported inference backend: {inference_config.backend}")
