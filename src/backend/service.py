"""Chat orchestration service."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from src.Logging import get_logger
import asyncio
from src.backend.runtime import BaseInferenceRuntime
from src.backend.schemas import ChatMessage, ChatSocketRequest, InferencePromptRequest
from src.config import Chat
from src.prompts import build_chat_system_prompt
from src.storage.conversation_store import ConversationSnapshot
from src.storage.models import AICompanionRecord, UserCompanionRecord
from src.storage.service import ChatHistoryService

logger = get_logger(__name__)


class ChatService:
    """Application service for chat."""

    def __init__(self, chat_config: Chat, runtime: BaseInferenceRuntime, history_service: ChatHistoryService):
        self.chat_config = chat_config
        self.runtime = runtime
        self.history_service = history_service

    async def stream_response(
        self, 
        request: ChatSocketRequest, 
        internal_user_id: int, 
        user_companion: UserCompanionRecord,
        ai_companion: AICompanionRecord,
        snapshot: ConversationSnapshot | None = None
    ) -> AsyncGenerator[str, None]:
        """Trim message history, persist logic via DB, and delegate streamed generation to the runtime."""
        logger.info(
            "Starting streamed chat response internal_user_id=%s ai_companion_id=%s",
            internal_user_id,
            request.ai_companion_id,
        )
        
        # Load snapshot if not provided (fallback)
        # Issue A: Ensure pre-fetched snapshot identity matches the actual request
        if snapshot:
            is_match = (
                snapshot.conversation.user_id == internal_user_id and
                snapshot.conversation.ai_companion_id == request.ai_companion_id
            )
            if not is_match:
                logger.warning(
                    "Snapshot identity mismatch. Discarding pre-fetch. "
                    "snapshot_user=%s req_user=%s snapshot_companion=%s req_companion=%s",
                    snapshot.conversation.user_id,
                    internal_user_id,
                    snapshot.conversation.ai_companion_id,
                    request.ai_companion_id
                )
                snapshot = None

        if snapshot is None:
            snapshot = await asyncio.to_thread(
                self.history_service.load_latest, 
                internal_user_id, 
                request.ai_companion_id
            )
            
        # Issue C: If no history exists, start a fresh conversation lazily
        if snapshot is None:
            logger.info("No existing conversation found. Starting fresh lazily.")
            snapshot = await asyncio.to_thread(
                self.history_service.start_fresh,
                internal_user_id,
                request.ai_companion_id
            )

        conversation = snapshot.conversation
        
        # 1. Save the incoming user message asynchronously
        await asyncio.to_thread(
            self.history_service.save_message,
            conversation_id=conversation.id,
            role="user",
            content=request.user_message
        )

        # 2. Prepare inference history context
        # Include past messages from snapshot and the current message
        history_records = list(snapshot.messages)
        trimmed_records = history_records[-self.chat_config.history_message_limit:]
        
        logger.debug(
            "Prepared inference history conversation_id=%s total_past_messages=%s trimmed_messages=%s limit=%s",
            conversation.id,
            len(history_records),
            len(trimmed_records),
            self.chat_config.history_message_limit,
        )

        mapped_messages = []
        for record in trimmed_records:
            mapped_messages.append(ChatMessage(role=record.role, content=record.content))  # type: ignore[arg-type]
            
        # Add the current user message to the context
        mapped_messages.append(ChatMessage(role="user", content=request.user_message))

        inference_request = InferencePromptRequest(
            system_prompt=self._build_system_prompt(request, user_companion, ai_companion),
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
            # 3. Save the final assistant response asynchronously
            await asyncio.to_thread(
                self.history_service.save_message,
                conversation_id=conversation.id,
                role="assistant",
                content=assistant_content
            )
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

    def _build_system_prompt(
            self,
            request: ChatSocketRequest,
            user_companion: UserCompanionRecord,
            ai_companion: AICompanionRecord,
    ) -> str:
        base_prompt = request.system_prompt or self.chat_config.system_prompt
        return build_chat_system_prompt(
            base_prompt=base_prompt,
            user_companion=user_companion,
            ai_companion=ai_companion,
        )
