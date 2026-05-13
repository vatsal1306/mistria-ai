"""Unit tests for the memory service."""

from datetime import datetime, timezone
from unittest import mock
import pytest

from src.config import Memory
from src.memory.embeddings import BaseEmbeddingProvider
from src.memory.schemas import MemoryExtraction
from src.memory.service import MemoryService
from src.memory.vector_store import BaseVectorStore
from src.storage.memory_repository import MemoryRepository
from src.storage.models import MemoryRecord


@pytest.fixture
def mock_repo():
    return mock.Mock(spec=MemoryRepository)


@pytest.fixture
def mock_vector_store():
    return mock.Mock(spec=BaseVectorStore)


@pytest.fixture
def mock_embeddings():
    provider = mock.Mock(spec=BaseEmbeddingProvider)
    provider.embed_text.return_value = [0.1] * 384
    return provider


@pytest.fixture
def memory_service(mock_repo, mock_vector_store, mock_embeddings):
    config = Memory(enabled=True)
    return MemoryService(
        config=config,
        repository=mock_repo,
        vector_store=mock_vector_store,
        embedding_provider=mock_embeddings,
    )


@pytest.mark.anyio
async def test_store_memories_basic_storage(memory_service, mock_repo, mock_vector_store):
    """Test storing a single memory with no existing conflicts."""
    candidate = MemoryExtraction(
        should_remember=True,
        memory_type="fact",
        canonical_key="user_job",
        content="User is a developer.",
        importance=3,
        confidence=0.9,
        reason="Explicitly stated."
    )
    
    # Mock SQLite creation
    mock_record = mock.Mock(spec=MemoryRecord)
    mock_record.id = 123
    mock_repo.find_active_by_canonical_key.return_value = None
    mock_repo.create_memory.return_value = mock_record
    
    ids = await memory_service.store_memories(
        user_id=1,
        ai_companion_id=2,
        conversation_id=10,
        message_id=202,
        extracted_memories=[candidate]
    )
    
    assert ids == [123]
    mock_repo.create_memory.assert_called_once()
    mock_repo.find_active_by_canonical_key.assert_called_with(
        user_id=1, ai_companion_id=2, canonical_key="user_job"
    )
    mock_vector_store.upsert_memory.assert_called_once()
    mock_vector_store.delete_memory.assert_not_called()


@pytest.mark.anyio
async def test_store_memories_conflict_resolution(memory_service, mock_repo, mock_vector_store):
    """Test that a newer memory with the same key supersedes the old one."""
    candidate = MemoryExtraction(
        should_remember=True,
        memory_type="preference",
        canonical_key="favorite_color",
        content="User likes blue.",
        importance=2,
        confidence=0.9,
        reason="Updated preference."
    )
    
    # Mock existing memory
    old_record = mock.Mock(spec=MemoryRecord)
    old_record.id = 50
    mock_repo.find_active_by_canonical_key.return_value = old_record
    
    # Mock new memory
    new_record = mock.Mock(spec=MemoryRecord)
    new_record.id = 100
    mock_repo.create_memory.return_value = new_record
    
    await memory_service.store_memories(
        user_id=1,
        ai_companion_id=2,
        conversation_id=10,
        message_id=202,
        extracted_memories=[candidate]
    )
    
    # Verify superseding in SQLite
    mock_repo.supersede.assert_called_with(memory_id=50, superseded_by_id=100)
    
    # Verify vector store synchronization
    mock_vector_store.delete_memory.assert_called_with(memory_id=50)
    mock_vector_store.upsert_memory.assert_called_with(
        memory_id=100,
        user_id=1,
        ai_companion_id=2,
        memory_type="preference",
        canonical_key="favorite_color",
        status="active",
        vector=mock.ANY
    )


