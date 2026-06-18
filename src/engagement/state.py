"""In-memory engagement score state keyed by conversation."""

from __future__ import annotations

import threading

_lock = threading.Lock()
_last_known_scores: dict[str, int] = {}


def get_last_score(conversation_id: str) -> int | None:
    """Return the last known engagement score for a conversation, if any."""
    with _lock:
        return _last_known_scores.get(conversation_id)


def set_last_score(conversation_id: str, score: int) -> None:
    """Persist the latest engagement score for a conversation in memory."""
    with _lock:
        _last_known_scores[conversation_id] = score


def clear_scores() -> None:
    """Clear all cached scores. Intended for tests."""
    with _lock:
        _last_known_scores.clear()
