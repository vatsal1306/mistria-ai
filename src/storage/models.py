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
class AICompanionRecord:
    """Persisted AI companion persona row."""
    id: int
    user_id: int
    title: str
    description: str
    gender: str
    visual_style: str = ""
    companion_ethnicity: str = ""
    eye_color: str = ""
    age: int = 18
    hair_length: str = ""
    hair_style: str = ""
    hair_color: str = ""
    companion_personality: str = ""
    companion_profession: str = ""
    body_type: str = ""
    bust: str = ""
    height: str = ""
    intention: str = ""
    created_at: str = ""
    updated_at: str = ""
    style: str | None = None
    ethnicity: str | None = None
    personality: str | None = None
    voice: str | None = None
    connection: str | None = None

    def __post_init__(self) -> None:
        """Backfill new fields from legacy attributes when old test/database rows are used."""
        if not self.visual_style and self.style:
            object.__setattr__(self, "visual_style", self.style)
        if not self.companion_ethnicity and self.ethnicity:
            object.__setattr__(self, "companion_ethnicity", self.ethnicity)
        if not self.companion_personality and self.personality:
            object.__setattr__(self, "companion_personality", self.personality)
        if not self.intention and self.connection:
            object.__setattr__(self, "intention", self.connection)


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


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """Persisted long-term memory row."""
    id: int
    user_id: int
    ai_companion_id: int
    source_conversation_id: int | None
    source_message_id: int | None
    memory_type: str
    canonical_key: str
    content: str
    importance: int
    confidence: float
    status: str
    supersedes_memory_id: int | None
    created_at: str
    updated_at: str
    last_retrieved_at: str | None
    retrieval_count: int


@dataclass(frozen=True, slots=True)
class ArchetypeResultRecord:
    """Persisted Slow Burn archetype scoring submission row."""
    id: int
    user_id: int
    onboarding_pathway: str
    trait_scores_json: str
    primary_archetype: str
    primary_similarity: float
    secondary_archetype: str | None
    secondary_similarity: float | None
    blend_active: bool
    created_at: str
