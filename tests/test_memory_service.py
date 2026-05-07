"""Unit tests for the memory service."""

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
        extracted_memories=[candidate]
    )
    
    # Result should still include the ID because it was saved to SQLite
    assert ids == [1]
    mock_repo.create_memory.assert_called_once()
