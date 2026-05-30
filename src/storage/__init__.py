"""Expose the supported storage package API."""

from src.storage.conversation_store import ConversationSnapshot, ConversationStore, SQLiteConversationStore
from src.storage.database import SQLiteDatabase
from src.storage.exceptions import DatabaseInitializationError, RepositoryError, StorageError
from src.storage.models import (
    AICompanionRecord,
    ArchetypeResultRecord,
    ConversationRecord,
    MemoryRecord,
    MessageRecord,
    UserCompanionRecord,
    UserRecord,
)
from src.storage.memory_repository import MemoryRepository, SQLiteMemoryRepository
from src.storage.repositories import (
    SQLiteAICompanionRepository,
    SQLiteArchetypeResultRepository,
    SQLiteConversationRepository,
    SQLiteUserCompanionRepository,
    SQLiteUserRepository,
    UserRepository,
)
from src.storage.service import ChatHistoryService

__all__ = [
    "AICompanionRecord",
    "ArchetypeResultRecord",
    "ChatHistoryService",
    "ConversationRecord",
    "ConversationSnapshot",
    "ConversationStore",
    "DatabaseInitializationError",
    "MemoryRecord",
    "MemoryRepository",
    "MessageRecord",
    "RepositoryError",
    "SQLiteAICompanionRepository",
    "SQLiteArchetypeResultRepository",
    "SQLiteConversationRepository",
    "SQLiteConversationStore",
    "SQLiteDatabase",
    "SQLiteMemoryRepository",
    "SQLiteUserCompanionRepository",
    "SQLiteUserRepository",
    "StorageError",
    "UserCompanionRecord",
    "UserRecord",
    "UserRepository",
]
