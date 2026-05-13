"""Unit tests for the memory backfill script."""

from __future__ import annotations

import argparse
from unittest import mock

import pytest

from scripts.backfill_memory import (
    BackfillStats,
    load_processed_message_ids,
    parse_args,
    run_backfill,
    scan_messages,
)
from src.memory.schemas import MemoryExtraction
from src.storage.database import SQLiteDatabase


@pytest.fixture
def tmp_database(tmp_path):
    """Create a temporary SQLite database with the full schema."""
    db_path = str(tmp_path / "test.db")
    database = SQLiteDatabase(db_path)
    database.initialize()

    # Seed a user, companion, conversation, and messages
    with database.connection() as conn:
        conn.execute(
            "INSERT INTO users (id, email, name) VALUES (1, 'alice@example.com', 'Alice')"
        )
        conn.execute(
            "INSERT INTO users (id, email, name) VALUES (2, 'bob@example.com', 'Bob')"
        )
        conn.execute(
            "INSERT INTO ai_companion (id, user_id, title, description, gender, style, ethnicity, "
            "eye_color, hair_style, hair_color, personality, voice, connection) "
            "VALUES (10, 1, 'Mira', 'desc', 'Female', 'Anime', 'Asian', 'Brown', 'Long', 'Black', "
            "'Playful', 'Calm', 'New Encounter')"
        )
        conn.execute(
            "INSERT INTO ai_companion (id, user_id, title, description, gender, style, ethnicity, "
            "eye_color, hair_style, hair_color, personality, voice, connection) "
            "VALUES (20, 2, 'Kai', 'desc', 'Male', 'Real', 'European', 'Blue', 'Short', 'Blond', "
            "'Intense', 'Deep', 'Old Friend')"
        )
        conn.execute(
            "INSERT INTO conversations (id, user_id, ai_companion_id) VALUES (100, 1, 10)"
        )
        conn.execute(
            "INSERT INTO conversations (id, user_id, ai_companion_id) VALUES (200, 2, 20)"
        )
        # Alice's messages
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content) VALUES (1, 100, 'user', 'I love dogs.')"
        )
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content) VALUES (2, 100, 'assistant', 'Dogs are great!')"
        )
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content) VALUES (3, 100, 'user', 'I am a developer.')"
        )
        # Bob's messages
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content) VALUES (4, 200, 'user', 'I like cats.')"
        )
        conn.commit()

    return database


def test_parse_args_reads_cli_arguments():
    """Test that CLI arguments are parsed correctly."""
    args = parse_args([
        "--user-email", "alice@example.com",
        "--ai-companion-id", "10",
        "--limit", "5",
        "--dry-run",
        "--fail-fast",
    ])
    assert args.user_email == "alice@example.com"
    assert args.ai_companion_id == 10
    assert args.limit == 5
    assert args.dry_run is True
    assert args.fail_fast is True


def test_parse_args_defaults():
    """Test that defaults are correct when no arguments given."""
    args = parse_args([])
    assert args.user_email is None
    assert args.ai_companion_id is None
    assert args.limit is None
    assert args.dry_run is False
    assert args.fail_fast is False


def test_scan_messages_returns_only_user_messages(tmp_database):
    """Test that only role='user' messages are returned."""
    messages = scan_messages(tmp_database)
    assert len(messages) == 3
    contents = [m["content"] for m in messages]
    assert "Dogs are great!" not in contents  # assistant message excluded
    assert "I love dogs." in contents
    assert "I am a developer." in contents
    assert "I like cats." in contents


def test_scan_messages_filter_by_user_id(tmp_database):
    """Test filtering by user_id."""
    messages = scan_messages(tmp_database, user_id=1)
    assert len(messages) == 2
    assert all(m["user_id"] == 1 for m in messages)


def test_scan_messages_filter_by_companion_id(tmp_database):
    """Test filtering by ai_companion_id."""
    messages = scan_messages(tmp_database, ai_companion_id=20)
    assert len(messages) == 1
    assert messages[0]["ai_companion_id"] == 20
    assert messages[0]["content"] == "I like cats."


def test_scan_messages_limit(tmp_database):
    """Test that --limit caps the result count."""
    messages = scan_messages(tmp_database, limit=2)
    assert len(messages) == 2


def test_load_processed_message_ids_empty(tmp_database):
    """Test that no processed IDs are returned when memories table is empty."""
    ids = load_processed_message_ids(tmp_database)
    assert ids == set()


def test_load_processed_message_ids_populated(tmp_database):
    """Test that processed message IDs are returned."""
    with tmp_database.connection() as conn:
        conn.execute(
            "INSERT INTO memories (user_id, ai_companion_id, source_message_id, memory_type, "
            "canonical_key, content, importance, confidence) "
            "VALUES (1, 10, 1, 'fact', 'likes_dogs', 'Likes dogs', 3, 0.9)"
        )
        conn.commit()

    ids = load_processed_message_ids(tmp_database)
    assert ids == {1}


