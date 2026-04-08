"""SQLite database bootstrap and connection management."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from src.Logging import logger
from src.storage.exceptions import DatabaseInitializationError, RepositoryError


class SQLiteDatabase:
    """Manage the SQLite file used by the Streamlit app."""

    def __init__(self, database_path: str):
        self.database_path = database_path

    def initialize(self) -> None:
        os.makedirs(os.path.dirname(self.database_path), exist_ok=True)

        schema_statements = (
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
                TEXT
                NOT
                NULL,
                created_at
                TEXT
                NOT
                NULL
                DEFAULT
                CURRENT_TIMESTAMP
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
            """
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_conversations_user_updated_at
                ON conversations(user_id, updated_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_messages_conversation_created_at
                ON messages(conversation_id, created_at ASC, id ASC)
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
                for statement in schema_statements:
                    connection.execute(statement)
                connection.commit()
            logger.info("SQLite database initialized at %s", self.database_path)
        except sqlite3.Error as exc:
            raise DatabaseInitializationError(f"Could not initialize SQLite database: {exc}") from exc

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
        except sqlite3.Error as exc:
            connection.rollback()
            raise RepositoryError(f"SQLite operation failed: {exc}") from exc
        finally:
            connection.close()
