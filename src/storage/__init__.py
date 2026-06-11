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
    UserRecord,
)
from src.storage.memory_repository import MemoryRepository, SQLiteMemoryRepository
from src.storage.archetype_repository import ArchetypeResultRepository, SQLiteArchetypeResultRepository
from src.storage.repositories import (
    SQLiteAICompanionRepository,
    SQLiteConversationRepository,
    SQLiteUserRepository,
    UserRepository,
)
from src.storage.service import ChatHistoryService

__all__ = [
    "AICompanionRecord",
    "ArchetypeResultRecord",
    "ArchetypeResultRepository",
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
    "SQLiteUserRepository",
    "StorageError",
    "UserRecord",
    "UserRepository",
]
