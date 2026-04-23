"""Conversation history abstraction with a SQLite implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.storage.models import ConversationRecord, MessageRecord
from src.storage.repositories import SQLiteConversationRepository


@dataclass(frozen=True, slots=True)
class ConversationSnapshot:
    """Bundle a conversation record together with its persisted messages."""
    conversation: ConversationRecord
    messages: list[MessageRecord]


class ConversationStore(ABC):
    """Abstract persistence interface for chat history."""

    @abstractmethod
    def get_or_create_latest_conversation(self, user_id: int, ai_companion_id: int) -> ConversationSnapshot:
        """Return the latest conversation for a user/persona pair, creating one if none exists."""

    @abstractmethod
    def get_latest_snapshot(self, user_id: int, ai_companion_id: int) -> ConversationSnapshot | None:
        """Return the latest conversation snapshot, or None if no conversation exists yet."""

    @abstractmethod
    def create_fresh_conversation(self, user_id: int, ai_companion_id: int) -> ConversationSnapshot:
        """Create a new empty conversation for the given user/persona pair."""

    @abstractmethod
    def append_message(self, conversation_id: int, role: str, content: str) -> MessageRecord:
        """Persist a message in the current conversation."""


class SQLiteConversationStore(ConversationStore):
    """SQLite implementation of the conversation history store."""

    def __init__(self, repository: SQLiteConversationRepository):
        self.repository = repository

    def get_or_create_latest_conversation(self, user_id: int, ai_companion_id: int) -> ConversationSnapshot:
        """Return the latest conversation for a user/persona pair, creating it if needed."""
        snapshot = self.get_latest_snapshot(user_id, ai_companion_id)
        if snapshot is not None:
            return snapshot
            
        return self.create_fresh_conversation(user_id, ai_companion_id)

    def get_latest_snapshot(self, user_id: int, ai_companion_id: int) -> ConversationSnapshot | None:
        """Return the latest conversation for a user/persona pair, without creating it."""
        conversation = self.repository.get_latest_conversation(user_id, ai_companion_id)
        if conversation is None:
            return None

        return ConversationSnapshot(
            conversation=conversation,
            messages=self.repository.list_messages(conversation.id),
        )

    def create_fresh_conversation(self, user_id: int, ai_companion_id: int) -> ConversationSnapshot:
        """Create and return a brand-new empty conversation for a user/persona pair."""
        conversation = self.repository.create_conversation(user_id, ai_companion_id)
        return ConversationSnapshot(conversation=conversation, messages=[])

    def append_message(self, conversation_id: int, role: str, content: str) -> MessageRecord:
        """Persist one message inside the target conversation."""
        return self.repository.create_message(conversation_id=conversation_id, role=role, content=content)
