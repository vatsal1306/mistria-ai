"""Chat orchestration service with engagement-driven behavior."""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from src.Logging import logger
from src.backend.runtime import BaseInferenceRuntime
from src.backend.schemas import ChatSocketRequest
from src.config import Chat, Engagement
from src.persona import CompanionPersona, load_companion
from src.persistence import load_user_data, save_user_session
from src.prompts import build_system_prompt, sanitize_response
from src.sessions import SESSIONS


@dataclass(frozen=True)
class StreamMetadata:
    """Metadata yielded as the final item of a streamed response."""

    connection: int
    latency_seconds: float


class ChatService:
    """Application service for chat with engagement-driven orchestration."""

    def __init__(
        self,
        chat_config: Chat,
        runtime: BaseInferenceRuntime,
        engagement_config: Engagement | None = None,
    ):
        self.chat_config = chat_config
        self.runtime = runtime
        self.engagement_config = engagement_config

    async def stream_response(
        self,
        request: ChatSocketRequest,
    ) -> AsyncGenerator[str | StreamMetadata, None]:
        """Stream response tokens, yielding StreamMetadata as the final item."""
        user_id = request.user_id
        user_info = None
        companion: CompanionPersona | None = None
        connection_pct = 0
        modified_request = request

        if user_id and self.engagement_config:
            user_info = load_user_data(user_id)

        if user_info and user_id and self.engagement_config:
            companion_id = user_info.get("companion_id", self.chat_config.default_companion_id)
            companion = load_companion(companion_id)

            last_score = int(user_info.get("engagement_score", self.engagement_config.default_score))
            last_msg_count = int(user_info.get("session_message_count", 0))
            last_seen = float(user_info.get("last_seen", 0))

            session = SESSIONS.get_or_create(user_id, last_score, last_msg_count)

            hours_away = (time.time() - last_seen) / 3600 if last_seen > 0 else 0
            if hours_away >= 12:
                session.engagement.apply_decay(hours_away)

            latest_message = request.messages[-1].content
            session.engagement.update(latest_message)

            state = session.engagement.relationship_state.value
            companion_name = companion.name if companion else self.chat_config.companion_name
            companion_personality = companion.personality_summary if companion else ""
            companion_backstory = companion.backstory if companion else ""

            system_prompt = build_system_prompt(
                relationship_state=state,
                user_info=user_info,
                companion_name=companion_name,
                companion_personality=companion_personality,
                companion_backstory=companion_backstory,
            )
            modified_request = request.model_copy(update={"system_prompt": system_prompt})
            connection_pct = session.engagement.connection_percentage

        trimmed = modified_request.messages[-self.chat_config.history_message_limit:]
        normalized = modified_request.model_copy(update={"messages": trimmed})

        start_time = time.time()
        full_reply_parts: list[str] = []

        async for token in self.runtime.stream_text(normalized):
            full_reply_parts.append(token)
            yield token

        full_reply = sanitize_response("".join(full_reply_parts))
        latency = round(time.time() - start_time, 2)

        if user_info and user_id and self.engagement_config:
            session = SESSIONS.get_or_create(user_id)
            session.history.append({"role": "assistant", "content": full_reply})
            connection_pct = session.engagement.connection_percentage
            save_user_session(
                user_id,
                session.engagement.score,
                session.engagement.session_message_count,
            )
            logger.debug(
                "[Engagement: %d | Connection: %d%% | State: %s | Latency: %ss]",
                session.engagement.score,
                connection_pct,
                session.engagement.relationship_state.value,
                latency,
            )

        yield StreamMetadata(connection=connection_pct, latency_seconds=latency)

    def reset_session(self, user_id: str) -> int:
        """Reset session and engagement to default. Returns connection %."""
        default = self.engagement_config.default_score if self.engagement_config else 0
        SESSIONS.reset(user_id, initial_score=default)
        save_user_session(user_id, default, 0)
        return 0

    def set_engagement(self, user_id: str, score: int) -> int:
        """Manually set engagement score (admin/dev). Returns connection %."""
        SESSIONS.reset(user_id, initial_score=score)
        save_user_session(user_id, score, 0)
        session = SESSIONS.get_or_create(user_id, score)
        return session.engagement.connection_percentage