@pytest.mark.anyio
async def test_store_memories_isolation(memory_service, mock_repo):
    """Test that memories are isolated by ai_companion_id."""
    candidate = MemoryExtraction(
        should_remember=True,
        memory_type="fact",
        canonical_key="user_name",
        content="John",
        importance=5,
        confidence=1.0,
        reason="Intro"
    )
    
    mock_repo.find_active_by_canonical_key.return_value = None
    mock_repo.create_memory.return_value = mock.Mock(id=99)
    
    await memory_service.store_memories(
        user_id=1,
        ai_companion_id=2, # Companion 2
        conversation_id=10,
        message_id=202,
        extracted_memories=[candidate]
    )
    
    # Check that search was scoped to Companion 2
    mock_repo.find_active_by_canonical_key.assert_called_with(
        user_id=1, ai_companion_id=2, canonical_key="user_name"
    )


@pytest.mark.anyio
async def test_store_memories_skips_ignored_candidates(memory_service, mock_repo):
    """Test that candidates with should_remember=False are skipped."""
    candidate = MemoryExtraction(
        should_remember=False, # Ignore
        memory_type="emotional",
        canonical_key="random",
        content="Noise",
        importance=1,
        confidence=0.1,
        reason="Small talk."
    )
    
    await memory_service.store_memories(
        user_id=1,
        ai_companion_id=2,
        conversation_id=10,
        message_id=202,
        extracted_memories=[candidate]
    )
    
    mock_repo.create_memory.assert_not_called()


@pytest.mark.anyio
async def test_store_memories_resilience_to_vector_failure(memory_service, mock_repo, mock_vector_store):
    """Test that a vector store failure does not prevent SQLite storage."""
    candidate = MemoryExtraction(
        should_remember=True,
        memory_type="fact",
        canonical_key="test",
        content="Test content",
        importance=1,
        confidence=1.0,
        reason="Test"
    )
    
    mock_repo.create_memory.return_value = mock.Mock(id=1)
    # Simulate vector store crash
    mock_vector_store.upsert_memory.side_effect = Exception("Vector store down")
    
    ids = await memory_service.store_memories(
        user_id=1,
        ai_companion_id=2,
        conversation_id=10,
        message_id=202,
        extracted_memories=[candidate]
    )
    
    # Result should still include the ID because it was saved to SQLite
    assert ids == [1]
    mock_repo.create_memory.assert_called_once()


@pytest.mark.anyio
async def test_store_memories_strict_mode_raises_on_vector_failure(memory_service, mock_repo, mock_vector_store):
    """Test that if raise_on_error is True, a vector store Exception is propagated."""
    candidate = MemoryExtraction(
        should_remember=True, memory_type="fact", canonical_key="user_job",
        content="User is a developer.", importance=3, confidence=0.9, reason="Stated."
    )
    mock_repo.find_active_by_canonical_key.return_value = None
    mock_repo.create_memory.return_value = mock.Mock(id=10)
    
    # Mock vector store failure
    mock_vector_store.upsert_memory.side_effect = RuntimeError("Qdrant down")
    
    with pytest.raises(RuntimeError, match="Qdrant down"):
        await memory_service.store_memories(
            user_id=1, ai_companion_id=2, conversation_id=10, message_id=202,
            extracted_memories=[candidate], raise_on_error=True
        )


@pytest.mark.anyio
async def test_retrieve_memories_hybrid_merge(memory_service, mock_repo, mock_vector_store):
    """Test that results from semantic and keyword search are merged and deduplicated."""
    from src.memory.vector_store import VectorStoreResult

    # 1. Mock Qdrant result (ID 1)
    mock_vector_store.search.return_value = [VectorStoreResult(memory_id=1, score=0.8)]
    
    # 2. Mock SQLite keyword result (IDs 1 and 2)
    record1 = mock.Mock(
        spec=MemoryRecord, id=1, user_id=1, ai_companion_id=2, status="active", 
        importance=3, confidence=1.0, updated_at=datetime.now(timezone.utc).isoformat(),
        memory_type="fact", content="Content 1", canonical_key="key1"
    )
    record2 = mock.Mock(
        spec=MemoryRecord, id=2, user_id=1, ai_companion_id=2, status="active", 
        importance=3, confidence=1.0, updated_at=datetime.now(timezone.utc).isoformat(),
        memory_type="fact", content="Content 2", canonical_key="key2"
    )
    mock_repo.keyword_search.return_value = [record1, record2]
    
    # 3. Mock find_by_id for record 1 (though it's already in keyword hits)
    mock_repo.find_by_id.side_effect = lambda mid: record1 if mid == 1 else record2

    results = await memory_service.retrieve_memories(user_id=1, ai_companion_id=2, query="test")
    
    # Verify merging (IDs 1 and 2)
    assert len(results) == 2
    ids = [r.memory_id for r in results]
    assert 1 in ids
    assert 2 in ids
    # ID 1 should be hybrid
    res1 = next(r for r in results if r.memory_id == 1)
    assert res1.source == "hybrid"
    # ID 2 should be keyword
    res2 = next(r for r in results if r.memory_id == 2)
    assert res2.source == "keyword"


