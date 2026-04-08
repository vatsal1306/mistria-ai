"""
Engagement scoring engine aligned with the Mistria Escalation & Engagement Spec.

Scoring:
    E += 1  per message
    E += 2  if session >= 5 messages
    E += 3  emotional / positive sentiment
    E += 5  voice interaction

Relationship states (internal only, never exposed to UI):
    0-20   just_met
    21-40  curious
    41-60  engaged
    61-80  attached
    81-100 intense

Decay:
    12h inactivity  -> slight decrease
    24h inactivity  -> moderate decrease
"""

from __future__ import annotations

from enum import Enum

from src.config import settings


class RelationshipState(str, Enum):
    JUST_MET = "just_met"
    CURIOUS = "curious"
    ENGAGED = "engaged"
    ATTACHED = "attached"
    INTENSE = "intense"


EMOTIONAL_TRIGGERS = frozenset([
    "love", "miss", "need", "want", "desire", "care", "amazing",
    "beautiful", "perfect", "obsessed", "crazy", "adore", "dream",
    "heart", "soul", "forever", "always", "feelings", "special",
    "kiss", "touch", "hold", "hug", "close", "cuddle", "mine",
    "baby", "babe", "darling", "sweetheart", "honey",
    "happy", "excited", "wow", "omg", "god", "please",
    "hard", "wet", "hot", "sexy", "naughty", "dirty",
    "body", "lips", "skin", "naked", "bed",
    "cock", "pussy", "cum", "tits", "ass", "clit",
    "finger", "ride", "thrust", "moan", "scream",
])


class EngagementEngine:
    """Tracks engagement score and derives relationship state per user session."""

    def __init__(self, initial_score: int = 0, session_message_count: int = 0):
        cfg = settings.engagement
        self.score: int = max(0, min(cfg.max_score, initial_score))
        self.session_message_count: int = session_message_count

    @property
    def relationship_state(self) -> RelationshipState:
        if self.score <= 20:
            return RelationshipState.JUST_MET
        if self.score <= 40:
            return RelationshipState.CURIOUS
        if self.score <= 60:
            return RelationshipState.ENGAGED
        if self.score <= 80:
            return RelationshipState.ATTACHED
        return RelationshipState.INTENSE

    @property
    def connection_percentage(self) -> int:
        """Non-linear connection % shown to user. Emotional/voice input = bigger jumps."""
        raw = self.score / settings.engagement.max_score
        curved = raw ** 0.7
        return min(100, max(0, int(curved * 100)))

    def update(self, message: str, is_voice: bool = False) -> int:
        """Update engagement based on a user action. Returns new score."""
        cfg = settings.engagement
        self.session_message_count += 1

        self.score += cfg.per_message_score

        if self.session_message_count >= cfg.session_bonus_threshold:
            self.score += cfg.session_bonus_score

        if self._has_emotional_sentiment(message):
            self.score += cfg.emotional_score

        if is_voice:
            self.score += cfg.voice_score

        if "!" in message:
            self.score += 1

        self.score = max(0, min(cfg.max_score, self.score))
        return self.score

    def apply_decay(self, hours_away: float) -> int:
        """Apply inactivity decay. Call on session resume after absence."""
        cfg = settings.engagement
        if hours_away >= 24:
            self.score = max(0, self.score - cfg.decay_24h)
        elif hours_away >= 12:
            self.score = max(0, self.score - cfg.decay_12h)
        return self.score

    @staticmethod
    def _has_emotional_sentiment(message: str) -> bool:
        words = set(message.lower().split())
        return bool(words & EMOTIONAL_TRIGGERS)
