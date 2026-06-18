"""Chat history service helpers for the Streamlit flow."""

from __future__ import annotations

from src.storage.conversation_store import ConversationSnapshot, ConversationStore
from src.storage.models import MessageRecord


class ChatHistoryService:
    """Coordinate latest-conversation loading and message persistence."""

    def __init__(self, conversation_store: ConversationStore):
        self.conversation_store = conversation_store

    def load_latest(self, user_id: int, ai_companion_id: int) -> ConversationSnapshot | None:
        """Load the latest conversation for a user/persona pair, without creating it."""
        return self.conversation_store.get_latest_snapshot(user_id, ai_companion_id)

    def start_fresh(self, user_id: int, ai_companion_id: int) -> ConversationSnapshot:
        """Start a fresh conversation for a user/persona pair."""
        return self.conversation_store.create_fresh_conversation(user_id, ai_companion_id)

    def save_message(self, conversation_id: int, role: str, content: str) -> MessageRecord:
        """Persist a single message in the active conversation."""
        return self.conversation_store.append_message(conversation_id=conversation_id, role=role, content=content)

    def list_recent_messages(self, conversation_id: int, limit: int) -> list[MessageRecord]:
        """Return the most recent messages for a conversation in chronological order."""
        if limit <= 0:
            return []

        messages = self.conversation_store.list_messages(conversation_id)
        return messages[-limit:]