@pytest.mark.anyio
async def test_retrieve_memories_thresholding(memory_service, mock_repo, mock_vector_store):
    """Test that results below the min_score threshold are filtered out."""
    from src.memory.vector_store import VectorStoreResult
    
    # Low score semantic result
    mock_vector_store.search.return_value = [VectorStoreResult(memory_id=99, score=0.1)]
    mock_repo.keyword_search.return_value = []
    
    low_record = mock.Mock(
        spec=MemoryRecord, id=99, user_id=1, ai_companion_id=2, status="active", 
        importance=1, confidence=0.5, updated_at="2020-01-01T00:00:00Z",
        memory_type="fact", content="Low", canonical_key="low"
    )
    mock_repo.find_by_id.return_value = low_record
    
    results = await memory_service.retrieve_memories(user_id=1, ai_companion_id=2, query="test")
    
    assert len(results) == 0


@pytest.mark.anyio
async def test_retrieve_memories_isolation(memory_service, mock_repo, mock_vector_store):
    """Test that memories from other users/companions are never returned."""
    from src.memory.vector_store import VectorStoreResult
    
    # Vector store accidentally returns another user's memory
    mock_vector_store.search.return_value = [VectorStoreResult(memory_id=500, score=0.9)]
    mock_repo.keyword_search.return_value = []
    
    wrong_record = mock.Mock(
        spec=MemoryRecord, id=500, user_id=999, ai_companion_id=888, status="active", 
        importance=5, confidence=1.0, updated_at=datetime.now(timezone.utc).isoformat(),
        memory_type="fact", content="Wrong", canonical_key="wrong"
    )
    mock_repo.find_by_id.return_value = wrong_record
    
    results = await memory_service.retrieve_memories(user_id=1, ai_companion_id=2, query="test")
    
    assert len(results) == 0


@pytest.mark.anyio
async def test_retrieve_memories_vector_failure_fallback(memory_service, mock_repo, mock_vector_store):
    """Test that keyword search works even if semantic search fails."""
    mock_vector_store.search.side_effect = Exception("Vector store down")
    
    record = mock.Mock(
        spec=MemoryRecord, id=10, user_id=1, ai_companion_id=2, status="active", 
        importance=3, confidence=1.0, updated_at=datetime.now(timezone.utc).isoformat(),
        memory_type="fact", content="Fallback", canonical_key="fallback"
    )
    mock_repo.keyword_search.return_value = [record]

    
    results = await memory_service.retrieve_memories(user_id=1, ai_companion_id=2, query="test")
    
    assert len(results) == 1
    assert results[0].memory_id == 10
    assert results[0].source == "keyword"


@pytest.mark.anyio
async def test_store_memories_logs_raw_content_when_enabled(
    mock_repo, mock_vector_store, mock_embeddings, caplog,
):
    """Test that raw memory content appears in logs when flag is enabled."""
    config = Memory(enabled=True, raw_content_logging_enabled=True)
    service = MemoryService(
        config=config, repository=mock_repo,
        vector_store=mock_vector_store, embedding_provider=mock_embeddings,
    )
    candidate = MemoryExtraction(
        should_remember=True, memory_type="fact", canonical_key="user_job",
        content="User is a developer.", importance=3, confidence=0.9,
        reason="Stated.",
    )
    mock_repo.find_active_by_canonical_key.return_value = None
    mock_repo.create_memory.return_value = mock.Mock(id=10)

    import logging
    mistria_logger = logging.getLogger("mistria")
    mistria_logger.propagate = True
    try:
        with caplog.at_level(logging.DEBUG, logger="mistria"):
            await service.store_memories(
                user_id=1, ai_companion_id=2, conversation_id=10,
                message_id=202, extracted_memories=[candidate],
            )

        assert any("User is a developer." in rec.message for rec in caplog.records)
    finally:
        mistria_logger.propagate = False


