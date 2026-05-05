"""Domain contracts for the memory subsystem."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MemoryCategory = Literal["fact", "preference", "event", "relationship"]


@dataclass(frozen=True, slots=True)
class MemoryScope:
    """Isolation key for all memory operations.

    Every memory operation must be scoped to a specific user and companion
    pair, ensuring that memories are never shared across companions.
    """
    user_id: int
    ai_companion_id: int
