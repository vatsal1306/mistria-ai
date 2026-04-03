"""Chat turn orchestration (sessions, persistence, LLM)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from src.config import AWAY_THRESHOLD_MINUTES, PULSE_DEFAULT
from src.llm import get_mistria_response
from src.persistence import load_user_data, save_user_session
from src.sessions import SESSIONS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatResult:
    reply: str
    pulse: int
    latency_seconds: float


def run_chat_turn(
    user_id: str,
    message: str,
    resume_pulse: bool,
) -> ChatResult | None:
    """Execute one chat turn. Returns None if ``user_id`` is unknown."""
    user_info = load_user_data(user_id)
    if not user_info:
        return None

    last_pulse = int(user_info.get("last_pulse", PULSE_DEFAULT))
    last_seen = float(user_info.get("last_seen", 0))
    minutes_away = (time.time() - last_seen) / 60 if last_seen > 0 else 0

    if last_seen > 0 and minutes_away > AWAY_THRESHOLD_MINUTES:
        start_pulse = last_pulse if resume_pulse else PULSE_DEFAULT
        SESSIONS.reset(user_id, initial_pulse=start_pulse)
        logger.debug(
            "Session cleared after %s min away for %s (resume_pulse=%s)",
            round(minutes_away),
            user_id,
            resume_pulse,
        )

    session = SESSIONS.get_or_create(user_id, initial_pulse=last_pulse)
    current_heat = session.pulse_engine.update(message)

    logger.debug("[Heat: %d%%] Mistria is thinking...", current_heat)
    reply, latency, session.history = get_mistria_response(
        message,
        current_heat,
        user_info,
        session.history,
    )
    logger.debug("[Latency: %ss]", latency)
    save_user_session(user_id, session.pulse_engine.score)

    return ChatResult(
        reply=reply,
        pulse=session.pulse_engine.score,
        latency_seconds=latency,
    )
