"""Chat orchestration service."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from src.Logging import get_logger
from src.backend.runtime import BaseInferenceRuntime
from src.backend.schemas import ChatMessage, ChatSocketRequest, InferencePromptRequest
from src.config import Chat
from src.storage.repositories import SQLiteConversationRepository

logger = get_logger(__name__)


class ChatService:
    """Application service for chat."""

    def __init__(self, chat_config: Chat, runtime: BaseInferenceRuntime, conversation_repo: SQLiteConversationRepository):
        self.chat_config = chat_config
        self.runtime = runtime
        self.conversation_repo = conversation_repo

    async def stream_response(self, request: ChatSocketRequest, internal_user_id: int) -> AsyncGenerator[str, None]:
        """Trim message history, persist logic via DB, and delegate streamed generation to the runtime."""
        logger.info(
            "Starting streamed chat response internal_user_id=%s ai_companion_id=%s",
            internal_user_id,
            request.ai_companion_id,
        )
        conversation = self.conversation_repo.get_latest_conversation(internal_user_id, request.ai_companion_id)
        created_new_conversation = conversation is None
        if conversation is None:
            conversation = self.conversation_repo.create_conversation(internal_user_id, request.ai_companion_id)
        logger.debug(
            "Resolved conversation conversation_id=%s created_new=%s internal_user_id=%s ai_companion_id=%s",
            conversation.id,
            created_new_conversation,
            internal_user_id,
            request.ai_companion_id,
        )

        self.conversation_repo.create_message(conversation.id, "user", request.user_message)

        history_records = self.conversation_repo.list_messages(conversation.id)
        trimmed_records = history_records[-self.chat_config.history_message_limit:]
        logger.debug(
            "Prepared inference history conversation_id=%s total_messages=%s trimmed_messages=%s limit=%s",
            conversation.id,
            len(history_records),
            len(trimmed_records),
            self.chat_config.history_message_limit,
        )

        mapped_messages = []
        for record in trimmed_records:
            mapped_messages.append(ChatMessage(role=record.role, content=record.content))  # type: ignore[arg-type]

        inference_request = InferencePromptRequest(
            system_prompt=request.system_prompt,
            messages=mapped_messages,
        )

        assistant_content = ""
        chunk_count = 0
        try:
            async for token in self.runtime.stream_text(inference_request):
                assistant_content += token
                chunk_count += 1
                yield token
        except Exception:
            logger.exception(
                "Streamed chat response failed conversation_id=%s internal_user_id=%s ai_companion_id=%s",
                conversation.id,
                internal_user_id,
                request.ai_companion_id,
            )
            raise

        if assistant_content:
            self.conversation_repo.create_message(conversation.id, "assistant", assistant_content)
            logger.info(
                "Completed streamed chat response conversation_id=%s chunks=%s assistant_chars=%s",
                conversation.id,
                chunk_count,
                len(assistant_content),
            )
        else:
            logger.warning(
                "Completed streamed chat response with empty assistant output conversation_id=%s",
                conversation.id,
            )
