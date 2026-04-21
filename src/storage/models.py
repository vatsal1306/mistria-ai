"""Dataclasses for local persistence records."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UserRecord:
    """Persisted user account row."""
    id: int
    email: str
    name: str
    encrypted_password: str | None
    created_at: str


@dataclass(frozen=True, slots=True)
class UserCompanionRecord:
    """Persisted user-level companion preference row."""
    id: int
    user_id: int
    intent_type: str
    dominance_mode: str
    intensity_level: str
    silence_response: str
    secret_desire: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class AICompanionRecord:
    """Persisted AI companion persona row."""
    id: int
    user_id: int
    title: str
    gender: str
    style: str
    ethnicity: str
    eye_color: str
    hair_style: str
    hair_color: str
    personality: str
    voice: str
    connection: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class ConversationRecord:
    """Persisted conversation row scoped to a user and optional persona."""
    id: int
    user_id: int
    ai_companion_id: int | None
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class MessageRecord:
    """Persisted chat message row."""
    id: int
    conversation_id: int
    role: str
    content: str
    created_at: str
    updated_at: str
