"""Memory service for managing long-term memories."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Literal

from src.Logging import get_logger
from src.config import Memory
from src.memory.embeddings import BaseEmbeddingProvider
from src.memory.schemas import MemoryExtraction, MemorySearchResult
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
        message_id: int,
        extracted_memories: list[MemoryExtraction],
    ) -> list[int]:
        """Persist extracted memory candidates and sync with vector store.
        
        Blocking operations are offloaded to worker threads to prevent stalling
        the main asyncio event loop.
        
        Args:
            user_id: The ID of the user.
            ai_companion_id: The ID of the companion persona.
            conversation_id: The ID of the current conversation.
            message_id: The ID of the current user message.
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
                    source_message_id=message_id,
                )
                
                new_id = new_record.id
                stored_ids.append(new_id)

                if self.config.raw_content_logging_enabled:
                    logger.info(
                        "Memory created id=%d user_id=%d companion_id=%d type=%s key=%s content=%r",
                        new_id, user_id, ai_companion_id, candidate.memory_type,
                        candidate.canonical_key, candidate.content,
                    )
                else:
                    logger.info(
                        "Memory created id=%d user_id=%d companion_id=%d type=%s key=%s",
                        new_id, user_id, ai_companion_id, candidate.memory_type,
                        candidate.canonical_key,
                    )

                if existing:
                    if self.config.raw_content_logging_enabled:
                        logger.info(
                            "Memory superseded old_id=%d new_id=%d key=%s old_content=%r new_content=%r",
                            existing.id, new_id, candidate.canonical_key,
                            existing.content, candidate.content,
                        )
                    else:
                        logger.info(
                            "Memory superseded old_id=%d new_id=%d key=%s",
                            existing.id, new_id, candidate.canonical_key,
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

    async def retrieve_memories(
        self,
        user_id: int,
        ai_companion_id: int,
        query: str,
    ) -> list[MemorySearchResult]:
        """Retrieve relevant memories using a hybrid of semantic and keyword search.
        
        Args:
            user_id: The ID of the user.
            ai_companion_id: The ID of the companion persona.
            query: The search query (usually the latest user message).
            
        Returns:
            A list of ranked MemorySearchResult objects.
        """
        if not self.config.enabled:
            return []

        logger.info(
            "Retrieval started user_id=%d companion_id=%d",
            user_id, ai_companion_id,
        )
        if self.config.raw_content_logging_enabled:
            logger.debug("Retrieval query content=%r", query)

        # 1. Semantic Search (Qdrant)
        semantic_results = []
        try:
            vector = await asyncio.to_thread(self.embedding_provider.embed_text, query)
            semantic_results = await asyncio.to_thread(
                self.vector_store.search,
                user_id=user_id,
                ai_companion_id=ai_companion_id,
                query_vector=vector,
                limit=self.config.retrieval_top_k * 2,
            )
        except Exception as e:
            logger.error("Semantic search failed during memory retrieval: %s", e)

        # 2. Keyword Search (SQLite)
        keyword_records = []
        try:
            keyword_records = await asyncio.to_thread(
                self.repository.keyword_search,
                user_id=user_id,
                ai_companion_id=ai_companion_id,
                query=query,
                limit=self.config.retrieval_top_k * 2,
            )
        except Exception as e:
            logger.error("Keyword search failed during memory retrieval: %s", e)

        # 3. Merge and Score
        candidate_ids = set([r.memory_id for r in semantic_results] + [r.id for r in keyword_records])
        scored_results = []

        for mid in candidate_ids:
            # Get full record (prefer existing keyword record to avoid extra DB call)
            record = next((r for r in keyword_records if r.id == mid), None)
            if not record:
                record = await asyncio.to_thread(self.repository.find_by_id, mid)

            if not record or record.status != "active":
                continue

            # Ensure isolation
            if record.user_id != user_id or record.ai_companion_id != ai_companion_id:
                continue

            # Scoring factors
            semantic_score = next((r.score for r in semantic_results if r.memory_id == mid), 0.0)
            keyword_hit = any(r.id == mid for r in keyword_records)

            # Base score calculation
            # Semantic score is naturally 0.0-1.0. Keyword hit gets a base relevance.
            base_score = semantic_score
            if keyword_hit:
                base_score = max(base_score, 0.5)
                if semantic_score > 0:
                    base_score += 0.2  # Hybrid bonus

            # Apply multipliers
            final_score = base_score
            final_score *= (0.5 + (record.importance / 10.0))  # Range 0.6 to 1.0
            final_score *= record.confidence

            # Recency decay (Monthly)
            try:
                # SQLite timestamps are UTC strings, potentially naive
                ts_str = record.updated_at
                updated_at = datetime.fromisoformat(ts_str)
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
                
                now = datetime.now(timezone.utc)
                days_old = (now - updated_at).days
                recency_multiplier = 1.0 / (1.0 + (max(0, days_old) / 30.0))
                final_score *= recency_multiplier
            except Exception as e:
                logger.debug("Failed to calculate recency for memory %d: %s", mid, e)

            # Filter by threshold
            if final_score >= self.config.retrieval_min_score:
                # Determine source label
                if semantic_score > 0 and keyword_hit:
                    source: Literal["semantic", "keyword", "hybrid"] = "hybrid"
                elif semantic_score > 0:
                    source = "semantic"
                else:
                    source = "keyword"

                scored_results.append(MemorySearchResult(
                    memory_id=record.id,
                    memory_type=record.memory_type,
                    content=record.content,
                    canonical_key=record.canonical_key,
                    score=min(final_score, 1.0),
                    source=source
                ))

        # 4. Finalize and mark retrieval
        scored_results.sort(key=lambda x: x.score, reverse=True)
        top_results = scored_results[:self.config.retrieval_top_k]

        for res in top_results:
            try:
                await asyncio.to_thread(self.repository.mark_retrieved, res.memory_id)
            except Exception as e:
                logger.warning("Failed to mark memory %d as retrieved: %s", res.memory_id, e)

        logger.info(
            "Retrieval completed user_id=%d companion_id=%d results=%d",
            user_id, ai_companion_id, len(top_results),
        )
        if self.config.raw_content_logging_enabled:
            for res in top_results:
                logger.debug(
                    "Retrieved memory id=%d score=%.4f source=%s type=%s content=%r",
                    res.memory_id, res.score, res.source, res.memory_type, res.content,
                )

        return top_results


