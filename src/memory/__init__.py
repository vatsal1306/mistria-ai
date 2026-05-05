"""Expose the memory module public API."""

from src.memory.contracts import MemoryScope
from src.memory.schemas import MemoryEntry
from src.memory.service import MemoryService

__all__ = [
    "MemoryEntry",
    "MemoryScope",
    "MemoryService",
]
