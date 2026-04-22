"""SQLite repositories for users and conversations."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.Logging import get_logger
from src.storage.database import SQLiteDatabase
from src.storage.models import (
    AICompanionRecord,
    ConversationRecord,
    MessageRecord,
    UserCompanionRecord,
    UserRecord,
)

logger = get_logger(__name__)


def _normalize_email(email: str) -> str:
    """Normalize an email address for case-insensitive lookups and storage."""
    return email.strip().lower()


class UserRepository(ABC):
    """User repository contract."""

    @abstractmethod
    def find_by_email(self, email: str) -> UserRecord | None:
        """Look up a user by normalized email."""

    @abstractmethod
    def find_by_id(self, user_id: int) -> UserRecord | None:
        """Look up a user by internal identifier."""

    @abstractmethod
    def create_user(self, email: str, name: str, encrypted_password: str | None) -> UserRecord:
        """Create a new user."""


class SQLiteUserRepository(UserRepository):
    """SQLite-backed implementation of the user repository."""

    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def find_by_email(self, email: str) -> UserRecord | None:
        """Fetch a user by normalized email address."""
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
            logger.debug("User lookup by email missed email=%s", normalized_email)
            return None
        user = UserRecord(**dict(row))
        logger.debug("User lookup by email hit user_id=%s email=%s", user.id, user.email)
        return user

    def find_by_id(self, user_id: int) -> UserRecord | None:
        """Fetch a user by its internal primary key."""
        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT id, email, name, encrypted_password, created_at
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()

        if row is None:
            logger.debug("User lookup by id missed user_id=%s", user_id)
            return None
        user = UserRecord(**dict(row))
        logger.debug("User lookup by id hit user_id=%s email=%s", user.id, user.email)
        return user

    def create_user(self, email: str, name: str, encrypted_password: str | None) -> UserRecord:
        """Insert a new user row and return the created record."""
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

        user = UserRecord(**dict(row))
        logger.debug("Created user record user_id=%s email=%s", user.id, user.email)
        return user


class SQLiteUserCompanionRepository:
    """Persistence for user-level companion preferences."""

    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def find_by_user_id(self, user_id: int) -> UserCompanionRecord | None:
        """Fetch the saved user-companion preferences for one user."""
        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    user_id,
                    intent_type,
                    dominance_mode,
                    intensity_level,
                    silence_response,
                    secret_desire,
                    title,
                    description,
                    created_at,
                    updated_at
                FROM user_companion
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()

        if row is None:
            logger.debug("User companion lookup missed user_id=%s", user_id)
            return None
        record = UserCompanionRecord(**dict(row))
        logger.debug("User companion lookup hit record_id=%s user_id=%s", record.id, record.user_id)
        return record

    def upsert(
        self,
        user_id: int,
        intent_type: str,
        dominance_mode: str,
        intensity_level: str,
        silence_response: str,
        secret_desire: str,
        title: str | None,
        description: str | None,
    ) -> UserCompanionRecord:
        """Insert or replace the user-companion preferences for one user."""
        with self.database.connection() as connection:
            connection.execute(
                """
                INSERT INTO user_companion
                (
                    user_id,
                    intent_type,
                    dominance_mode,
                    intensity_level,
                    silence_response,
                    secret_desire,
                    title,
                    description
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id)
                DO UPDATE SET
                    intent_type = excluded.intent_type,
                    dominance_mode = excluded.dominance_mode,
                    intensity_level = excluded.intensity_level,
                    silence_response = excluded.silence_response,
                    secret_desire = excluded.secret_desire,
                    title = excluded.title,
                    description = excluded.description,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    user_id,
                    intent_type,
                    dominance_mode,
                    intensity_level,
                    silence_response,
                    secret_desire,
                    title,
                    description,
                ),
            )
            row = connection.execute(
                """
                SELECT
                    id,
                    user_id,
                    intent_type,
                    dominance_mode,
                    intensity_level,
                    silence_response,
                    secret_desire,
                    title,
                    description,
                    created_at,
                    updated_at
                FROM user_companion
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
            connection.commit()

        record = UserCompanionRecord(**dict(row))
        logger.debug("Upserted user companion record record_id=%s user_id=%s", record.id, record.user_id)
        return record


class SQLiteAICompanionRepository:
    """Persistence for user-created AI companion personas."""

    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def create(
        self,
        user_id: int,
        title: str,
        description: str | None,
        gender: str,
        style: str,
        ethnicity: str,
        eye_color: str,
        hair_style: str,
        hair_color: str,
        personality: str,
        voice: str,
        connection_value: str,
    ) -> AICompanionRecord:
        """Insert a new AI companion persona and return the saved row."""
        with self.database.connection() as db_connection:
            cursor = db_connection.execute(
                """
                INSERT INTO ai_companion
                (
                    user_id,
                    title,
                    description,
                    gender,
                    style,
                    ethnicity,
                    eye_color,
                    hair_style,
                    hair_color,
                    personality,
                    voice,
                    connection
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    title,
                    description,
                    gender,
                    style,
                    ethnicity,
                    eye_color,
                    hair_style,
                    hair_color,
                    personality,
                    voice,
                    connection_value,
                ),
            )
            row = db_connection.execute(
                """
                SELECT
                    id,
                    user_id,
                    title,
                    description,
                    gender,
                    style,
                    ethnicity,
                    eye_color,
                    hair_style,
                    hair_color,
                    personality,
                    voice,
                    connection,
                    created_at,
                    updated_at
                FROM ai_companion
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
            db_connection.commit()

        record = AICompanionRecord(**dict(row))
        logger.debug(
            "Created AI companion record ai_companion_id=%s user_id=%s title=%s",
            record.id,
            record.user_id,
            record.title,
        )
        return record

    def find_by_id(self, ai_companion_id: int) -> AICompanionRecord | None:
        """Fetch one AI companion persona by primary key."""
        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    user_id,
                    title,
                    description,
                    gender,
                    style,
                    ethnicity,
                    eye_color,
                    hair_style,
                    hair_color,
                    personality,
                    voice,
                    connection,
                    created_at,
                    updated_at
                FROM ai_companion
                WHERE id = ?
                """,
                (ai_companion_id,),
            ).fetchone()

        if row is None:
            logger.debug("AI companion lookup missed ai_companion_id=%s", ai_companion_id)
            return None
        record = AICompanionRecord(**dict(row))
        logger.debug("AI companion lookup hit ai_companion_id=%s user_id=%s", record.id, record.user_id)
        return record

    def list_by_user_id(self, user_id: int) -> list[AICompanionRecord]:
        """List all AI companion personas owned by a user, newest first."""
        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    user_id,
                    title,
                    description,
                    gender,
                    style,
                    ethnicity,
                    eye_color,
                    hair_style,
                    hair_color,
                    personality,
                    voice,
                    connection,
                    created_at,
                    updated_at
                FROM ai_companion
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (user_id,),
            ).fetchall()

        records = [AICompanionRecord(**dict(row)) for row in rows]
        logger.debug("Listed AI companion records user_id=%s count=%s", user_id, len(records))
        return records

    def find_latest_by_user_id(self, user_id: int) -> AICompanionRecord | None:
        """Fetch the most recently created AI companion persona for a user."""
        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    user_id,
                    title,
                    description,
                    gender,
                    style,
                    ethnicity,
                    eye_color,
                    hair_style,
                    hair_color,
                    personality,
                    voice,
                    connection,
                    created_at,
                    updated_at
                FROM ai_companion
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()

        if row is None:
            logger.debug("Latest AI companion lookup missed user_id=%s", user_id)
            return None
        record = AICompanionRecord(**dict(row))
        logger.debug("Latest AI companion lookup hit user_id=%s ai_companion_id=%s", user_id, record.id)
        return record


