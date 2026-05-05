"""Pydantic schemas for the memory subsystem."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.memory.contracts import MemoryCategory


class MemoryEntry(BaseModel):
    """A single extracted memory fact."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    content: str = Field(min_length=1, description="The extracted memory text")
    category: MemoryCategory = Field(description="Classification of the memory")
    confidence: float = Field(ge=0.0, le=1.0, default=1.0, description="Extraction confidence score")
