"""Tests for memory configuration defaults and environment variable parsing."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_memory_config_defaults():
    """Memory config has safe defaults for local development."""
    from src.config import Memory
    config = Memory()
    assert config.enabled is False
    assert config.extraction_enabled is False
    assert config.qdrant_url == "http://localhost:6333"
    assert config.qdrant_collection == "mistria_memories"
    assert config.embedding_model_name == "all-MiniLM-L6-v2"
    assert config.retrieval_top_k == 5
    assert config.retrieval_min_score == 0.35
    assert config.raw_content_logging_enabled is True


def test_memory_config_in_settings():
    """settings.memory exists and is a Memory instance."""
    from src.config import settings, Memory
    assert hasattr(settings, "memory")
    assert isinstance(settings.memory, Memory)


def test_memory_package_imports_cleanly():
    """The memory package can be imported without errors."""
    from src.memory import MemoryEntry, MemoryScope, MemoryService
    assert MemoryEntry is not None
    assert MemoryScope is not None
    assert MemoryService is not None


def test_memory_scope_is_frozen():
    """MemoryScope is immutable after creation."""
    from src.memory.contracts import MemoryScope
    scope = MemoryScope(user_id=1, ai_companion_id=2)
    assert scope.user_id == 1
    assert scope.ai_companion_id == 2
    with pytest.raises(AttributeError):
        scope.user_id = 99


def test_memory_entry_validation():
    """MemoryEntry enforces field constraints."""
    from src.memory.schemas import MemoryEntry
    entry = MemoryEntry(content="User likes coffee", category="preference", confidence=0.9)
    assert entry.content == "User likes coffee"
    assert entry.category == "preference"
    assert entry.confidence == 0.9

    with pytest.raises(Exception):
        MemoryEntry(content="", category="preference")
