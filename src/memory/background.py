"""Background worker for non-blocking memory extraction."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from src.Logging import get_logger

if TYPE_CHECKING:
    from src.backend.schemas import ChatMessage
    from src.memory.extraction import MemoryExtractionService
    from src.memory.service import MemoryService

logger = get_logger(__name__)

_DEFAULT_MAX_CONCURRENT_JOBS = 3


class MemoryExtractionWorker:
    """Schedule and run memory extraction jobs without blocking chat streaming."""

    def __init__(
        self,
        extraction_service: MemoryExtractionService,
        memory_service: MemoryService,
        max_concurrent_jobs: int = _DEFAULT_MAX_CONCURRENT_JOBS,
    ):
        """Initialize the background extraction worker.

        Args:
            extraction_service: Service that extracts memory candidates from messages.
            memory_service: Service that persists extracted memories.
            max_concurrent_jobs: Maximum number of concurrent extraction jobs.
        """
        self.extraction_service = extraction_service
        self.memory_service = memory_service
        self._max_concurrent_jobs = max_concurrent_jobs
        self._pending = 0
        self._tasks: set[asyncio.Task] = set()  # type: ignore[type-arg]

    def schedule(
        self,
        user_id: int,
        ai_companion_id: int,
        conversation_id: int,
        message_id: int,
        message_content: str,
        recent_messages: list[ChatMessage] | None = None,
    ) -> None:
        """Schedule a non-blocking extraction job.

        Args:
            user_id: The internal user ID.
            ai_companion_id: The companion persona ID.
            conversation_id: The current conversation ID.
            message_id: The user message record ID.
            message_content: The raw user message text.
            recent_messages: Optional recent conversation context.
        """
        if self._pending >= self._max_concurrent_jobs:
            logger.warning(
                "Extraction job skipped (concurrency limit reached) user_id=%d conversation_id=%d message_id=%d",
                user_id, conversation_id, message_id,
            )
            return

        self._pending += 1
        task = asyncio.create_task(
            self._run(
                user_id, ai_companion_id, conversation_id, message_id,
                message_content, recent_messages,
            ),
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def shutdown(self) -> None:
        """Gracefully shut down the worker, waiting for pending jobs to finish."""
        if not self._tasks:
            return

        logger.info("MemoryExtractionWorker shutting down. Waiting for %d pending jobs.", len(self._tasks))
        
        # Give pending tasks up to 5 seconds to finish cleanly
        done, pending = await asyncio.wait(self._tasks, timeout=5.0)
        
        if pending:
            logger.warning("MemoryExtractionWorker shutdown timeout. Cancelling %d tasks.", len(pending))
            for task in pending:
                task.cancel()
            
            # Wait briefly for cancellation to process
            await asyncio.wait(pending, timeout=1.0)
            
        logger.info("MemoryExtractionWorker shutdown complete.")

    async def _run(
        self,
        user_id: int,
        ai_companion_id: int,
        conversation_id: int,
        message_id: int,
        message_content: str,
        recent_messages: list[ChatMessage] | None,
    ) -> None:
        """Execute a single extraction-and-store cycle."""
        try:
            logger.info(
                "Extraction job started user_id=%d conversation_id=%d message_id=%d",
                user_id, conversation_id, message_id,
            )
            candidates = await self.extraction_service.extract_memories(
                user_id=user_id,
                ai_companion_id=ai_companion_id,
                conversation_id=conversation_id,
                message_id=message_id,
                message_content=message_content,
                recent_messages=recent_messages,
            )

            if not candidates:
                logger.info(
                    "Extraction job completed with no candidates user_id=%d message_id=%d",
                    user_id, message_id,
                )
                return

            outcome = await self.memory_service.store_memories(
                user_id=user_id,
                ai_companion_id=ai_companion_id,
                conversation_id=conversation_id,
                message_id=message_id,
                extracted_memories=candidates,
            )
            logger.info(
                "Extraction job succeeded user_id=%d message_id=%d candidates=%d created=%d superseded=%d failed=%d",
                user_id, message_id, len(candidates), outcome.created_count, outcome.superseded_count, outcome.failed_count,
            )
        except Exception:
            logger.exception(
                "Extraction job failed user_id=%d conversation_id=%d message_id=%d",
                user_id, conversation_id, message_id,
            )
        finally:
            self._pending -= 1