@pytest.mark.anyio
async def test_dry_run_does_not_write_memories(tmp_database, monkeypatch):
    """Test that dry-run mode does not persist any memories."""
    args = argparse.Namespace(
        user_email=None, ai_companion_id=None, limit=None,
        dry_run=True, fail_fast=False,
    )

    # Patch settings and database
    mock_settings = mock.Mock()
    mock_settings.storage.sqlite_path = tmp_database.database_path
    mock_settings.chat = mock.Mock()
    mock_settings.inference = mock.Mock()
    mock_settings.secrets = mock.Mock()
    mock_settings.memory.extraction_enabled = True
    mock_settings.memory.raw_content_logging_enabled = False
    mock_settings.memory.embedding_model_name = "all-MiniLM-L6-v2"
    mock_settings.memory.qdrant_url = "http://localhost:6333"
    mock_settings.memory.qdrant_collection = "mistria_memories"
    mock_settings.memory.enabled = True
    monkeypatch.setattr("scripts.backfill_memory.settings", mock_settings)

    # Mock the runtime
    mock_runtime = mock.AsyncMock()
    mock_runtime.generate_text.return_value = '{"memories": []}'
    monkeypatch.setattr(
        "scripts.backfill_memory.InferenceRuntimeFactory.create",
        mock.Mock(return_value=mock_runtime),
    )

    # Mock extraction_service.extract_memories to return empty
    monkeypatch.setattr(
        "scripts.backfill_memory.MemoryExtractionService",
        lambda runtime: mock.Mock(
            extract_memories=mock.AsyncMock(return_value=[]),
        ),
    )

    stats = await run_backfill(args)

    assert stats.scanned == 3
    assert stats.stored == 0

    # Verify no memories were written
    with tmp_database.connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    assert count == 0


@pytest.mark.anyio
async def test_skip_already_processed_messages(tmp_database, monkeypatch):
    """Test that messages already linked to memories are skipped."""
    # Pre-insert a memory for message_id=1
    with tmp_database.connection() as conn:
        conn.execute(
            "INSERT INTO memories (user_id, ai_companion_id, source_message_id, memory_type, "
            "canonical_key, content, importance, confidence) "
            "VALUES (1, 10, 1, 'fact', 'likes_dogs', 'Likes dogs', 3, 0.9)"
        )
        conn.commit()

    args = argparse.Namespace(
        user_email=None, ai_companion_id=None, limit=None,
        dry_run=True, fail_fast=False,
    )

    mock_settings = mock.Mock()
    mock_settings.storage.sqlite_path = tmp_database.database_path
    mock_settings.chat = mock.Mock()
    mock_settings.inference = mock.Mock()
    mock_settings.secrets = mock.Mock()
    mock_settings.memory.extraction_enabled = True
    mock_settings.memory.raw_content_logging_enabled = False
    monkeypatch.setattr("scripts.backfill_memory.settings", mock_settings)

    mock_runtime = mock.AsyncMock()
    monkeypatch.setattr(
        "scripts.backfill_memory.InferenceRuntimeFactory.create",
        mock.Mock(return_value=mock_runtime),
    )

    mock_extract = mock.AsyncMock(return_value=[])
    monkeypatch.setattr(
        "scripts.backfill_memory.MemoryExtractionService",
        lambda runtime: mock.Mock(extract_memories=mock_extract),
    )

    stats = await run_backfill(args)

    assert stats.scanned == 3
    assert stats.skipped == 1  # message_id=1 was skipped
    # extract_memories should only be called for the 2 non-skipped messages
    assert mock_extract.await_count == 2


@pytest.mark.anyio
async def test_fail_fast_aborts_on_first_failure(tmp_database, monkeypatch):
    """Test that --fail-fast aborts the run on first extraction error."""
    args = argparse.Namespace(
        user_email=None, ai_companion_id=None, limit=None,
        dry_run=True, fail_fast=True,
    )

    mock_settings = mock.Mock()
    mock_settings.storage.sqlite_path = tmp_database.database_path
    mock_settings.chat = mock.Mock()
    mock_settings.inference = mock.Mock()
    mock_settings.secrets = mock.Mock()
    mock_settings.memory.extraction_enabled = True
    mock_settings.memory.raw_content_logging_enabled = False
    monkeypatch.setattr("scripts.backfill_memory.settings", mock_settings)

    mock_runtime = mock.AsyncMock()
    monkeypatch.setattr(
        "scripts.backfill_memory.InferenceRuntimeFactory.create",
        mock.Mock(return_value=mock_runtime),
    )

    # First call fails
    mock_extract = mock.AsyncMock(side_effect=RuntimeError("LLM down"))
    monkeypatch.setattr(
        "scripts.backfill_memory.MemoryExtractionService",
        lambda runtime: mock.Mock(extract_memories=mock_extract),
    )

    with pytest.raises(RuntimeError, match="LLM down"):
        await run_backfill(args)


