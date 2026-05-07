"""Service for extracting long-term memory candidates from chat messages."""

from pydantic import ValidationError

from src.Logging import get_logger
from src.backend.runtime import BaseInferenceRuntime
from src.backend.schemas import ChatMessage, InferencePromptRequest
from src.config import settings
from src.memory.schemas import MemoryExtraction, MemoryExtractionResult
from src.prompts import MEMORY_EXTRACTION_SYSTEM_PROMPT

logger = get_logger(__name__)


class MemoryExtractionService:
    """Extracts structural memory candidates from user chat messages."""

    def __init__(self, runtime: BaseInferenceRuntime):
        """Initialize the extraction service.
        
        Args:
            runtime: The inference runtime used to generate memory candidates.
        """
        self.runtime = runtime

    async def extract_memories(
        self,
        user_id: int,
        ai_companion_id: int,
        conversation_id: str,
        message_content: str,
    ) -> list[MemoryExtraction]:
        """Extract memory candidates from a user message.
        
        Args:
            user_id: The ID of the user.
            ai_companion_id: The ID of the companion.
            conversation_id: The ID of the current conversation session.
            message_content: The text of the user's latest message.
            
        Returns:
            A list of validated MemoryExtraction objects. Returns an empty list if extraction is disabled or fails.
        """
        if not settings.memory.extraction_enabled:
            logger.debug("Memory extraction is disabled in settings. Skipping extraction for user_id=%s", user_id)
            return []

        if not message_content or not message_content.strip():
            return []

        logger.info(
            "Extracting memories for user_id=%s companion_id=%s conversation_id=%s",
            user_id, ai_companion_id, conversation_id
        )
        
        if settings.memory.raw_content_logging_enabled:
            logger.debug("Extraction input content: %s", message_content)

        req = InferencePromptRequest(
            system_prompt=MEMORY_EXTRACTION_SYSTEM_PROMPT,
            messages=[ChatMessage(role="user", content=message_content)],
            json_schema=MemoryExtractionResult.model_json_schema(),
        )

        try:
            output_text = await self.runtime.generate_text(req)
        except Exception as e:
            logger.error("Inference runtime failed during memory extraction: %s", e)
            return []

        try:
            result = MemoryExtractionResult.model_validate_json(output_text.strip())
            
            if settings.memory.raw_content_logging_enabled:
                for idx, memory in enumerate(result.memories):
                    logger.debug(
                        "Extracted candidate %d: should_remember=%s type=%s key=%s content='%s' reason='%s'", 
                        idx, memory.should_remember, memory.memory_type, memory.canonical_key, memory.content, memory.reason
                    )
            
            return result.memories

        except ValidationError as e:
            logger.error("Malformed JSON or schema validation error during memory extraction: %s", e)
            return []
