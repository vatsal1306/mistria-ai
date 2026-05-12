"""Unit tests for SQLite repository implementations."""

from __future__ import annotations

import sqlite3

import pytest

from src.storage.conversation_store import SQLiteConversationStore
from src.storage.database import SQLiteDatabase
from src.storage.exceptions import RepositoryError
from src.storage.repositories import (
    SQLiteAICompanionRepository,
    SQLiteConversationRepository,
    SQLiteUserCompanionRepository,
    SQLiteUserRepository,
    _normalize_email,
)
from src.storage.service import ChatHistoryService


def _create_user(repository: SQLiteUserRepository, email: str = "USER@Example.COM"):
    return repository.create_user(email=email, name=" Test User ", encrypted_password=None)


def _create_ai_companion(repository: SQLiteAICompanionRepository, user_id: int, title: str = "Aria"):
    return repository.create(
        user_id=user_id,
        title=title,
        description="A focused test companion.",
        gender="Female",
        style="Anime",
        ethnicity="East Asian",
        eye_color="Brown",
        hair_style="Long",
        hair_color="Black",
        personality="Playful",
        voice="Calm",
        connection_value="New Encounter",
    )


def test_normalize_email_strips_and_lowercases():
    assert _normalize_email("  Mixed@Example.COM ") == "mixed@example.com"


def test_user_repository_create_and_lookup(sqlite_db):
    repository = SQLiteUserRepository(sqlite_db)

    created = _create_user(repository)

    assert created.email == "user@example.com"
    assert created.name == "Test User"
    assert repository.find_by_email(" USER@example.com ").id == created.id
    assert repository.find_by_id(created.id) == created
    assert repository.find_by_email("missing@example.com") is None
    assert repository.find_by_id(9999) is None


def test_user_companion_repository_upserts_latest_values(sqlite_db):
    user = _create_user(SQLiteUserRepository(sqlite_db))
    repository = SQLiteUserCompanionRepository(sqlite_db)

    first = repository.upsert(
        user_id=user.id,
        intent_type="easy",
        dominance_mode="user_leads",
        intensity_level="show_me",
        silence_response="wait",
        secret_desire="running",
        title="First",
        description="First description",
    )
    second = repository.upsert(
        user_id=user.id,
        intent_type="alive",
        dominance_mode="ai_leads",
        intensity_level="break_glass",
        silence_response="come_looking",
        secret_desire="both",
        title="Second",
        description="Second description",
    )

    assert first.id == second.id
    assert repository.find_by_user_id(user.id).title == "Second"
    assert repository.find_by_user_id(9999) is None


def test_ai_companion_repository_create_find_list_and_latest(sqlite_db):
    user = _create_user(SQLiteUserRepository(sqlite_db))
    repository = SQLiteAICompanionRepository(sqlite_db)

    first = _create_ai_companion(repository, user.id, title="Aria")
    second = _create_ai_companion(repository, user.id, title="Nova")

    assert repository.find_by_id(first.id) == first
    assert repository.find_by_id(9999) is None
    assert [record.id for record in repository.list_by_user_id(user.id)] == [second.id, first.id]
    assert repository.find_latest_by_user_id(user.id).id == second.id
    assert repository.find_latest_by_user_id(9999) is None


def test_conversation_repository_and_store_round_trip(sqlite_db):
    user = _create_user(SQLiteUserRepository(sqlite_db))
    ai_companion = _create_ai_companion(SQLiteAICompanionRepository(sqlite_db), user.id)
    repository = SQLiteConversationRepository(sqlite_db)
    store = SQLiteConversationStore(repository)
    history = ChatHistoryService(store)

    assert history.load_latest(user.id, ai_companion.id) is None

    first = store.get_or_create_latest_conversation(user.id, ai_companion.id)
    assert first.messages == []
    message = history.save_message(first.conversation.id, "user", "hello")
    assert message.content == "hello"

    snapshot = history.load_latest(user.id, ai_companion.id)
    assert snapshot.conversation.id == first.conversation.id
    assert [item.content for item in snapshot.messages] == ["hello"]

    reused = store.get_or_create_latest_conversation(user.id, ai_companion.id)
    fresh = history.start_fresh(user.id, ai_companion.id)
    assert reused.conversation.id == first.conversation.id
    assert fresh.conversation.id != first.conversation.id


def test_database_connection_rolls_back_sqlite_errors(sqlite_db):
    with pytest.raises(RepositoryError):
        with sqlite_db.connection() as connection:
            connection.execute("INSERT INTO users (email, name) VALUES ('dupe@example.com', 'A')")
            connection.execute("INSERT INTO users (email, name) VALUES ('dupe@example.com', 'B')")

    with sqlite_db.connection() as connection:
        rows = connection.execute("SELECT email FROM users WHERE email = 'dupe@example.com'").fetchall()
    assert rows == []


def test_database_migrates_legacy_nullable_password_and_conversation_companion(tmp_path):
    db_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                name TEXT NOT NULL,
                encrypted_password TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO users (email, name, encrypted_password) VALUES ('legacy@example.com', 'Legacy', '');
            CREATE TABLE conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        connection.commit()
    finally:
        connection.close()

    database = SQLiteDatabase(str(db_path))
    database.initialize()

    with database.connection() as connection:
        user_columns = {row["name"]: row for row in connection.execute("PRAGMA table_info(users)").fetchall()}
        conversation_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(conversations)").fetchall()
        }
        encrypted_password = connection.execute(
            "SELECT encrypted_password FROM users WHERE email = 'legacy@example.com'"
        ).fetchone()["encrypted_password"]

    assert user_columns["encrypted_password"]["notnull"] == 0
    assert encrypted_password is None
    assert "ai_companion_id" in conversation_columns
