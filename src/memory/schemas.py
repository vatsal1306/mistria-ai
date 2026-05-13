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


class DebugMemoryRetrieveRequest(BaseModel):
    """Request schema for internal memory retrieval debugging."""

    model_config = ConfigDict(extra="forbid")

    user_mail_id: str = Field(description="The email address of the user.")
    ai_companion_id: int = Field(description="The ID of the AI companion.")
    user_message: str = Field(description="The hypothetical query or user message.")


class DebugMemoryRetrieveResponse(BaseModel):
    """Response schema for internal memory retrieval debugging."""

    model_config = ConfigDict(extra="forbid")

    user_mail_id: str = Field(description="The email address of the user.")
    ai_companion_id: int = Field(description="The ID of the AI companion.")
    memories: list[MemorySearchResult] = Field(description="The memory results that would be retrieved.")


class MemoryStoreOutcome(BaseModel):
    """The result of storing a batch of memory candidates."""
    model_config = ConfigDict(extra="forbid")

    stored_ids: list[int] = Field(default_factory=list, description="IDs of the newly created memory records.")
    created_count: int = Field(default=0, description="Number of memories that were brand new.")
    superseded_count: int = Field(default=0, description="Number of old memories that were superseded.")
    failed_count: int = Field(default=0, description="Number of candidates that failed to store.")


