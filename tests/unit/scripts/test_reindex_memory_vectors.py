"""Tests for the memory reindexing script."""

import pytest
from unittest.mock import MagicMock, patch
from scripts.reindex_memory_vectors import main


@pytest.fixture
def mock_components():
    """Mock all external dependencies for the reindex script."""
    with patch("scripts.reindex_memory_vectors.SQLiteDatabase") as mock_db, \
         patch("scripts.reindex_memory_vectors.SQLiteUserRepository") as mock_user_repo, \
         patch("scripts.reindex_memory_vectors.SQLiteMemoryRepository") as mock_memory_repo, \
         patch("scripts.reindex_memory_vectors.QdrantVectorStore") as mock_vector_store, \
         patch("scripts.reindex_memory_vectors.LocalEmbeddingProvider") as mock_embed, \
         patch("scripts.reindex_memory_vectors.settings") as mock_settings:
        
        mock_settings.memory.enabled = True
        mock_settings.memory.qdrant_url = "http://localhost:6333"
        mock_settings.memory.qdrant_collection = "test_collection"
        mock_settings.memory.embedding_model_name = "test_model"
        
        yield {
            "db": mock_db,
            "user_repo": mock_user_repo.return_value,
            "memory_repo": mock_memory_repo.return_value,
            "vector_store": mock_vector_store.return_value,
            "embed": mock_embed.return_value,
            "settings": mock_settings
        }


def test_reindex_dry_run(mock_components):
    """Verify dry-run performs no writes."""
    components = mock_components
    mem = MagicMock(id=1, user_id=1, ai_companion_id=1, memory_type="fact", canonical_key="key1", content="content1", status="active")
    components["memory_repo"].list_all_active.return_value = [mem]
    
    exit_code = main(["--dry-run"])
    
    assert exit_code == 0
    components["vector_store"].upsert_memory.assert_not_called()
    components["vector_store"].bootstrap_collection.assert_not_called()
    components["vector_store"].recreate_collection.assert_not_called()
    components["embed"].embed_text.assert_not_called()


def test_reindex_recreate(mock_components):
    """Verify --recreate triggers collection recreation."""
    components = mock_components
    components["memory_repo"].list_all_active.return_value = []
    components["embed"].get_dimension.return_value = 384
    
    exit_code = main(["--recreate"])
    
    assert exit_code == 0
    components["vector_store"].recreate_collection.assert_called_with(384)
    components["vector_store"].bootstrap_collection.assert_not_called()


def test_reindex_bootstrap_default(mock_components):
    """Verify default run triggers bootstrap (not recreate)."""
    components = mock_components
    components["memory_repo"].list_all_active.return_value = []
    components["embed"].get_dimension.return_value = 384
    
    exit_code = main([])
    
    assert exit_code == 0
    components["vector_store"].bootstrap_collection.assert_called_with(384)
    components["vector_store"].recreate_collection.assert_not_called()


def test_reindex_with_filters(mock_components):
    """Verify filters are passed correctly to the repository."""
    components = mock_components
    components["user_repo"].find_by_email.return_value = MagicMock(id=42)
    components["memory_repo"].list_all_active.return_value = []
    
    exit_code = main([
        "--user-email", "test@example.com",
        "--ai-companion-id", "7",
        "--memory-type", "preference",
        "--limit", "10"
    ])
    
    assert exit_code == 0
    components["memory_repo"].list_all_active.assert_called_with(
        user_id=42,
        ai_companion_id=7,
        memory_type="preference",
        limit=10
    )


def test_reindex_success_path(mock_components):
    """Verify memories are embedded and upserted correctly."""
    components = mock_components
    mem1 = MagicMock(id=1, user_id=1, ai_companion_id=1, memory_type="fact", canonical_key="key1", content="content1", status="active")
    components["memory_repo"].list_all_active.return_value = [mem1]
    components["embed"].embed_text.return_value = [0.1, 0.2]
    
    exit_code = main([])
    
    assert exit_code == 0
    components["embed"].embed_text.assert_called_with("content1")
    components["vector_store"].upsert_memory.assert_called_once_with(
        memory_id=1,
        user_id=1,
        ai_companion_id=1,
        memory_type="fact",
        canonical_key="key1",
        status="active",
        vector=[0.1, 0.2]
    )


def test_reindex_error_handling(mock_components):
    """Verify failed records do not abort the entire run."""
    components = mock_components
    mem1 = MagicMock(id=1, user_id=1, ai_companion_id=1, memory_type="fact", canonical_key="key1", content="c1", status="active")
    mem2 = MagicMock(id=2, user_id=1, ai_companion_id=1, memory_type="fact", canonical_key="key2", content="c2", status="active")
    components["memory_repo"].list_all_active.return_value = [mem1, mem2]
    
    # Fail the first one
    components["embed"].embed_text.side_effect = [Exception("Embedding failed"), [0.1, 0.2]]
    
    exit_code = main([])
    
    # Returns 1 because there was a failure
    assert exit_code == 1
    # But it should have attempted the second one
    assert components["embed"].embed_text.call_count == 2
    assert components["vector_store"].upsert_memory.call_count == 1


def test_reindex_disabled_guard(mock_components):
    """Verify script aborts if memory system is disabled in settings."""
    components = mock_components
    components["settings"].memory.enabled = False
    
    exit_code = main([])
    
    assert exit_code == 1
    components["memory_repo"].list_all_active.assert_not_called()


def test_reindex_user_not_found(mock_components):
    """Verify script aborts if user filter provides invalid email."""
    components = mock_components
    components["user_repo"].find_by_email.return_value = None
    
    exit_code = main(["--user-email", "nonexistent@example.com"])
    
    assert exit_code == 1
    components["memory_repo"].list_all_active.assert_not_called()
