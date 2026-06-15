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
                TEXT
                NOT
                NULL,
                gender
                TEXT
                NOT
                NULL,
                visual_style
                TEXT
                NOT
                NULL
                DEFAULT
                'Realistic',
                companion_ethnicity
                TEXT
                NOT
                NULL
                DEFAULT
                'East Asian',
                eye_color
                TEXT
                NOT
                NULL,
                age
                INTEGER
                NOT
                NULL
                DEFAULT
                18,
                hair_length
                TEXT
                NOT
                NULL
                DEFAULT
                'Average',
                hair_style
                TEXT
                NOT
                NULL,
                hair_color
                TEXT
                NOT
                NULL,
                companion_personality
                TEXT
                NOT
                NULL
                DEFAULT
                'Playful',
                companion_profession
                TEXT
                NOT
                NULL
                DEFAULT
                'Companion',
                body_type
                TEXT
                NOT
                NULL
                DEFAULT
                'Natural',
                bust
                TEXT
                NOT
                NULL
                DEFAULT
                'Natural',
                height
                TEXT
                NOT
                NULL
                DEFAULT
                'Average',
                intention
                TEXT
                NOT
                NULL
                DEFAULT
                'quick',
                style
                TEXT
                NOT
                NULL
                DEFAULT
                '',
                ethnicity
                TEXT
                NOT
                NULL
                DEFAULT
                '',
                personality
                TEXT
                NOT
                NULL
                DEFAULT
                '',
                voice
                TEXT
                NOT
                NULL
                DEFAULT
                '',
                connection
                TEXT
                NOT
                NULL
                DEFAULT
                '',
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
            """
            CREATE TABLE IF NOT EXISTS memories
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                ai_companion_id INTEGER NOT NULL,
                source_conversation_id INTEGER,
                source_message_id INTEGER,
                memory_type TEXT NOT NULL CHECK (memory_type IN ('fact','preference','pattern','emotional')),
                canonical_key TEXT NOT NULL,
                content TEXT NOT NULL,
                importance INTEGER NOT NULL,
                confidence REAL NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('active','superseded','archived')) DEFAULT 'active',
                supersedes_memory_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_retrieved_at TEXT,
                retrieval_count INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (ai_companion_id) REFERENCES ai_companion (id) ON DELETE CASCADE,
                FOREIGN KEY (source_conversation_id) REFERENCES conversations (id) ON DELETE SET NULL,
                FOREIGN KEY (source_message_id) REFERENCES messages (id) ON DELETE SET NULL,
                FOREIGN KEY (supersedes_memory_id) REFERENCES memories (id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS archetype_results
            (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                onboarding_pathway TEXT NOT NULL DEFAULT 'slow_burn',
                trait_scores_json TEXT NOT NULL,
                primary_archetype TEXT NOT NULL CHECK (primary_archetype IN ('devotee', 'muse', 'protector', 'rebel', 'soulmate')),
                primary_similarity REAL NOT NULL CHECK (primary_similarity >= -3.0 AND primary_similarity <= 3.0),
                secondary_archetype TEXT CHECK (secondary_archetype IS NULL OR secondary_archetype IN ('devotee', 'muse', 'protector', 'rebel', 'soulmate')),
                secondary_similarity REAL CHECK (secondary_similarity IS NULL OR (secondary_similarity >= -3.0 AND secondary_similarity <= 3.0)),
                blend_active INTEGER NOT NULL CHECK (blend_active IN (0, 1)) DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            """,
        )

        index_statements = (
            """
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)
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
            """
            CREATE INDEX IF NOT EXISTS idx_memories_scope_status
                ON memories(user_id, ai_companion_id, status)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_memories_scope_key_status
                ON memories(user_id, ai_companion_id, canonical_key, status)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_memories_source_message
                ON memories(source_message_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_archetype_results_user_latest
                ON archetype_results(user_id, created_at DESC, id DESC)
            """,
        )

        trigger_statements = (
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
            """
            CREATE TRIGGER IF NOT EXISTS trg_memories_updated_at
            AFTER
            UPDATE ON memories
                FOR EACH ROW
                WHEN NEW.updated_at = OLD.updated_at
            BEGIN
            UPDATE memories
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = OLD.id;
            END
            """,
        )

        try:
            with self.connection() as connection:
                for statement in table_statements:
                    connection.execute(statement)
                self._ensure_users_password_nullable(connection)
                self._ensure_ai_companion_feature_columns(connection)
                self._ensure_conversations_ai_companion_column(connection)
                self._ensure_archetype_results_constraints(connection)
                self._drop_user_companion_objects(connection)
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

    @staticmethod
    def _drop_user_companion_objects(connection: sqlite3.Connection) -> None:
        connection.execute("DROP TRIGGER IF EXISTS trg_user_companion_updated_at")
        connection.execute("DROP INDEX IF EXISTS idx_user_companion_user_id")
        connection.execute("DROP TABLE IF EXISTS user_companion")

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

    def _ensure_ai_companion_feature_columns(self, connection: sqlite3.Connection) -> None:
        column_defs = {
            "visual_style": "TEXT NOT NULL DEFAULT 'Realistic'",
            "companion_ethnicity": "TEXT NOT NULL DEFAULT 'East Asian'",
            "age": "INTEGER NOT NULL DEFAULT 18",
            "hair_length": "TEXT NOT NULL DEFAULT 'Average'",
            "companion_personality": "TEXT NOT NULL DEFAULT 'Playful'",
            "companion_profession": "TEXT NOT NULL DEFAULT 'Companion'",
            "body_type": "TEXT NOT NULL DEFAULT 'Natural'",
            "bust": "TEXT NOT NULL DEFAULT 'Natural'",
            "height": "TEXT NOT NULL DEFAULT 'Average'",
            "intention": "TEXT NOT NULL DEFAULT 'quick'",
            "style": "TEXT NOT NULL DEFAULT ''",
            "ethnicity": "TEXT NOT NULL DEFAULT ''",
            "personality": "TEXT NOT NULL DEFAULT ''",
            "voice": "TEXT NOT NULL DEFAULT ''",
            "connection": "TEXT NOT NULL DEFAULT ''",
        }

        added_columns = False
        for column_name, column_def in column_defs.items():
            if self._column_exists(connection, "ai_companion", column_name):
                continue
            logger.info("Adding ai_companion.%s column via migration", column_name)
            connection.execute(f"ALTER TABLE ai_companion ADD COLUMN {column_name} {column_def}")
            added_columns = True

        if not added_columns:
            return

        if self._column_exists(connection, "ai_companion", "style"):
            connection.execute(
                """
                UPDATE ai_companion
                SET visual_style = style
                WHERE style IS NOT NULL AND style != ''
                """
            )
        if self._column_exists(connection, "ai_companion", "ethnicity"):
            connection.execute(
                """
                UPDATE ai_companion
                SET companion_ethnicity = CASE
                    WHEN ethnicity IN (
                        'African Descent',
                        'South Asian',
                        'Eastern European',
                        'East Asian',
                        'Latinx',
                        'Latina',
                        'Middle Eastern'
                    ) THEN ethnicity
                    ELSE companion_ethnicity
                END
                WHERE ethnicity IS NOT NULL AND ethnicity != ''
                """
            )
        if self._column_exists(connection, "ai_companion", "hair_style"):
            connection.execute(
                """
                UPDATE ai_companion
                SET hair_length = CASE
                    WHEN hair_style IN ('Short', 'Long', 'Extra Long') THEN hair_style
                    ELSE hair_length
                END
                WHERE hair_style IS NOT NULL AND hair_style != ''
                """
            )
        if self._column_exists(connection, "ai_companion", "personality"):
            connection.execute(
                """
                UPDATE ai_companion
                SET companion_personality = CASE personality
                    WHEN 'Flirty' THEN 'Flirty'
                    WHEN 'Obsessed' THEN 'Obsessed'
                    WHEN 'Playful' THEN 'Playful'
                    WHEN 'Dominant' THEN 'Dominant'
                    WHEN 'Mysterious' THEN 'Mysterious'
                    WHEN 'Caring' THEN 'Caring'
                    WHEN 'Confident' THEN 'Confident'
                    WHEN 'Sensual' THEN 'Sensual'
                    WHEN 'Passionate' THEN 'Passionate'
                    WHEN 'Seductive' THEN 'Flirty'
                    WHEN 'Adventurous' THEN 'Playful'
                    WHEN 'Ambitious' THEN 'Confident'
                    WHEN 'Submissive' THEN 'Passionate'
                    WHEN 'Intellectual' THEN 'Mysterious'
                    ELSE companion_personality
                END
                WHERE personality IS NOT NULL AND personality != ''
                """
            )
        if self._column_exists(connection, "ai_companion", "connection"):
            connection.execute(
                """
                UPDATE ai_companion
                SET intention = connection
                WHERE connection IS NOT NULL AND connection != ''
                """
            )

    def _ensure_archetype_results_constraints(self, connection: sqlite3.Connection) -> None:
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='archetype_results'"
        ).fetchone()
        if not row:
            return

        sql = row["sql"]
        if "CHECK" in sql and "UNIQUE" in sql:
            return

        logger.info("Migrating archetype_results to include CHECK and UNIQUE constraints")
        connection.execute("PRAGMA foreign_keys = OFF")
        try:
            connection.execute("ALTER TABLE archetype_results RENAME TO archetype_results_legacy")
            connection.execute(
                """
                CREATE TABLE archetype_results
                (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    onboarding_pathway TEXT NOT NULL DEFAULT 'slow_burn',
                    trait_scores_json TEXT NOT NULL,
                    primary_archetype TEXT NOT NULL CHECK (primary_archetype IN ('devotee', 'muse', 'protector', 'rebel', 'soulmate')),
                    primary_similarity REAL NOT NULL CHECK (primary_similarity >= -3.0 AND primary_similarity <= 3.0),
                    secondary_archetype TEXT CHECK (secondary_archetype IS NULL OR secondary_archetype IN ('devotee', 'muse', 'protector', 'rebel', 'soulmate')),
                    secondary_similarity REAL CHECK (secondary_similarity IS NULL OR (secondary_similarity >= -3.0 AND secondary_similarity <= 3.0)),
                    blend_active INTEGER NOT NULL CHECK (blend_active IN (0, 1)) DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                """
                INSERT INTO archetype_results (
                    id, user_id, onboarding_pathway, trait_scores_json,
                    primary_archetype, primary_similarity,
                    secondary_archetype, secondary_similarity,
                    blend_active, created_at
                )
                SELECT id, user_id, onboarding_pathway, trait_scores_json,
                       primary_archetype, primary_similarity,
                       secondary_archetype, secondary_similarity,
                       blend_active, created_at
                FROM archetype_results_legacy
                WHERE id IN (
                    SELECT MAX(id)
                    FROM archetype_results_legacy
                    GROUP BY user_id
                )
                  AND primary_archetype IN ('devotee', 'muse', 'protector', 'rebel', 'soulmate')
                  AND primary_similarity >= -3.0 AND primary_similarity <= 3.0
                  AND (secondary_archetype IS NULL OR secondary_archetype IN ('devotee', 'muse', 'protector', 'rebel', 'soulmate'))
                  AND (secondary_similarity IS NULL OR (secondary_similarity >= -3.0 AND secondary_similarity <= 3.0))
                  AND blend_active IN (0, 1)
                """
            )
            connection.execute("DROP TABLE archetype_results_legacy")
        finally:
            connection.execute("PRAGMA foreign_keys = ON")
