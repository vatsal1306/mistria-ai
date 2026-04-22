"""SQLite database bootstrap and connection management."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from src.Logging import get_logger
from src.storage.exceptions import DatabaseInitializationError, RepositoryError

logger = get_logger(__name__)


class SQLiteDatabase:
    """Manage the SQLite file used by the Streamlit app."""

    def __init__(self, database_path: str):
        self.database_path = database_path

    def initialize(self) -> None:
        """Create or migrate the SQLite schema required by the application."""
        os.makedirs(os.path.dirname(self.database_path), exist_ok=True)
        logger.info("Initializing SQLite database path=%s", self.database_path)

        table_statements = (
            """
            CREATE TABLE IF NOT EXISTS users
            (
                id
                INTEGER
                PRIMARY
                KEY
                AUTOINCREMENT,
                email
                TEXT
                NOT
                NULL
                UNIQUE
                COLLATE
                NOCASE,
                name
                TEXT
                NOT
                NULL,
                encrypted_password
                TEXT,
                created_at
                TEXT
                NOT
                NULL
                DEFAULT
                CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS user_companion
            (
                id
                INTEGER
                PRIMARY
                KEY
                AUTOINCREMENT,
                user_id
                INTEGER
                NOT
                NULL
                UNIQUE,
                intent_type
                TEXT
                NOT
                NULL,
                dominance_mode
                TEXT
                NOT
                NULL,
                intensity_level
                TEXT
                NOT
                NULL,
                silence_response
                TEXT
                NOT
                NULL,
                secret_desire
                TEXT
                NOT
                NULL,
                title
                TEXT,
                description
                TEXT,
                created_at
                TEXT
                NOT
                NULL
                DEFAULT
                CURRENT_TIMESTAMP,
                updated_at
                TEXT
                NOT
                NULL
                DEFAULT
                CURRENT_TIMESTAMP,
                FOREIGN
                KEY
            (
                user_id
            ) REFERENCES users
            (
                id
            ) ON DELETE CASCADE
                )
            """,
            """
            CREATE TABLE IF NOT EXISTS ai_companion
            (
                id
                INTEGER
                PRIMARY
                KEY
                AUTOINCREMENT,
                user_id
                INTEGER
                NOT
                NULL,
                title
                TEXT
                NOT
                NULL,
                description
                TEXT,
                gender
                TEXT
                NOT
                NULL,
                style
                TEXT
                NOT
                NULL,
                ethnicity
                TEXT
                NOT
                NULL,
                eye_color
                TEXT
                NOT
                NULL,
                hair_style
                TEXT
                NOT
                NULL,
                hair_color
                TEXT
                NOT
                NULL,
                personality
                TEXT
                NOT
                NULL,
                voice
                TEXT
                NOT
                NULL,
                connection
                TEXT
                NOT
                NULL,
                created_at
                TEXT
                NOT
                NULL
                DEFAULT
                CURRENT_TIMESTAMP,
                updated_at
                TEXT
                NOT
                NULL
                DEFAULT
                CURRENT_TIMESTAMP,
                FOREIGN
                KEY
            (
                user_id
            ) REFERENCES users
            (
                id
            ) ON DELETE CASCADE
                )
            """,
            """
            CREATE TABLE IF NOT EXISTS conversations
            (
                id
                INTEGER
                PRIMARY
                KEY
                AUTOINCREMENT,
                user_id
                INTEGER
                NOT
                NULL,
                ai_companion_id
                INTEGER,
                created_at
                TEXT
                NOT
                NULL
                DEFAULT
                CURRENT_TIMESTAMP,
                updated_at
                TEXT
                NOT
                NULL
                DEFAULT
                CURRENT_TIMESTAMP,
                FOREIGN
                KEY
            (
                user_id
            ) REFERENCES users
            (
                id
            ) ON DELETE CASCADE,
                FOREIGN
                KEY
            (
                ai_companion_id
            ) REFERENCES ai_companion
            (
                id
            )
              ON DELETE CASCADE
                )
            """,
            """
            CREATE TABLE IF NOT EXISTS messages
            (
                id
                INTEGER
                PRIMARY
                KEY
                AUTOINCREMENT,
                conversation_id
                INTEGER
                NOT
                NULL,
                role
                TEXT
                NOT
                NULL
                CHECK (
                role
                IN
            (
                'user',
                'assistant'
            )),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY
            (
                conversation_id
            ) REFERENCES conversations
            (
                id
            ) ON DELETE CASCADE
                )
            """,
        )

        index_statements = (
            """
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_user_companion_user_id
                ON user_companion(user_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_ai_companion_user_created_at
                ON ai_companion(user_id, created_at DESC, id DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_conversations_user_updated_at
                ON conversations(user_id, updated_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_conversations_user_ai_updated_at
                ON conversations(user_id, ai_companion_id, updated_at DESC, id DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_messages_conversation_created_at
                ON messages(conversation_id, created_at ASC, id ASC)
            """,
        )

        trigger_statements = (
            """
            CREATE TRIGGER IF NOT EXISTS trg_user_companion_updated_at
            AFTER
            UPDATE ON user_companion
                FOR EACH ROW
                WHEN NEW.updated_at = OLD.updated_at
            BEGIN
            UPDATE user_companion
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = OLD.id;
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_ai_companion_updated_at
            AFTER
            UPDATE ON ai_companion
                FOR EACH ROW
                WHEN NEW.updated_at = OLD.updated_at
            BEGIN
            UPDATE ai_companion
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = OLD.id;
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_conversations_updated_at
            AFTER
            UPDATE ON conversations
                FOR EACH ROW
                WHEN NEW.updated_at = OLD.updated_at
            BEGIN
            UPDATE conversations
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = OLD.id;
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_messages_updated_at
            AFTER
            UPDATE ON messages
                FOR EACH ROW
                WHEN NEW.updated_at = OLD.updated_at
            BEGIN
            UPDATE messages
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = OLD.id;
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_messages_touch_conversation_on_insert
            AFTER INSERT ON messages
            FOR EACH ROW
            BEGIN
            UPDATE conversations
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = NEW.conversation_id;
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trg_messages_touch_conversation_on_update
            AFTER
            UPDATE ON messages
                FOR EACH ROW
            BEGIN
            UPDATE conversations
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = NEW.conversation_id;
            END
            """,
        )

        try:
            with self.connection() as connection:
                for statement in table_statements:
                    connection.execute(statement)
                self._ensure_users_password_nullable(connection)
                self._ensure_conversations_ai_companion_column(connection)
                self._ensure_user_companion_metadata_columns(connection)
                self._ensure_ai_companion_metadata_columns(connection)
                for statement in index_statements:
                    connection.execute(statement)
                for statement in trigger_statements:
                    connection.execute(statement)
                connection.commit()
            logger.info("SQLite database initialized at %s", self.database_path)
        except sqlite3.Error as exc:
            logger.exception("SQLite database initialization failed path=%s", self.database_path)
            raise DatabaseInitializationError(f"Could not initialize SQLite database: {exc}") from exc

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Yield a configured SQLite connection with rollback-on-error semantics."""
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
        except sqlite3.Error as exc:
            logger.exception("SQLite operation failed path=%s", self.database_path)
            connection.rollback()
            raise RepositoryError(f"SQLite operation failed: {exc}") from exc
        finally:
            connection.close()

    @staticmethod
    def _column_exists(connection: sqlite3.Connection, table_name: str, column_name: str) -> bool:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        return any(row["name"] == column_name for row in rows)

    @staticmethod
    def _column_is_not_null(connection: sqlite3.Connection, table_name: str, column_name: str) -> bool:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        for row in rows:
            if row["name"] == column_name:
                return bool(row["notnull"])
        return False

    def _ensure_users_password_nullable(self, connection: sqlite3.Connection) -> None:
        if not self._column_is_not_null(connection, "users", "encrypted_password"):
            return

        logger.info("Migrating users.encrypted_password to nullable column")
        connection.execute("PRAGMA foreign_keys = OFF")
        try:
            connection.execute("ALTER TABLE users RENAME TO users_legacy")
            connection.execute(
                """
                CREATE TABLE users
                (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    name TEXT NOT NULL,
                    encrypted_password TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                INSERT INTO users (id, email, name, encrypted_password, created_at)
                SELECT id, email, name, NULLIF(encrypted_password, ''), created_at
                FROM users_legacy
                """
            )
            connection.execute("DROP TABLE users_legacy")
        finally:
            connection.execute("PRAGMA foreign_keys = ON")

    def _ensure_conversations_ai_companion_column(self, connection: sqlite3.Connection) -> None:
        if self._column_exists(connection, "conversations", "ai_companion_id"):
            return

        logger.info("Adding conversations.ai_companion_id column via migration")
        connection.execute(
            """
            ALTER TABLE conversations
                ADD COLUMN ai_companion_id INTEGER REFERENCES ai_companion (id) ON DELETE CASCADE
            """
        )

    def _ensure_user_companion_metadata_columns(self, connection: sqlite3.Connection) -> None:
        if not self._column_exists(connection, "user_companion", "title"):
            connection.execute("ALTER TABLE user_companion ADD COLUMN title TEXT")
        if not self._column_exists(connection, "user_companion", "description"):
            connection.execute("ALTER TABLE user_companion ADD COLUMN description TEXT")

    def _ensure_ai_companion_metadata_columns(self, connection: sqlite3.Connection) -> None:
        if not self._column_exists(connection, "ai_companion", "description"):
            connection.execute("ALTER TABLE ai_companion ADD COLUMN description TEXT")
