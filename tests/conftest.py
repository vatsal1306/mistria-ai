"""Shared pytest fixtures for deterministic local tests."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace

import pytest

from src.config import Memory
from src.storage.database import SQLiteDatabase
from src.storage.models import AICompanionRecord, ConversationRecord, MessageRecord, UserCompanionRecord, UserRecord


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
def sample_user_companion() -> UserCompanionRecord:
    return UserCompanionRecord(
        id=1,
        user_id=1,
        intent_type="alive",
        dominance_mode="ai_leads",
        intensity_level="break_glass",
        silence_response="come_looking",
        secret_desire="both",
        title="Chased and Unapologetic",
        description="A high-intensity dynamic built on pursuit and surrender.",
        created_at="2026-04-24 09:00:00",
        updated_at="2026-04-24 09:00:00",
    )


@pytest.fixture
def sample_ai_companion() -> AICompanionRecord:
    return AICompanionRecord(
        id=2,
        user_id=1,
        title="Luna",
        description="A playful but controlling companion with confident energy.",
        gender="Female",
        style="Anime",
        ethnicity="East Asian",
        eye_color="Green",
        hair_style="Long",
        hair_color="Pink",
        personality="Playful",
        voice="Breathy",
        connection="Passionate Lover",
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
