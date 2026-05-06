"""Tests for the Qdrant vector store adapter."""

from pathlib import Path
import sys
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.memory.vector_store import NoOpVectorStore, QdrantVectorStore


def test_noop_vector_store_does_nothing():
    """Verify NoOpVectorStore methods execute without error and return empty."""
    store = NoOpVectorStore()
    store.bootstrap_collection(128)
    store.upsert_memory(1, 1, 1, "fact", "key", "active", [0.1] * 128)
    store.delete_memory(1)
    
    results = store.search(1, 1, [0.1] * 128, 5)
    assert len(results) == 0


def test_qdrant_disabled_acts_like_noop():
    """Verify QdrantVectorStore acts like a No-Op when enabled=False."""
    store = QdrantVectorStore(url="http://fake", collection_name="test", enabled=False)
    assert store._get_client() is None
    
    # Should not raise any errors
    store.bootstrap_collection(128)
    store.upsert_memory(1, 1, 1, "fact", "key", "active", [0.1] * 128)
    store.delete_memory(1)
    
    results = store.search(1, 1, [0.1] * 128, 5)
    assert len(results) == 0


@mock.patch("src.memory.vector_store.logger")
def test_qdrant_client_import_failure_disables_store(mock_logger):
    """Test that missing qdrant_client safely disables the store."""
    store = QdrantVectorStore(url="http://fake", collection_name="test", enabled=True)
    
    # Simulate ImportError
    with mock.patch.dict("sys.modules", {"qdrant_client": None}):
        client = store._get_client()
        assert client is None
        assert store.enabled is False
        mock_logger.error.assert_called_with("qdrant-client is not installed. Vector search will be disabled.")


def test_qdrant_upsert_sends_correct_payload():
    """Test that upsert_memory constructs the payload correctly."""
    store = QdrantVectorStore(url="http://fake", collection_name="test", enabled=True)
    
    mock_client = mock.Mock()
    store._client = mock_client
    
    # Needs the models to be importable
    from qdrant_client.models import PointStruct
    
    with mock.patch.dict("sys.modules", {"qdrant_client": mock.Mock(models=mock.Mock(PointStruct=PointStruct))}):
        store.upsert_memory(
            memory_id=42,
            user_id=1,
            ai_companion_id=2,
            memory_type="preference",
            canonical_key="likes_dogs",
            status="active",
            vector=[0.1, 0.2, 0.3]
        )
        
        mock_client.upsert.assert_called_once()
        kwargs = mock_client.upsert.call_args.kwargs
        assert kwargs["collection_name"] == "test"
        
        points = kwargs["points"]
        assert len(points) == 1
        point = points[0]
        assert point.id == 42
        assert point.vector == [0.1, 0.2, 0.3]
        assert point.payload["user_id"] == 1
        assert point.payload["ai_companion_id"] == 2
        assert point.payload["status"] == "active"
        assert point.payload["memory_type"] == "preference"


def test_qdrant_search_builds_strict_filters():
    """Test that search strictly filters by user, companion, and active status."""
    store = QdrantVectorStore(url="http://fake", collection_name="test", enabled=True)
    
    mock_client = mock.Mock()
    
    # Create mock hits
    mock_hit = mock.Mock()
    mock_hit.score = 0.95
    mock_hit.payload = {"memory_id": 42}
    mock_client.search.return_value = [mock_hit]
    
    store._client = mock_client
    
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    
    with mock.patch.dict("sys.modules", {"qdrant_client": mock.Mock()}):
        results = store.search(user_id=5, ai_companion_id=10, query_vector=[0.1], limit=3)
        
        assert len(results) == 1
        assert results[0].memory_id == 42
        assert results[0].score == 0.95
        
        mock_client.search.assert_called_once()
        kwargs = mock_client.search.call_args.kwargs
        assert kwargs["collection_name"] == "test"
        assert kwargs["limit"] == 3
        
        query_filter = kwargs["query_filter"]
        # Verify the 3 must conditions
        assert len(query_filter.must) == 3
        conditions = query_filter.must
        
        # Verify condition contents (they are FieldConditions)
        # user_id
        assert any(c.key == "user_id" and c.match.value == 5 for c in conditions)
        # ai_companion_id
        assert any(c.key == "ai_companion_id" and c.match.value == 10 for c in conditions)
        # status
        assert any(c.key == "status" and c.match.value == "active" for c in conditions)


def test_qdrant_bootstrap_idempotent():
    """Test that bootstrap_collection handles existing collections."""
    store = QdrantVectorStore(url="http://fake", collection_name="test", enabled=True)
    
    mock_client = mock.Mock()
    # get_collection returns without error means it exists
    mock_client.get_collection.return_value = True
    store._client = mock_client
    
    with mock.patch.dict("sys.modules", {"qdrant_client": mock.Mock()}):
        store.bootstrap_collection(128)
        
        mock_client.get_collection.assert_called_once_with(collection_name="test")
        # create_collection should NOT be called
        mock_client.create_collection.assert_not_called()
