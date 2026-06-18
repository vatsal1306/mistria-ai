"""Unit tests for in-memory engagement score state."""

from __future__ import annotations

import threading

from src.engagement import state


def setup_function() -> None:
    state.clear_scores()


def test_get_last_score_returns_none_for_unknown_conversation() -> None:
    assert state.get_last_score("conversation-1") is None


def test_set_and_get_last_score_round_trip() -> None:
    state.set_last_score("conversation-1", 72)
    assert state.get_last_score("conversation-1") == 72


def test_set_last_score_overwrites_previous_value() -> None:
    state.set_last_score("conversation-1", 50)
    state.set_last_score("conversation-1", 80)
    assert state.get_last_score("conversation-1") == 80


def test_state_is_thread_safe_under_concurrent_updates() -> None:
    def _writer(conversation_id: str, score: int) -> None:
        state.set_last_score(conversation_id, score)

    threads = [
        threading.Thread(target=_writer, args=("conversation-1", 10 + index))
        for index in range(20)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert state.get_last_score("conversation-1") is not None
