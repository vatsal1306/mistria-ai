"""Chat history service helpers for the Streamlit flow."""

from __future__ import annotations

from src.storage.conversation_store import ConversationSnapshot, ConversationStore
from src.storage.models import MessageRecord


class ChatHistoryService:
    """Coordinate latest-conversation loading and message persistence."""

    def __init__(self, conversation_store: ConversationStore):
        self.conversation_store = conversation_store

    def load_latest(self, user_id: int) -> ConversationSnapshot:
        return self.conversation_store.get_or_create_latest_conversation(user_id)

    def start_fresh(self, user_id: int) -> ConversationSnapshot:
        return self.conversation_store.create_fresh_conversation(user_id)

    def save_message(self, conversation_id: int, role: str, content: str) -> MessageRecord:
        return self.conversation_store.append_message(conversation_id=conversation_id, role=role, content=content)
