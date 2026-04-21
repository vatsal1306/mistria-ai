"""Chat orchestration service."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from src.backend.runtime import BaseInferenceRuntime
from src.backend.schemas import ChatMessage, ChatSocketRequest, InferencePromptRequest
from src.config import Chat
from src.storage.repositories import SQLiteConversationRepository


class ChatService:
    """Application service for chat."""

    def __init__(self, chat_config: Chat, runtime: BaseInferenceRuntime, conversation_repo: SQLiteConversationRepository):
        self.chat_config = chat_config
        self.runtime = runtime
        self.conversation_repo = conversation_repo

    async def stream_response(self, request: ChatSocketRequest, internal_user_id: int) -> AsyncGenerator[str, None]:
        """Trim message history, persist logic via DB, and delegate streamed generation to the runtime."""
        conversation = self.conversation_repo.get_latest_conversation(internal_user_id, request.ai_companion_id)
        if not conversation:
            conversation = self.conversation_repo.create_conversation(internal_user_id, request.ai_companion_id)

        self.conversation_repo.create_message(conversation.id, "user", request.user_message)

        history_records = self.conversation_repo.list_messages(conversation.id)
        trimmed_records = history_records[-self.chat_config.history_message_limit:]
        
        mapped_messages = []
        for record in trimmed_records:
            mapped_messages.append(ChatMessage(role=record.role, content=record.content)) # type: ignore

        inference_request = InferencePromptRequest(
            system_prompt=request.system_prompt,
            messages=mapped_messages,
        )

        assistant_content = ""
        async for token in self.runtime.stream_text(inference_request):
            assistant_content += token
            yield token

        if assistant_content:
            self.conversation_repo.create_message(conversation.id, "assistant", assistant_content)
