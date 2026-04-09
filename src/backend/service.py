"""Chat orchestration service."""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from src.Logging import logger
from src.backend.runtime import BaseInferenceRuntime
from src.backend.schemas import ChatSocketRequest
from src.config import Chat


@dataclass(frozen=True)
class StreamMetadata:
    """Metadata yielded as the final item of a streamed response."""

    latency_seconds: float


class ChatService:
    """Application service for chat."""

    def __init__(
        self,
        chat_config: Chat,
        runtime: BaseInferenceRuntime,
    ):
        self.chat_config = chat_config
        self.runtime = runtime

    async def stream_response(
        self,
        request: ChatSocketRequest,
    ) -> AsyncGenerator[str | StreamMetadata, None]:
        """Stream response tokens, yielding StreamMetadata as the final item."""
        trimmed = request.messages[-self.chat_config.history_message_limit:]
        normalized = request.model_copy(update={"messages": trimmed})

        start_time = time.time()

        async for token in self.runtime.stream_text(normalized):
            yield token

        latency = round(time.time() - start_time, 2)

        logger.debug("[Latency: %ss]", latency)

        yield StreamMetadata(latency_seconds=latency)


