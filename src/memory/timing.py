"""Lightweight timing instrumentation for memory operations.

Provides a reusable context manager for measuring operation durations
and structured-log emission. Designed so that future metrics export
(e.g. Prometheus) can hook into ``OperationTimer`` without changing call sites.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator

from src.Logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class TimingRecord:
    """Captured duration for a single measured operation."""

    operation: str
    duration_ms: float
    user_id: int | None = None
    ai_companion_id: int | None = None
    count: int | None = None
    extra: dict[str, object] = field(default_factory=dict)


@contextmanager
def timed_operation(
    operation: str,
    *,
    user_id: int | None = None,
    ai_companion_id: int | None = None,
    warn_threshold_ms: float | None = None,
) -> Generator[TimingRecord, None, None]:
    """Context manager that measures wall-clock duration and logs it.

    Args:
        operation: Human-readable label for the operation being timed.
        user_id: Optional scope identifier for structured logging.
        ai_companion_id: Optional scope identifier for structured logging.
        warn_threshold_ms: If set, emit a WARNING when the operation exceeds
            this many milliseconds. Otherwise a DEBUG log is emitted.

    Yields:
        A ``TimingRecord`` whose ``duration_ms`` and ``count`` fields can
        be updated by the caller before the context exits.
    """
    record = TimingRecord(
        operation=operation,
        duration_ms=0.0,
        user_id=user_id,
        ai_companion_id=ai_companion_id,
    )
    start = time.perf_counter()
    try:
        yield record
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        record.duration_ms = elapsed_ms

        parts = [
            "op=%s",
            "duration_ms=%.1f",
        ]
        args: list[object] = [operation, elapsed_ms]

        if user_id is not None:
            parts.append("user_id=%d")
            args.append(user_id)
        if ai_companion_id is not None:
            parts.append("companion_id=%d")
            args.append(ai_companion_id)
        if record.count is not None:
            parts.append("count=%d")
            args.append(record.count)

        fmt = " ".join(parts)

        if warn_threshold_ms is not None and elapsed_ms > warn_threshold_ms:
            logger.warning("SLOW " + fmt, *args)
        else:
            logger.info(fmt, *args)
