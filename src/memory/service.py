"""Memory service coordinating extraction and retrieval."""

from __future__ import annotations

from src.Logging import get_logger
from src.config import Memory
from src.memory.contracts import MemoryScope
from src.memory.schemas import MemoryEntry

logger = get_logger(__name__)


class MemoryService:
    """Coordinate memory extraction, storage, and retrieval.

    This service is the single entry point for the memory subsystem.
    Actual extraction and vector retrieval logic will be implemented
    in subsequent issues.
    """

    def __init__(self, config: Memory):
        self.config = config
        logger.info(
            "Memory service initialized enabled=%s extraction=%s",
            config.enabled,
            config.extraction_enabled,
        )

    def extract(self, scope: MemoryScope, conversation_text: str) -> list[MemoryEntry]:
        """Extract memory entries from a conversation turn.

        Not yet implemented. Will be added in a future issue.
        """
        raise NotImplementedError("Memory extraction will be implemented in a future issue.")

    def retrieve(self, scope: MemoryScope, query: str, top_k: int | None = None) -> list[MemoryEntry]:
        """Retrieve relevant memories for a query.

        Not yet implemented. Will be added in a future issue.
        """
        raise NotImplementedError("Memory retrieval will be implemented in a future issue.")
