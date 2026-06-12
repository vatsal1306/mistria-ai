"""Pydantic schemas for the companion HTTP API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.companion.contracts import (
    AIBust,
    AIEthnicity,
    AIGender,
    AIHeight,
    AIPersonality,
)


def normalize_user_mail_id(user_mail_id: str) -> str:
    """Normalize and minimally validate the incoming user email identifier."""
    normalized = user_mail_id.strip().lower()
    if not normalized or "@" not in normalized:
        raise ValueError("user_mail_id must be a valid email address.")
    return normalized


class AICompanionMetadata(BaseModel):
    """Structured output for AI companion metadata generation."""

    title: str = Field(
        description=(
            "Exactly one realistic human first name. One word only. "
            "No spaces, punctuation, surnames, titles, roles, or fantasy labels."
        )
    )
    description: str = Field(
        description=(
            "A brief single-sentence persona description grounded in the supplied traits."
        )
    )


class AICompanionFeaturePayload(BaseModel):
    """Shared companion feature fields used by create, generate, and response models."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    gender: AIGender
    visual_style: str = Field(min_length=1)
    companion_ethnicity: AIEthnicity
    eye_color: str = Field(min_length=1)
    age: int = Field(ge=18, le=120)
    hair_length: str = Field(min_length=1)
    hair_style: str = Field(min_length=1)
    hair_color: str = Field(min_length=1)
    companion_personality: AIPersonality
    companion_profession: str = Field(min_length=1)
    body_type: str = Field(min_length=1)
    bust: AIBust
    height: AIHeight
    intention: str = Field(min_length=1)


class AICompanionCreateRequest(AICompanionFeaturePayload):
    """Request payload for creating an AI companion persona."""

    user_mail_id: str = Field(min_length=3, max_length=320)
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, min_length=1)

    @field_validator("user_mail_id")
    @classmethod
    def validate_user_mail_id(cls, value: str) -> str:
        """Normalize the email identifier before model validation completes."""
        return normalize_user_mail_id(value)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        """Collapse blank titles to `None` so the service can generate a default."""
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        """Collapse blank descriptions to `None` so the service can generate a default."""
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class AICompanionGenerateRequest(AICompanionFeaturePayload):
    """Request payload for generating companion metadata without persistence."""


class AICompanionGenerateResponse(BaseModel):
    """Generated companion metadata returned without storing a companion."""

    model_config = ConfigDict(extra="forbid")

    title: str
    description: str


class AICompanionCreateResponse(BaseModel):
    """Identifier and metadata returned when a companion is created."""

    model_config = ConfigDict(extra="forbid")

    ai_companion_id: int
    title: str
    description: str 


class AICompanionResponse(AICompanionFeaturePayload):
    """Saved AI companion payload returned by read endpoints."""

    id: int
    user_mail_id: str
    title: str
    description: str