class SQLiteConversationRepository:
    """Persistence for conversations and their messages."""

    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def get_latest_conversation(self, user_id: int, ai_companion_id: int) -> ConversationRecord | None:
        """Fetch the most recently updated conversation for a user/persona pair."""
        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT id, user_id, ai_companion_id, created_at, updated_at
                FROM conversations
                WHERE user_id = ? AND ai_companion_id = ?
                ORDER BY updated_at DESC, id DESC LIMIT 1
                """,
                (user_id, ai_companion_id),
            ).fetchone()

        if row is None:
            logger.debug("Conversation lookup missed user_id=%s ai_companion_id=%s", user_id, ai_companion_id)
            return None
        record = ConversationRecord(**dict(row))
        logger.debug(
            "Conversation lookup hit conversation_id=%s user_id=%s ai_companion_id=%s",
            record.id,
            record.user_id,
            record.ai_companion_id,
        )
        return record

    def create_conversation(self, user_id: int, ai_companion_id: int) -> ConversationRecord:
        """Insert a new conversation scoped to a user/persona pair."""
        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO conversations (user_id, ai_companion_id)
                VALUES (?, ?)
                """,
                (user_id, ai_companion_id),
            )
            row = connection.execute(
                """
                SELECT id, user_id, ai_companion_id, created_at, updated_at
                FROM conversations
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
            connection.commit()

        record = ConversationRecord(**dict(row))
        logger.debug(
            "Created conversation record conversation_id=%s user_id=%s ai_companion_id=%s",
            record.id,
            record.user_id,
            record.ai_companion_id,
        )
        return record

    def list_messages(self, conversation_id: int) -> list[MessageRecord]:
        """List all messages in one conversation in creation order."""
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

        records = [MessageRecord(**dict(row)) for row in rows]
        logger.debug("Listed conversation messages conversation_id=%s count=%s", conversation_id, len(records))
        return records

    def create_message(self, conversation_id: int, role: str, content: str) -> MessageRecord:
        """Insert one chat message and return the saved row."""
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

        record = MessageRecord(**dict(row))
        logger.debug(
            "Created message record message_id=%s conversation_id=%s role=%s content_length=%s",
            record.id,
            record.conversation_id,
            record.role,
            len(record.content),
        )
        return record
