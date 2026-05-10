"""Pydantic schemas for memory extraction."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MemoryExtraction(BaseModel):
    """Schema for extracting a single memory candidate from a chat message."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    should_remember: bool = Field(
        description="True if the message contains a concrete memory, fact, or preference worth saving long-term."
    )
    memory_type: Literal["fact", "preference", "pattern", "emotional"] = Field(
        description="The category of the memory."
    )
    canonical_key: str = Field(
        description="A short, normalized key describing the topic (e.g., 'likes_dogs', 'user_age', 'fear_of_heights')."
    )
    content: str = Field(
        description="The actual memory content to save, phrased clearly."
    )
    importance: int = Field(
        ge=1,
        le=5,
        description="Importance from 1 (trivial/everyday) to 5 (critical/core identity).",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in extraction accuracy from 0.0 to 1.0.",
    )
    reason: str = Field(
        description="Brief reason for why this memory was extracted or why it was ignored."
    )


class MemoryExtractionResult(BaseModel):
    """Wrapper schema for extracting multiple memory candidates from a single chat message."""

    model_config = ConfigDict(extra="forbid")

    memories: list[MemoryExtraction] = Field(
        description="List of extracted memory candidates."
    )


class MemorySearchResult(BaseModel):
    """A single memory search result."""

    model_config = ConfigDict(extra="forbid")

    memory_id: int = Field(description="The unique identifier of the memory record.")
    memory_type: str = Field(description="The category of the memory.")
    content: str = Field(description="The actual text content of the memory.")
    canonical_key: str = Field(description="The normalized key for the memory.")
    score: float = Field(description="The calculated relevance score (0.0 to 1.0).")
    source: Literal["semantic", "keyword", "hybrid"] = Field(
        description="The method used to retrieve this memory."
    )