@pytest.mark.anyio
async def test_failure_without_fail_fast_continues(tmp_database, monkeypatch):
    """Test that without --fail-fast, failures are counted but processing continues."""
    args = argparse.Namespace(
        user_email=None, ai_companion_id=None, limit=None,
        dry_run=True, fail_fast=False,
    )

    mock_settings = mock.Mock()
    mock_settings.storage.sqlite_path = tmp_database.database_path
    mock_settings.chat = mock.Mock()
    mock_settings.inference = mock.Mock()
    mock_settings.secrets = mock.Mock()
    mock_settings.memory.extraction_enabled = True
    mock_settings.memory.raw_content_logging_enabled = False
    monkeypatch.setattr("scripts.backfill_memory.settings", mock_settings)

    mock_runtime = mock.AsyncMock()
    monkeypatch.setattr(
        "scripts.backfill_memory.InferenceRuntimeFactory.create",
        mock.Mock(return_value=mock_runtime),
    )

    # All calls fail
    mock_extract = mock.AsyncMock(side_effect=RuntimeError("LLM down"))
    monkeypatch.setattr(
        "scripts.backfill_memory.MemoryExtractionService",
        lambda runtime: mock.Mock(extract_memories=mock_extract),
    )

    stats = await run_backfill(args)

    assert stats.scanned == 3
    assert stats.failed == 3
    assert stats.extracted == 0


@pytest.mark.anyio
async def test_storage_failure_increments_stats(tmp_database, monkeypatch):
    """Test that if storage fails (raises), stats.failed is incremented."""
    args = argparse.Namespace(
        user_email=None, ai_companion_id=None, limit=None,
        dry_run=False, fail_fast=False,
    )

    mock_settings = mock.Mock()
    mock_settings.storage.sqlite_path = tmp_database.database_path
    mock_settings.memory.extraction_enabled = True
    mock_settings.memory.raw_content_logging_enabled = False
    mock_settings.memory.embedding_model_name = "test"
    mock_settings.memory.qdrant_url = "http://localhost"
    mock_settings.memory.qdrant_collection = "test"
    mock_settings.memory.enabled = True
    monkeypatch.setattr("scripts.backfill_memory.settings", mock_settings)

    mock_runtime = mock.AsyncMock()
    monkeypatch.setattr(
        "scripts.backfill_memory.InferenceRuntimeFactory.create",
        mock.Mock(return_value=mock_runtime),
    )

    # Extraction succeeds
    candidate = mock.Mock(spec=MemoryExtraction, canonical_key="test")
    mock_extract = mock.AsyncMock(return_value=[candidate])
    monkeypatch.setattr(
        "scripts.backfill_memory.MemoryExtractionService",
        lambda runtime: mock.Mock(extract_memories=mock_extract),
    )

    # Storage fails
    mock_store = mock.AsyncMock(side_effect=RuntimeError("Storage failed"))
    monkeypatch.setattr(
        "scripts.backfill_memory.MemoryService",
        lambda **kwargs: mock.Mock(store_memories=mock_store),
    )
    
    # Mock vector store bootstrap
    monkeypatch.setattr(
        "scripts.backfill_memory.QdrantVectorStore",
        mock.Mock(),
    )
    monkeypatch.setattr(
        "scripts.backfill_memory.LocalEmbeddingProvider",
        mock.Mock(return_value=mock.Mock(get_dimension=mock.Mock(return_value=128))),
    )

    stats = await run_backfill(args)

    assert stats.scanned == 3
    assert stats.failed == 3  # All 3 messages failed at the storage step
    assert stats.extracted == 3
    assert stats.stored == 0


@pytest.mark.anyio
async def test_user_email_filter(tmp_database, monkeypatch):
    """Test that --user-email filters correctly."""
    args = argparse.Namespace(
        user_email="alice@example.com", ai_companion_id=None, limit=None,
        dry_run=True, fail_fast=False,
    )

    mock_settings = mock.Mock()
    mock_settings.storage.sqlite_path = tmp_database.database_path
    mock_settings.chat = mock.Mock()
    mock_settings.inference = mock.Mock()
    mock_settings.secrets = mock.Mock()
    mock_settings.memory.extraction_enabled = True
    mock_settings.memory.raw_content_logging_enabled = False
    monkeypatch.setattr("scripts.backfill_memory.settings", mock_settings)

    mock_runtime = mock.AsyncMock()
    monkeypatch.setattr(
        "scripts.backfill_memory.InferenceRuntimeFactory.create",
        mock.Mock(return_value=mock_runtime),
    )

    mock_extract = mock.AsyncMock(return_value=[])
    monkeypatch.setattr(
        "scripts.backfill_memory.MemoryExtractionService",
        lambda runtime: mock.Mock(extract_memories=mock_extract),
    )

    stats = await run_backfill(args)

    # Only Alice's 2 user messages should be processed
    assert stats.scanned == 2
    assert mock_extract.await_count == 2
