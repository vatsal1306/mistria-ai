"""Reindex SQLite memories into Qdrant vector store."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from src.Logging import get_logger
from src.config import settings
from src.memory.embeddings import LocalEmbeddingProvider
from src.memory.vector_store import QdrantVectorStore
from src.storage.database import SQLiteDatabase
from src.storage.memory_repository import SQLiteMemoryRepository
from src.storage.repositories import SQLiteUserRepository

logger = get_logger(__name__)


@dataclass
class ReindexStats:
    """Accumulated counters for the reindexing run."""

    total: int = 0
    indexed: int = 0
    skipped: int = 0
    failed: int = 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the reindex script."""
    parser = argparse.ArgumentParser(
        description="Reindex SQLite memories into Qdrant vector store.",
    )
    parser.add_argument(
        "--user-email",
        help="Filter reindexing by user email.",
    )
    parser.add_argument(
        "--ai-companion-id",
        type=int,
        help="Filter reindexing by AI companion ID.",
    )
    parser.add_argument(
        "--memory-type",
        help="Filter reindexing by memory type (e.g., 'preference').",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of memories to reindex.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform no writes to Qdrant, only log what would be done.",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and recreate the Qdrant collection before indexing.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point for the reindex script."""
    args = parse_args(argv)

    if not settings.memory.enabled:
        logger.error("Memory system is disabled in configuration. Cannot reindex.")
        return 1

    database = SQLiteDatabase(settings.storage.sqlite_path)
    user_repo = SQLiteUserRepository(database)
    memory_repo = SQLiteMemoryRepository(database)

    # We use QdrantVectorStore directly here to ensure writes happen if enabled
    # regardless of whether the app is currently running.
    vector_store = QdrantVectorStore(
        url=settings.memory.qdrant_url,
        collection_name=settings.memory.qdrant_collection,
        enabled=True,
    )

    embedding_provider = LocalEmbeddingProvider(settings.memory.embedding_model_name)

    user_id = None
    if args.user_email:
        user = user_repo.find_by_email(args.user_email)
        if not user:
            logger.error("User with email '%s' not found.", args.user_email)
            return 1
        user_id = user.id

    if not args.dry_run:
        try:
            # We must load the model to know the dimension for collection creation
            dimension = embedding_provider.get_dimension()
            if args.recreate:
                logger.warning("Explicit recreation of collection '%s' requested.", settings.memory.qdrant_collection)
                vector_store.recreate_collection(dimension)
            else:
                vector_store.bootstrap_collection(dimension)
        except Exception as e:
            logger.error("Failed to prepare Qdrant collection: %s", e)
            return 1

    memories = memory_repo.list_all_active(
        user_id=user_id,
        ai_companion_id=args.ai_companion_id,
        memory_type=args.memory_type,
        limit=args.limit,
    )

    stats = ReindexStats(total=len(memories))
    logger.info("Found %d active memories to reindex.", stats.total)

    for memory in memories:
        try:
            if args.dry_run:
                logger.info("[DRY-RUN] Would reindex memory id=%d (key=%s)", memory.id, memory.canonical_key)
                stats.indexed += 1
                continue

            # Generate new embedding
            vector = embedding_provider.embed_text(memory.content)

            # Sync to vector store
            vector_store.upsert_memory(
                memory_id=memory.id,
                user_id=memory.user_id,
                ai_companion_id=memory.ai_companion_id,
                memory_type=memory.memory_type,
                canonical_key=memory.canonical_key,
                status=memory.status,
                vector=vector,
            )
            stats.indexed += 1

            if stats.indexed % 50 == 0:
                logger.info("Progress: %d/%d", stats.indexed, stats.total)

        except Exception as e:
            logger.error("Failed to reindex memory id=%d: %s", memory.id, e)
            stats.failed += 1

    logger.info("Reindexing complete.")
    logger.info(
        "Results - Total: %d, Indexed: %d, Failed: %d",
        stats.total,
        stats.indexed,
        stats.failed,
    )

    return 0 if stats.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