@pytest.mark.anyio
async def test_store_memories_suppresses_raw_content_when_disabled(
    mock_repo, mock_vector_store, mock_embeddings, caplog,
):
    """Test that raw memory content does NOT appear in logs when flag is disabled."""
    config = Memory(enabled=True, raw_content_logging_enabled=False)
    service = MemoryService(
        config=config, repository=mock_repo,
        vector_store=mock_vector_store, embedding_provider=mock_embeddings,
    )
    candidate = MemoryExtraction(
        should_remember=True, memory_type="fact", canonical_key="user_job",
        content="User is a developer.", importance=3, confidence=0.9,
        reason="Stated.",
    )
    mock_repo.find_active_by_canonical_key.return_value = None
    mock_repo.create_memory.return_value = mock.Mock(id=10)

    import logging
    mistria_logger = logging.getLogger("mistria")
    mistria_logger.propagate = True
    try:
        with caplog.at_level(logging.DEBUG, logger="mistria"):
            await service.store_memories(
                user_id=1, ai_companion_id=2, conversation_id=10,
                message_id=202, extracted_memories=[candidate],
            )

        assert not any("User is a developer." in rec.message for rec in caplog.records)
    finally:
        mistria_logger.propagate = False


@pytest.mark.anyio
async def test_retrieve_memories_logs_raw_content_when_enabled(
    mock_repo, mock_vector_store, mock_embeddings, caplog,
):
    """Test that retrieved memory content appears in logs when flag is enabled."""
    config = Memory(enabled=True, raw_content_logging_enabled=True)
    service = MemoryService(
        config=config, repository=mock_repo,
        vector_store=mock_vector_store, embedding_provider=mock_embeddings,
    )
    record = mock.Mock(
        spec=MemoryRecord, id=10, user_id=1, ai_companion_id=2, status="active",
        importance=3, confidence=1.0, updated_at=datetime.now(timezone.utc).isoformat(),
        memory_type="fact", content="Secret info", canonical_key="secret",
    )
    mock_vector_store.search.return_value = []
    mock_repo.keyword_search.return_value = [record]

    import logging
    mistria_logger = logging.getLogger("mistria")
    mistria_logger.propagate = True
    try:
        with caplog.at_level(logging.DEBUG, logger="mistria"):
            await service.retrieve_memories(user_id=1, ai_companion_id=2, query="test")

        assert any("Secret info" in rec.message for rec in caplog.records)
    finally:
        mistria_logger.propagate = False


@pytest.mark.anyio
async def test_retrieve_memories_suppresses_raw_content_when_disabled(
    mock_repo, mock_vector_store, mock_embeddings, caplog,
):
    """Test that retrieved memory content does NOT appear in logs when flag is disabled."""
    config = Memory(enabled=True, raw_content_logging_enabled=False)
    service = MemoryService(
        config=config, repository=mock_repo,
        vector_store=mock_vector_store, embedding_provider=mock_embeddings,
    )
    record = mock.Mock(
        spec=MemoryRecord, id=10, user_id=1, ai_companion_id=2, status="active",
        importance=3, confidence=1.0, updated_at=datetime.now(timezone.utc).isoformat(),
        memory_type="fact", content="Secret info", canonical_key="secret",
    )
    mock_vector_store.search.return_value = []
    mock_repo.keyword_search.return_value = [record]

    import logging
    mistria_logger = logging.getLogger("mistria")
    mistria_logger.propagate = True
    try:
        with caplog.at_level(logging.DEBUG, logger="mistria"):
            await service.retrieve_memories(user_id=1, ai_companion_id=2, query="test")

        assert not any("Secret info" in rec.message for rec in caplog.records)
    finally:
        mistria_logger.propagate = False


