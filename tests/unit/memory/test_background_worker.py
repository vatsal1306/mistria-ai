"""Unit tests for the memory extraction background worker."""

from __future__ import annotations

import asyncio

import pytest

from src.backend.schemas import ChatMessage
from src.memory.background import MemoryExtractionWorker
from src.memory.schemas import MemoryExtraction


class _ExtractionServiceStub:
    """Stub that returns pre-configured extraction candidates."""

    def __init__(self, candidates: list[MemoryExtraction] | None = None, should_fail: bool = False):
        self.candidates = candidates or []
        self.should_fail = should_fail
        self.calls: list[dict] = []

    async def extract_memories(self, **kwargs) -> list[MemoryExtraction]:
        self.calls.append(kwargs)
        if self.should_fail:
            raise RuntimeError("extraction boom")
        return self.candidates


class _MemoryServiceStub:
    """Stub that records stored memory batches."""

    def __init__(self):
        self.stored: list[dict] = []

    async def store_memories(self, **kwargs) -> MemoryStoreOutcome:
        from src.memory.schemas import MemoryStoreOutcome
        self.stored.append(kwargs)
        return MemoryStoreOutcome(stored_ids=[100], created_count=1, superseded_count=0, failed_count=0)


@pytest.mark.anyio
async def test_worker_schedules_and_completes_extraction():
    """Verify the worker runs extraction and storage end-to-end."""
    candidate = MemoryExtraction(
        should_remember=True,
        memory_type="fact",
        canonical_key="likes_hiking",
        content="User likes hiking",
        importance=3,
        confidence=0.9,
        reason="Stated directly",
    )
    extraction_service = _ExtractionServiceStub(candidates=[candidate])
    memory_service = _MemoryServiceStub()
    worker = MemoryExtractionWorker(extraction_service, memory_service)

    worker.schedule(
        user_id=1, ai_companion_id=2, conversation_id=10,
        message_id=5, message_content="I love hiking",
    )

    # Wait for background task to complete
    await asyncio.sleep(0.1)

    assert len(extraction_service.calls) == 1
    assert extraction_service.calls[0]["user_id"] == 1
    assert extraction_service.calls[0]["message_content"] == "I love hiking"
    assert len(memory_service.stored) == 1
    assert memory_service.stored[0]["user_id"] == 1


@pytest.mark.anyio
async def test_worker_handles_extraction_failure_gracefully():
    """Verify the worker logs and suppresses extraction errors."""
    extraction_service = _ExtractionServiceStub(should_fail=True)
    memory_service = _MemoryServiceStub()
    worker = MemoryExtractionWorker(extraction_service, memory_service)

    worker.schedule(
        user_id=1, ai_companion_id=2, conversation_id=10,
        message_id=5, message_content="test",
    )

    await asyncio.sleep(0.1)

    # Extraction was attempted
    assert len(extraction_service.calls) == 1
    # Storage was never called because extraction failed
    assert len(memory_service.stored) == 0


@pytest.mark.anyio
async def test_worker_skips_storage_when_no_candidates():
    """Verify storage is not called when extraction returns nothing."""
    extraction_service = _ExtractionServiceStub(candidates=[])
    memory_service = _MemoryServiceStub()
    worker = MemoryExtractionWorker(extraction_service, memory_service)

    worker.schedule(
        user_id=1, ai_companion_id=2, conversation_id=10,
        message_id=5, message_content="just chatting",
    )

    await asyncio.sleep(0.1)

    assert len(extraction_service.calls) == 1
    assert len(memory_service.stored) == 0


@pytest.mark.anyio
async def test_worker_respects_concurrency_limit():
    """Verify jobs are skipped when the concurrency limit is reached."""
    extraction_service = _ExtractionServiceStub(candidates=[])
    memory_service = _MemoryServiceStub()
    worker = MemoryExtractionWorker(extraction_service, memory_service, max_concurrent_jobs=1)

    # Simulate a running job by setting the pending counter
    worker._pending = 1

    worker.schedule(
        user_id=1, ai_companion_id=2, conversation_id=10,
        message_id=5, message_content="should be skipped",
    )

    await asyncio.sleep(0.1)

    # The job should have been skipped because the limit was reached
    assert len(extraction_service.calls) == 0


@pytest.mark.anyio
async def test_worker_skips_all_burst_calls_beyond_limit():
    """Verify multiple synchronous schedule() calls are properly bounded."""
    extraction_service = _ExtractionServiceStub(candidates=[])
    memory_service = _MemoryServiceStub()
    worker = MemoryExtractionWorker(extraction_service, memory_service, max_concurrent_jobs=1)

    # Schedule 3 jobs synchronously before the event loop runs any task
    for i in range(3):
        worker.schedule(
            user_id=1, ai_companion_id=2, conversation_id=10,
            message_id=i, message_content=f"msg-{i}",
        )

    # Only the first call should have been accepted
    assert worker._pending == 1

    await asyncio.sleep(0.1)

    # Only 1 extraction should have run
    assert len(extraction_service.calls) == 1
    # Counter should be back to 0 after completion
    assert worker._pending == 0


@pytest.mark.anyio
async def test_worker_shutdown_awaits_pending_jobs():
    """Verify shutdown awaits jobs that complete quickly."""
    
    class _SlowExtractionStub(_ExtractionServiceStub):
        async def extract_memories(self, **kwargs):
            self.calls.append(kwargs)
            await asyncio.sleep(0.05)
            return self.candidates
            
    extraction_service = _SlowExtractionStub(candidates=[])
    memory_service = _MemoryServiceStub()
    worker = MemoryExtractionWorker(extraction_service, memory_service)

    worker.schedule(user_id=1, ai_companion_id=2, conversation_id=10, message_id=1, message_content="test")
    
    # Task is scheduled but not finished
    assert len(worker._tasks) == 1
    
    # Shutdown should wait for the task
    await worker.shutdown()
    
    # Task should be complete
    assert len(worker._tasks) == 0
    assert len(extraction_service.calls) == 1


@pytest.mark.anyio
async def test_worker_shutdown_cancels_long_running_jobs(monkeypatch):
    """Verify shutdown cancels jobs that exceed timeout."""
    
    class _VerySlowExtractionStub(_ExtractionServiceStub):
        async def extract_memories(self, **kwargs):
            self.calls.append(kwargs)
            await asyncio.sleep(10.0) # Much longer than timeout
            return self.candidates
            
    # Mock asyncio.wait to simulate a timeout quickly for the first call
    original_wait = asyncio.wait
    async def mock_wait(tasks, timeout=None):
        if timeout == 5.0:
            # First wait: return nothing done, all pending to simulate timeout
            return set(), tasks
        # Second wait (1.0s): let the real wait handle the cancellation
        return await original_wait(tasks, timeout=timeout)
        
    monkeypatch.setattr(asyncio, "wait", mock_wait)
            
    extraction_service = _VerySlowExtractionStub(candidates=[])
    memory_service = _MemoryServiceStub()
    worker = MemoryExtractionWorker(extraction_service, memory_service)

    worker.schedule(user_id=1, ai_companion_id=2, conversation_id=10, message_id=1, message_content="test")
    
    task = list(worker._tasks)[0]
    
    await worker.shutdown()
    
    # Task should have been cancelled
    assert task.cancelled()
