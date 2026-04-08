"""SQLite repositories for users and conversations."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.storage.database import SQLiteDatabase
from src.storage.models import ConversationRecord, MessageRecord, UserRecord


def _normalize_email(email: str) -> str:
    return email.strip().lower()


class UserRepository(ABC):
    """User repository contract."""

    @abstractmethod
    def find_by_email(self, email: str) -> UserRecord | None:
        """Look up a user by normalized email."""

    @abstractmethod
    def create_user(self, email: str, name: str, encrypted_password: str) -> UserRecord:
        """Create a new user."""


class SQLiteUserRepository(UserRepository):
    """SQLite-backed implementation of the user repository."""

    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def find_by_email(self, email: str) -> UserRecord | None:
        normalized_email = _normalize_email(email)
        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT id, email, name, encrypted_password, created_at
                FROM users
                WHERE email = ?
                """,
                (normalized_email,),
            ).fetchone()

        if row is None:
            return None
        return UserRecord(**dict(row))

    def create_user(self, email: str, name: str, encrypted_password: str) -> UserRecord:
        normalized_email = _normalize_email(email)
        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (email, name, encrypted_password)
                VALUES (?, ?, ?)
                """,
                (normalized_email, name.strip(), encrypted_password),
            )
            row = connection.execute(
                """
                SELECT id, email, name, encrypted_password, created_at
                FROM users
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
            connection.commit()

        return UserRecord(**dict(row))


class SQLiteConversationRepository:
    """Persistence for conversations and their messages."""

    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def get_latest_conversation(self, user_id: int) -> ConversationRecord | None:
        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT id, user_id, created_at, updated_at
                FROM conversations
                WHERE user_id = ?
                ORDER BY updated_at DESC, id DESC LIMIT 1
                """,
                (user_id,),
            ).fetchone()

        if row is None:
            return None
        return ConversationRecord(**dict(row))

    def create_conversation(self, user_id: int) -> ConversationRecord:
        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO conversations (user_id)
                VALUES (?)
                """,
                (user_id,),
            )
            row = connection.execute(
                """
                SELECT id, user_id, created_at, updated_at
                FROM conversations
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
            connection.commit()

        return ConversationRecord(**dict(row))

    def list_messages(self, conversation_id: int) -> list[MessageRecord]:
        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT id, conversation_id, role, content, created_at, updated_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (conversation_id,),
            ).fetchall()

        return [MessageRecord(**dict(row)) for row in rows]

    def create_message(self, conversation_id: int, role: str, content: str) -> MessageRecord:
        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO messages (conversation_id, role, content)
                VALUES (?, ?, ?)
                """,
                (conversation_id, role, content),
            )
            row = connection.execute(
                """
                SELECT id, conversation_id, role, content, created_at, updated_at
                FROM messages
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
            connection.commit()

        return MessageRecord(**dict(row))
