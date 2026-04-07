"""Chat orchestration service."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from src.backend.runtime import BaseInferenceRuntime
from src.backend.schemas import ChatSocketRequest
from src.config import Chat


class ChatService:
    """Application service for normalized chat requests."""

    def __init__(self, chat_config: Chat, runtime: BaseInferenceRuntime):
        self.chat_config = chat_config
        self.runtime = runtime

    async def stream_response(self, request: ChatSocketRequest) -> AsyncGenerator[str, None]:
        trimmed_messages = request.messages[-self.chat_config.history_message_limit :]
        normalized_request = request.model_copy(update={"messages": trimmed_messages})
        async for chunk in self.runtime.stream_text(normalized_request):
            yield chunk
