"""Memory service entry point."""

from __future__ import annotations

from src.Logging import get_logger
from src.config import Memory

logger = get_logger(__name__)


class MemoryService:
    """Entry point for the memory subsystem.

    Extraction and retrieval methods will be added in subsequent issues.
    """

    def __init__(self, config: Memory):
        self.config = config
        logger.info(
            "Memory service initialized enabled=%s",
            config.enabled,
        )
