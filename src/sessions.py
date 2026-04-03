"""In-memory chat sessions (pulse + history per user)."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.config import PULSE_DEFAULT
from src.pulse import MistriaPulse


@dataclass
class UserChatSession:
    pulse_engine: MistriaPulse
    history: list[dict[str, str]] = field(default_factory=list)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, UserChatSession] = {}

    def get_or_create(self, user_id: str, initial_pulse: int) -> UserChatSession:
        if user_id not in self._sessions:
            self._sessions[user_id] = UserChatSession(
                pulse_engine=MistriaPulse(initial_pulse),
                history=[],
            )
        return self._sessions[user_id]

    def reset(self, user_id: str, initial_pulse: int = PULSE_DEFAULT) -> None:
        self._sessions[user_id] = UserChatSession(
            pulse_engine=MistriaPulse(initial_pulse),
            history=[],
        )


SESSIONS = SessionStore()
