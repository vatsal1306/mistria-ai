"""Memory service for managing long-term memories."""

from __future__ import annotations

import asyncio

from src.Logging import get_logger
from src.config import Memory
from src.memory.embeddings import BaseEmbeddingProvider
from src.memory.schemas import MemoryExtraction
from src.memory.vector_store import BaseVectorStore
from src.storage.memory_repository import MemoryRepository

logger = get_logger(__name__)


class MemoryService:
    """Service for storing, retrieving, and managing long-term memories."""

    def __init__(
        self,
        config: Memory,
        repository: MemoryRepository,
        vector_store: BaseVectorStore,
        embedding_provider: BaseEmbeddingProvider,
    ):
        """Initialize the memory service.
        
        Args:
            config: Memory configuration settings.
            repository: SQLite repository for memory persistence.
            vector_store: Vector store for semantic search.
            embedding_provider: Provider for generating text embeddings.
        """
        self.config = config
        self.repository = repository
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        logger.info("Memory service initialized enabled=%s", config.enabled)

    async def store_memories(
        self,
        user_id: int,
        ai_companion_id: int,
        conversation_id: int,
        extracted_memories: list[MemoryExtraction],
    ) -> list[int]:
        """Persist extracted memory candidates and sync with vector store.
        
        Blocking operations are offloaded to worker threads to prevent stalling
        the main asyncio event loop.
        
        Args:
            user_id: The ID of the user.
            ai_companion_id: The ID of the companion persona.
            conversation_id: The ID of the current conversation.
            extracted_memories: List of memory candidates extracted from chat.
            
        Returns:
            A list of newly created memory IDs.
        """
        if not self.config.enabled:
            logger.debug("Memory service is disabled. Skipping storage.")
            return []

        stored_ids = []

        for candidate in extracted_memories:
            if not candidate.should_remember:
                continue

            try:
                # 1. Handle Conflict Resolution (Superseding)
                # Check for existing active memory with the same canonical key in this scope
                existing = await asyncio.to_thread(
                    self.repository.find_active_by_canonical_key,
                    user_id=user_id,
                    ai_companion_id=ai_companion_id,
                    canonical_key=candidate.canonical_key,
                )

                # 2. Persist to SQLite
                new_record = await asyncio.to_thread(
                    self.repository.create_memory,
                    user_id=user_id,
                    ai_companion_id=ai_companion_id,
                    memory_type=candidate.memory_type,
                    canonical_key=candidate.canonical_key,
                    content=candidate.content,
                    importance=candidate.importance,
                    confidence=candidate.confidence,
                    source_conversation_id=conversation_id,
                )
                
                new_id = new_record.id
                stored_ids.append(new_id)

                if existing:
                    logger.info(
                        "Conflict detected for key '%s'. Superseding memory %d with %d",
                        candidate.canonical_key, existing.id, new_id
                    )
                    # Mark old as superseded in SQLite
                    await asyncio.to_thread(
                        self.repository.supersede,
                        memory_id=existing.id,
                        superseded_by_id=new_id
                    )
                    # Remove old from Vector Store to keep index clean
                    await asyncio.to_thread(
                        self.vector_store.delete_memory,
                        memory_id=existing.id
                    )

                # 3. Sync to Vector Store
                # Generate embedding for the new memory content
                vector = await asyncio.to_thread(
                    self.embedding_provider.embed_text,
                    candidate.content
                )
                
                # Upsert new memory to vector store
                await asyncio.to_thread(
                    self.vector_store.upsert_memory,
                    memory_id=new_id,
                    user_id=user_id,
                    ai_companion_id=ai_companion_id,
                    memory_type=candidate.memory_type,
                    canonical_key=candidate.canonical_key,
                    status="active",
                    vector=vector,
                )

            except Exception as e:
                logger.error(
                    "Failed to store memory candidate '%s' for user %d: %s",
                    candidate.canonical_key, user_id, e
                )
                # Continue to next candidate instead of failing the whole batch

        return stored_ids

