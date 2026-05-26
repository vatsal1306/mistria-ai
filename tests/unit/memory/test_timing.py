"""Unit tests for memory timing instrumentation and timeout guardrails."""

import asyncio
import time
from unittest import mock

import pytest

from src.memory.timing import timed_operation, TimingRecord


class TestTimedOperation:
    """Tests for the timed_operation context manager."""

    def test_records_duration(self):
        """Verify that duration_ms is populated after context exit."""
        with timed_operation("test_op") as record:
            time.sleep(0.01)

        assert record.operation == "test_op"
        assert record.duration_ms >= 5  # at least ~10ms, allow margin

    def test_records_scope_fields(self):
        """Verify user_id and ai_companion_id are captured."""
        with timed_operation("scoped_op", user_id=42, ai_companion_id=7) as record:
            pass

        assert record.user_id == 42
        assert record.ai_companion_id == 7

    def test_count_field_can_be_set(self):
        """Verify caller can set count inside the context."""
        with timed_operation("counted_op") as record:
            record.count = 5

        assert record.count == 5

    def test_warns_on_slow_operation(self):
        """Verify WARNING log when operation exceeds threshold."""
        with mock.patch("src.memory.timing.logger") as mock_logger:
            with timed_operation("slow_op", warn_threshold_ms=0.001):
                time.sleep(0.01)

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0][0]
        assert "SLOW" in call_args

    def test_no_warn_under_threshold(self):
        """Verify no warning when operation is under threshold."""
        with mock.patch("src.memory.timing.logger") as mock_logger:
            with timed_operation("fast_op", warn_threshold_ms=10000):
                pass

        mock_logger.warning.assert_not_called()
        mock_logger.info.assert_called_once()


class TestRetrievalTimeout:
    """Tests for the retrieval timeout guardrail in MemoryService."""

    @pytest.mark.anyio
    async def test_retrieval_timeout_returns_empty_list(self):
        """Verify that a slow retrieval returns [] instead of crashing."""
        from src.config import Memory
        from src.memory.service import MemoryService

        config = Memory(
            enabled=True,
            retrieval_top_k=5,
            retrieval_min_score=0.35,
            retrieval_timeout_seconds=0.05,  # 50ms timeout
        )

        # Create a slow embedding provider that sleeps longer than the timeout
        slow_embed = mock.Mock()
        def slow_embed_text(text):
            time.sleep(0.2)  # 200ms — will exceed timeout
            return [0.1] * 384
        slow_embed.embed_text = slow_embed_text

        mock_repo = mock.Mock()
        mock_vector_store = mock.Mock()

        service = MemoryService(config, mock_repo, mock_vector_store, slow_embed)

        result = await service.retrieve_memories(
            user_id=1,
            ai_companion_id=2,
            query="test query",
        )

        assert result == []

    @pytest.mark.anyio
    async def test_retrieval_completes_within_timeout(self):
        """Verify that fast retrieval succeeds normally."""
        from src.config import Memory
        from src.memory.service import MemoryService

        config = Memory(
            enabled=True,
            retrieval_top_k=5,
            retrieval_min_score=0.35,
            retrieval_timeout_seconds=5.0,
        )

        fast_embed = mock.Mock()
        fast_embed.embed_text.return_value = [0.1] * 384

        mock_repo = mock.Mock()
        mock_repo.keyword_search.return_value = []
        mock_repo.find_by_id.return_value = None

        mock_vector_store = mock.Mock()
        mock_vector_store.search.return_value = []

        service = MemoryService(config, mock_repo, mock_vector_store, fast_embed)

        result = await service.retrieve_memories(
            user_id=1,
            ai_companion_id=2,
            query="test query",
        )

        assert result == []
        fast_embed.embed_text.assert_called_once_with("test query")

    @pytest.mark.anyio
    async def test_retrieval_disabled_returns_empty(self):
        """Verify disabled config returns [] without timing overhead."""
        from src.config import Memory
        from src.memory.service import MemoryService

        config = Memory(enabled=False)
        service = MemoryService(config, mock.Mock(), mock.Mock(), mock.Mock())

        result = await service.retrieve_memories(user_id=1, ai_companion_id=2, query="q")
        assert result == []
