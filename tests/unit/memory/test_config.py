"""Tests for memory configuration defaults and environment variable parsing."""


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
    from src.memory import MemoryService
    assert MemoryService is not None
