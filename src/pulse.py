"""Pulse scoring engine."""

from src.config import (
    HEAT_TRIGGERS,
    LONG_MSG_THRESHOLD,
    PULSE_DECAY_PER_TURN,
    PULSE_EXCLAIM_BOOST,
    PULSE_LONG_MSG_BOOST,
    PULSE_MAX,
    PULSE_MIN,
    PULSE_TRIGGER_BOOST,
)


class MistriaPulse:
    def __init__(self, start_score: int) -> None:
        self.score: int = max(PULSE_MIN, min(PULSE_MAX, start_score))

    def update(self, msg: str) -> int:
        self.score -= PULSE_DECAY_PER_TURN
        words = set(msg.lower().split())
        if words & HEAT_TRIGGERS:
            self.score += PULSE_TRIGGER_BOOST
        if len(msg) > LONG_MSG_THRESHOLD:
            self.score += PULSE_LONG_MSG_BOOST
        if "!" in msg:
            self.score += PULSE_EXCLAIM_BOOST
        self.score = max(PULSE_MIN, min(PULSE_MAX, self.score))
        return self.score
