"""Conversation history abstraction with a SQLite implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.storage.models import ConversationRecord, MessageRecord
from src.storage.repositories import SQLiteConversationRepository


@dataclass(frozen=True, slots=True)
class ConversationSnapshot:
    conversation: ConversationRecord
    messages: list[MessageRecord]


class ConversationStore(ABC):
    """Abstract persistence interface for chat history."""

    @abstractmethod
    def get_or_create_latest_conversation(self, user_id: int) -> ConversationSnapshot:
        """Return the user's latest conversation, creating one if none exists."""

    @abstractmethod
    def create_fresh_conversation(self, user_id: int) -> ConversationSnapshot:
        """Create a new empty conversation for the user."""

    @abstractmethod
    def append_message(self, conversation_id: int, role: str, content: str) -> MessageRecord:
        """Persist a message in the current conversation."""


class SQLiteConversationStore(ConversationStore):
    """SQLite implementation of the conversation history store."""

    def __init__(self, repository: SQLiteConversationRepository):
        self.repository = repository

    def get_or_create_latest_conversation(self, user_id: int) -> ConversationSnapshot:
        conversation = self.repository.get_latest_conversation(user_id)
        if conversation is None:
            conversation = self.repository.create_conversation(user_id)

        return ConversationSnapshot(
            conversation=conversation,
            messages=self.repository.list_messages(conversation.id),
        )

    def create_fresh_conversation(self, user_id: int) -> ConversationSnapshot:
        conversation = self.repository.create_conversation(user_id)
        return ConversationSnapshot(conversation=conversation, messages=[])

    def append_message(self, conversation_id: int, role: str, content: str) -> MessageRecord:
        return self.repository.create_message(conversation_id=conversation_id, role=role, content=content)
