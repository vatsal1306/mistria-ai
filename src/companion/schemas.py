"""Pydantic schemas for the companion HTTP API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.companion.contracts import (
    AIConnection,
    AIEthnicity,
    AIEyeColor,
    AIGender,
    AIHairColor,
    AIHairStyle,
    AIPersonality,
    AIStyle,
    AIVoice,
    DominanceMode,
    IntentType,
    IntensityLevel,
    SecretDesire,
    SilenceResponse,
)


def normalize_user_mail_id(user_mail_id: str) -> str:
    """Normalize and minimally validate the incoming user email identifier."""
    normalized = user_mail_id.strip().lower()
    if not normalized or "@" not in normalized:
        raise ValueError("user_mail_id must be a valid email address.")
    return normalized


class UserCompanionUpsertRequest(BaseModel):
    """Request payload for saving user-level companion preferences."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    user_mail_id: str = Field(min_length=3, max_length=320)
    intent_type: IntentType
    dominance_mode: DominanceMode
    intensity_level: IntensityLevel
    silence_response: SilenceResponse
    secret_desire: SecretDesire

    @field_validator("user_mail_id")
    @classmethod
    def validate_user_mail_id(cls, value: str) -> str:
        """Normalize the email identifier before model validation completes."""
        return normalize_user_mail_id(value)


class UserCompanionResponse(BaseModel):
    """Saved user-level companion preferences."""

    model_config = ConfigDict(extra="forbid")

    user_mail_id: str
    intent_type: IntentType
    dominance_mode: DominanceMode
    intensity_level: IntensityLevel
    silence_response: SilenceResponse
    secret_desire: SecretDesire


class AICompanionCreateRequest(BaseModel):
    """Request payload for creating an AI companion persona."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    user_mail_id: str = Field(min_length=3, max_length=320)
    title: str | None = Field(default=None, min_length=1, max_length=120)
    gender: AIGender
    style: AIStyle
    ethnicity: AIEthnicity
    eyeColor: AIEyeColor
    hairStyle: AIHairStyle
    hairColor: AIHairColor
    personality: AIPersonality
    voice: AIVoice
    connection: AIConnection

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


class AICompanionIdentifierResponse(BaseModel):
    """Identifier returned when a companion is created."""

    model_config = ConfigDict(extra="forbid")

    id: int


class AICompanionResponse(BaseModel):
    """Saved AI companion payload returned by read endpoints."""

    model_config = ConfigDict(extra="forbid")

    id: int
    user_mail_id: str
    title: str
    gender: AIGender
    style: AIStyle
    ethnicity: AIEthnicity
    eyeColor: AIEyeColor
    hairStyle: AIHairStyle
    hairColor: AIHairColor
    personality: AIPersonality
    voice: AIVoice
    connection: AIConnection
