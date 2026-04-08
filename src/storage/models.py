"""Dataclasses for local persistence records."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UserRecord:
    id: int
    email: str
    name: str
    encrypted_password: str
    created_at: str


@dataclass(frozen=True, slots=True)
class ConversationRecord:
    id: int
    user_id: int
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class MessageRecord:
    id: int
    conversation_id: int
    role: str
    content: str
    created_at: str
    updated_at: str
