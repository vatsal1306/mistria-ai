"""Shared pytest fixtures for deterministic local tests."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace

import pytest

from src.config import Memory
from src.storage.database import SQLiteDatabase
from src.storage.models import AICompanionRecord, ConversationRecord, MessageRecord, UserRecord


@pytest.fixture
def anyio_backend() -> str:
    """Run AnyIO-marked tests on asyncio only."""
    return "asyncio"


@pytest.fixture
def sqlite_db(tmp_path) -> Iterator[SQLiteDatabase]:
    """Provide an initialized temporary SQLite database."""
    db = SQLiteDatabase(str(tmp_path / "test.db"))
    db.initialize()
    yield db


@pytest.fixture
def memory_config() -> Memory:
    """Return an enabled memory config with fast, deterministic thresholds."""
    return Memory(enabled=True, retrieval_top_k=5, retrieval_min_score=0.35)


@pytest.fixture
def sample_user() -> UserRecord:
    return UserRecord(
        id=1,
        email="user@example.com",
        name="Vatsal Patel",
        encrypted_password=None,
        created_at="2026-04-24 09:00:00",
    )


@pytest.fixture
def sample_ai_companion() -> AICompanionRecord:
    return AICompanionRecord(
        id=2,
        user_id=1,
        title="Luna",
        description="A playful but controlling companion with confident energy.",
        gender="Female",
        visual_style="Anime",
        companion_ethnicity="East Asian",
        eye_color="Green",
        age=28,
        hair_length="Long",
        hair_style="Long",
        hair_color="Pink",
        companion_personality="Playful",
        companion_profession="Writer",
        body_type="Natural",
        bust="Natural",
        height="Average",
        intention="Passionate Lover",
        created_at="2026-04-24 09:00:00",
        updated_at="2026-04-24 09:00:00",
    )


@pytest.fixture
def sample_conversation() -> ConversationRecord:
    return ConversationRecord(
        id=10,
        user_id=1,
        ai_companion_id=2,
        created_at="2026-04-24 10:00:00",
        updated_at="2026-04-24 10:00:00",
    )


def make_message(
    message_id: int,
    conversation_id: int = 10,
    role: str = "user",
    content: str = "hello",
) -> MessageRecord:
    return MessageRecord(
        id=message_id,
        conversation_id=conversation_id,
        role=role,
        content=content,
        created_at="2026-04-24 10:00:00",
        updated_at="2026-04-24 10:00:00",
    )


def user_with(**overrides) -> UserRecord:
    return replace(
        UserRecord(
            id=1,
            email="user@example.com",
            name="User",
            encrypted_password=None,
            created_at="2026-04-24 09:00:00",
        ),
        **overrides,
    )
