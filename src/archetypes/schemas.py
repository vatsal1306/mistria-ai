"""Pydantic schemas for archetype API endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.archetypes.contracts import ArchetypeId, OnboardingPathway, TraitVector


class SlowBurnScoreRequest(BaseModel):
    """Payload for submitting a Slow Burn archetype quiz."""

    model_config = ConfigDict(extra="forbid")

    user_mail_id: str = Field(..., min_length=3, max_length=320)
    trait_scores: TraitVector


class ArchetypeResultResponse(BaseModel):
    """Canonical representation of an archetype scoring result."""

    model_config = ConfigDict(extra="forbid")

    user_mail_id: str
    onboarding_pathway: OnboardingPathway
    primary_archetype: ArchetypeId
    primary_similarity: float
    secondary_archetype: ArchetypeId | None
    secondary_similarity: float | None
    blend_active: bool
    trait_scores: dict[str, float]
    created_at: datetime
