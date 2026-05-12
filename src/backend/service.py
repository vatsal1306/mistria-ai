"""Chat orchestration service."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from src.Logging import get_logger
import asyncio
from src.backend.runtime import BaseInferenceRuntime
from src.backend.schemas import ChatMessage, ChatSocketRequest, InferencePromptRequest
from src.config import Chat
from src.memory.background import MemoryExtractionWorker
from src.memory.prompts import render_memory_prompt
from src.memory.service import MemoryService
from src.prompts import build_chat_system_prompt
from src.storage.conversation_store import ConversationSnapshot
from src.storage.models import AICompanionRecord, UserCompanionRecord
from src.storage.service import ChatHistoryService

logger = get_logger(__name__)


class ChatService:
    """Application service for chat."""

    def __init__(
        self,
        chat_config: Chat,
        runtime: BaseInferenceRuntime,
        history_service: ChatHistoryService,
        memory_service: MemoryService | None = None,
        extraction_worker: MemoryExtractionWorker | None = None,
    ):
        self.chat_config = chat_config
        self.runtime = runtime
        self.history_service = history_service
        self.memory_service = memory_service
        self.extraction_worker = extraction_worker

    async def stream_response(
        self, 
        request: ChatSocketRequest, 
        internal_user_id: int, 
        user_name: str | None,
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
            
        if snapshot is None:
            logger.info("No existing conversation found. Starting fresh lazily.")
            snapshot = await asyncio.to_thread(
                self.history_service.start_fresh,
                internal_user_id,
                request.ai_companion_id
            )

        conversation = snapshot.conversation
        
        # 1. Save the incoming user message asynchronously
        user_message_record = await asyncio.to_thread(
            self.history_service.save_message,
            conversation_id=conversation.id,
            role="user",
            content=request.user_message
        )

        # 2. Retrieve memories (if enabled and service provided)
        memory_block = ""
        if self.memory_service:
            try:
                memories = await self.memory_service.retrieve_memories(
                    user_id=internal_user_id,
                    ai_companion_id=request.ai_companion_id,
                    query=request.user_message
                )

                if memories:
                    memory_block = render_memory_prompt(memories)
                    logger.debug(
                        "Retrieved %d memories for conversation_id=%s",
                        len(memories),
                        conversation.id
                    )
                    for mem in memories:
                        if self.memory_service.config.raw_content_logging_enabled:
                            logger.debug(
                                "Memory retrieved: id=%s, score=%.4f, type=%s, content=%r",
                                mem.memory_id, mem.score, mem.memory_type, mem.content
                            )
                        else:
                            logger.debug(
                                "Memory retrieved: id=%s, score=%.4f, type=%s",
                                mem.memory_id, mem.score, mem.memory_type
                            )
            except Exception as e:
                logger.error("Memory retrieval failed (falling back to normal chat): %s", e)

        # 3. Prepare inference history context
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

        # Snapshot of prior history only (before the current user message) for extraction context
        prior_history = list(mapped_messages)

        mapped_messages.append(ChatMessage(role="user", content=request.user_message))

        inference_request = InferencePromptRequest(
            system_prompt=self._build_system_prompt(
                request, user_name, user_companion, ai_companion, memory_block
            ),
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
            # 4. Save the final assistant response asynchronously
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

            # 5. Schedule non-blocking memory extraction
            if self.extraction_worker and user_message_record:
                self.extraction_worker.schedule(
                    user_id=internal_user_id,
                    ai_companion_id=request.ai_companion_id,
                    conversation_id=conversation.id,
                    message_id=user_message_record.id,
                    message_content=request.user_message,
                    recent_messages=prior_history,
                )
        else:
            logger.warning(
                "Completed streamed chat response with empty assistant output conversation_id=%s",
                conversation.id,
            )

    def _build_system_prompt(
            self,
            request: ChatSocketRequest,
            user_name: str | None,
            user_companion: UserCompanionRecord,
            ai_companion: AICompanionRecord,
            memory_block: str = "",
    ) -> str:
        base_prompt = request.system_prompt or self.chat_config.system_prompt
        return build_chat_system_prompt(
            base_prompt=base_prompt,
            user_name=user_name,
            user_companion=user_companion,
            ai_companion=ai_companion,
            memory_block=memory_block,
        )
