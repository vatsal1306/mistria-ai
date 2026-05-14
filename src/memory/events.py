"""Internal event system for memory-related actions."""

from datetime import datetime, timezone
from typing import Literal, Optional, Protocol

from pydantic import BaseModel, Field

from src.Logging import get_logger

logger = get_logger(__name__)

MemoryEventType = Literal[
    "memory_candidate_extracted",
    "memory_created",
    "memory_superseded",
    "memory_retrieved",
    "high_importance_preference_saved",
    "emotional_memory_saved",
]


class MemoryEvent(BaseModel):
    """Base payload for all memory-related internal events."""

    event_type: MemoryEventType
    user_id: int
    ai_companion_id: int
    conversation_id: Optional[int] = None
    memory_id: Optional[int] = None
    memory_type: Optional[str] = None
    importance: Optional[int] = None
    confidence: Optional[float] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MemoryEventSink(Protocol):
    """Interface for receiving internal memory events."""

    def emit(self, event: MemoryEvent) -> None:
        """Process a memory event."""
        ...


class NoOpMemoryEventSink:
    """Default implementation that does nothing."""

    def emit(self, event: MemoryEvent) -> None:
        """Ignore the event."""
        pass


class LoggingMemoryEventSink:
    """Implementation that logs events for auditing and engagement tracking."""

    def __init__(self) -> None:
        """Initialize with the default memory events logger."""
        self.logger = get_logger("mistria.memory.events")

    def emit(self, event: MemoryEvent) -> None:
        """Log the event as JSON for easy downstream parsing."""
        self.logger.info("Memory event: %s", event.model_dump_json())
