"""Expose the supported storage package API."""

from src.storage.conversation_store import ConversationSnapshot, ConversationStore, SQLiteConversationStore
from src.storage.database import SQLiteDatabase
from src.storage.exceptions import DatabaseInitializationError, RepositoryError, StorageError
from src.storage.models import (
    AICompanionRecord,
    ConversationRecord,
    MessageRecord,
    UserCompanionRecord,
    UserRecord,
)
from src.storage.repositories import (
    SQLiteAICompanionRepository,
    SQLiteConversationRepository,
    SQLiteUserCompanionRepository,
    SQLiteUserRepository,
    UserRepository,
)
from src.storage.service import ChatHistoryService

__all__ = [
    "AICompanionRecord",
    "ChatHistoryService",
    "ConversationRecord",
    "ConversationSnapshot",
    "ConversationStore",
    "DatabaseInitializationError",
    "MessageRecord",
    "RepositoryError",
    "SQLiteAICompanionRepository",
    "SQLiteConversationRepository",
    "SQLiteConversationStore",
    "SQLiteDatabase",
    "SQLiteUserCompanionRepository",
    "SQLiteUserRepository",
    "StorageError",
    "UserCompanionRecord",
    "UserRecord",
    "UserRepository",
]
