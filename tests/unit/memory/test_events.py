"""Tests for the memory event system."""

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone

from src.memory.events import MemoryEvent, MemoryEventSink, LoggingMemoryEventSink, NoOpMemoryEventSink

def test_memory_event_payload():
    """Verify MemoryEvent can be instantiated and dumped to JSON."""
    event = MemoryEvent(
        event_type="memory_created",
        user_id=1,
        ai_companion_id=2,
        memory_id=100,
        memory_type="preference",
        importance=5,
        confidence=0.95
    )
    
    assert event.event_type == "memory_created"
    assert event.user_id == 1
    assert event.ai_companion_id == 2
    assert event.memory_id == 100
    assert event.importance == 5
    assert isinstance(event.timestamp, datetime)
    
    # Verify JSON serialization
    json_data = event.model_dump_json()
    assert '"event_type":"memory_created"' in json_data
    assert '"user_id":1' in json_data

def test_noop_sink():
    """Verify NoOp sink does not crash."""
    sink = NoOpMemoryEventSink()
    event = MemoryEvent(event_type="memory_created", user_id=1, ai_companion_id=1)
    sink.emit(event)  # Should just do nothing

def test_logging_sink():
    """Verify logging sink writes to the log."""
    import logging
    sink = LoggingMemoryEventSink()
    mock_logger = MagicMock()
    sink.logger = mock_logger
    
    event = MemoryEvent(event_type="memory_created", user_id=1, ai_companion_id=1)
    sink.emit(event)
    
    mock_logger.info.assert_called()
    assert "Memory event:" in mock_logger.info.call_args[0][0]
    assert '"event_type":"memory_created"' in mock_logger.info.call_args[0][1]

def test_memory_service_emits_events(monkeypatch):
    """Verify MemoryService emits events during store and retrieve."""
    from src.memory.service import MemoryService
    from src.memory.schemas import MemoryExtraction
    from unittest.mock import AsyncMock
    
    mock_config = MagicMock()
    mock_config.enabled = True
    mock_repo = MagicMock()
    mock_vector = MagicMock()
    mock_embed = MagicMock()
    mock_sink = MagicMock(spec=MemoryEventSink)
    
    service = MemoryService(mock_config, mock_repo, mock_vector, mock_embed, event_sink=mock_sink)
    
    # 1. Test store_memories (creation)
    mock_repo.find_active_by_canonical_key.return_value = None
    mock_repo.create_memory.return_value = MagicMock(id=123)
    
    candidate = MemoryExtraction(
        should_remember=True,
        memory_type="fact",
        canonical_key="test_key",
        content="test content",
        importance=3,
        confidence=1.0,
        reason="test"
    )
    
    import asyncio
    asyncio.run(service.store_memories(
        user_id=1,
        ai_companion_id=2,
        conversation_id=3,
        message_id=4,
        extracted_memories=[candidate]
    ))
    
    # Check if emit was called
    mock_sink.emit.assert_called()
    call_args = mock_sink.emit.call_args[0][0]
    assert call_args.event_type == "memory_created"
    assert call_args.memory_id == 123
    assert call_args.user_id == 1

    # 2. Test retrieve_memories
    mock_sink.emit.reset_mock()
    mock_embed.embed_text.return_value = [0.1] * 384
    mock_vector.search.return_value = [MagicMock(memory_id=123, score=0.9)]
    mock_repo.find_by_id.return_value = MagicMock(
        id=123, user_id=1, ai_companion_id=2, status="active",
        memory_type="fact", content="content", canonical_key="key",
        importance=4, confidence=0.9, updated_at=datetime.now(timezone.utc).isoformat()
    )
    mock_config.retrieval_top_k = 1
    mock_config.retrieval_min_score = 0.1

    asyncio.run(service.retrieve_memories(
        user_id=1,
        ai_companion_id=2,
        query="test query",
        conversation_id=555
    ))

    mock_sink.emit.assert_called()
    retrieval_call = mock_sink.emit.call_args[0][0]
    assert retrieval_call.event_type == "memory_retrieved"
    assert retrieval_call.importance == 4
    assert retrieval_call.conversation_id == 555
    assert retrieval_call.memory_id == 123

    # 3. Test store_memories (superseding)
    mock_sink.emit.reset_mock()
    mock_repo.find_active_by_canonical_key.return_value = MagicMock(id=99, content="old")
    mock_repo.create_memory.return_value = MagicMock(id=124)
    
    candidate = MemoryExtraction(
        should_remember=True,
        memory_type="preference",
        canonical_key="test_key",
        content="new content",
        importance=5,
        confidence=0.8,
        reason="update"
    )
    
    asyncio.run(service.store_memories(
        user_id=1,
        ai_companion_id=2,
        conversation_id=3,
        message_id=4,
        extracted_memories=[candidate]
    ))
    
    mock_sink.emit.assert_called()
    superseded_call = mock_sink.emit.call_args[0][0]
    assert superseded_call.event_type == "memory_superseded"
    assert superseded_call.memory_id == 124
    assert superseded_call.importance == 5
    assert superseded_call.confidence == 0.8
    assert superseded_call.user_id == 1
    assert superseded_call.ai_companion_id == 2
    assert superseded_call.conversation_id == 3

def test_worker_emits_events():
    """Verify MemoryExtractionWorker emits memory_candidate_extracted."""
    from src.memory.background import MemoryExtractionWorker
    from src.memory.schemas import MemoryExtraction
    from unittest.mock import AsyncMock
    
    mock_extract = AsyncMock()
    mock_memory = MagicMock()
    mock_sink = MagicMock(spec=MemoryEventSink)
    mock_memory.event_sink = mock_sink
    
    worker = MemoryExtractionWorker(mock_extract, mock_memory)
    
    candidate = MemoryExtraction(
        should_remember=True,
        memory_type="fact",
        canonical_key="test_key",
        content="test content",
        importance=3,
        confidence=1.0,
        reason="test"
    )
    mock_extract.extract_memories.return_value = [candidate]
    mock_memory.store_memories = AsyncMock()
    
    import asyncio
    asyncio.run(worker._run(1, 2, 3, 4, "test message", None))
    
    # Verify candidate event was emitted
    emitted_types = [call.args[0].event_type for call in mock_sink.emit.call_args_list]
    assert "memory_candidate_extracted" in emitted_types
