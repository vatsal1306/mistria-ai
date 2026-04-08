"""In-memory chat sessions (engagement + history per user)."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.engagement import EngagementEngine


@dataclass
class UserChatSession:
    engagement: EngagementEngine
    history: list[dict[str, str]] = field(default_factory=list)


class SessionStore:
    """Store for per-user chat sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, UserChatSession] = {}

    def get_or_create(
        self,
        user_id: str,
        initial_score: int = 0,
        session_message_count: int = 0,
    ) -> UserChatSession:
        if user_id not in self._sessions:
            self._sessions[user_id] = UserChatSession(
                engagement=EngagementEngine(initial_score, session_message_count),
                history=[],
            )
        return self._sessions[user_id]

    def reset(self, user_id: str, initial_score: int = 0) -> None:
        self._sessions[user_id] = UserChatSession(
            engagement=EngagementEngine(initial_score),
            history=[],
        )


SESSIONS = SessionStore()
