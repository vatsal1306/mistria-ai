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

    async def store_memories(self, **kwargs) -> list[int]:
        self.stored.append(kwargs)
        return [100]


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

    # Acquire the semaphore manually to simulate a running job
    await worker._semaphore.acquire()

    worker.schedule(
        user_id=1, ai_companion_id=2, conversation_id=10,
        message_id=5, message_content="should be skipped",
    )

    await asyncio.sleep(0.1)

    # The job should have been skipped because the semaphore was full
    assert len(extraction_service.calls) == 0

    # Release the semaphore
    worker._semaphore.release()
