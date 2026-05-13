"""Backfill memory extraction for existing chat history."""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass

from src.Logging import get_logger
from src.backend.runtime import InferenceRuntimeFactory
from src.config import settings
from src.memory.embeddings import LocalEmbeddingProvider
from src.memory.extraction import MemoryExtractionService
from src.memory.service import MemoryService
from src.memory.vector_store import QdrantVectorStore
from src.storage.database import SQLiteDatabase
from src.storage.memory_repository import SQLiteMemoryRepository
from src.storage.repositories import SQLiteUserRepository

logger = get_logger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the backfill script."""
    parser = argparse.ArgumentParser(
        description="Backfill memory extraction from existing chat history.",
    )
    parser.add_argument(
        "--user-email",
        default=None,
        help="Limit backfill to a single user by email address.",
    )
    parser.add_argument(
        "--ai-companion-id",
        type=int,
        default=None,
        help="Limit backfill to a single AI companion ID.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of user messages to process.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract candidates but do not persist them.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Abort the entire run on first extraction failure.",
    )
    return parser.parse_args(argv)


@dataclass
class BackfillStats:
    """Accumulated counters for the backfill run."""

    scanned: int = 0
    skipped: int = 0
    extracted: int = 0
    stored: int = 0
    failed: int = 0


def scan_messages(
    database: SQLiteDatabase,
    *,
    user_id: int | None = None,
    ai_companion_id: int | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Query user messages joined with their conversation scope.

    Returns a list of dicts with keys:
        message_id, conversation_id, user_id, ai_companion_id, content
    """
    clauses = ["m.role = 'user'", "c.ai_companion_id IS NOT NULL"]
    params: list[object] = []

    if user_id is not None:
        clauses.append("c.user_id = ?")
        params.append(user_id)

    if ai_companion_id is not None:
        clauses.append("c.ai_companion_id = ?")
        params.append(ai_companion_id)

    where = " AND ".join(clauses)
    query = f"""
        SELECT
            m.id          AS message_id,
            c.id          AS conversation_id,
            c.user_id     AS user_id,
            c.ai_companion_id AS ai_companion_id,
            m.content     AS content
        FROM messages m
        JOIN conversations c ON c.id = m.conversation_id
        WHERE {where}
        ORDER BY m.created_at ASC, m.id ASC
    """

    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)

    with database.connection() as connection:
        rows = connection.execute(query, params).fetchall()

    return [dict(row) for row in rows]


def load_processed_message_ids(database: SQLiteDatabase) -> set[int]:
    """Return the set of message IDs that already have memory candidates."""
    with database.connection() as connection:
        rows = connection.execute(
            "SELECT DISTINCT source_message_id FROM memories WHERE source_message_id IS NOT NULL"
        ).fetchall()
    return {row["source_message_id"] for row in rows}


async def run_backfill(args: argparse.Namespace) -> BackfillStats:
    """Execute the backfill run with the given CLI arguments."""
    stats = BackfillStats()

    # 1. Initialize infrastructure
    database = SQLiteDatabase(settings.storage.sqlite_path)
    database.initialize()

    user_repository = SQLiteUserRepository(database)
    memory_repository = SQLiteMemoryRepository(database)

    runtime = InferenceRuntimeFactory.create(
        settings.chat, settings.inference, settings.secrets,
    )
    await runtime.startup()

    extraction_service = MemoryExtractionService(runtime)

    # Memory service and its dependencies (only needed for non-dry-run)
    memory_service: MemoryService | None = None
    if not args.dry_run:
        embedding_provider = LocalEmbeddingProvider(settings.memory.embedding_model_name)
        vector_store = QdrantVectorStore(
            url=settings.memory.qdrant_url,
            collection_name=settings.memory.qdrant_collection,
            enabled=settings.memory.enabled,
        )
        dimension = embedding_provider.get_dimension()
        vector_store.bootstrap_collection(dimension)
        memory_service = MemoryService(
            config=settings.memory,
            repository=memory_repository,
            vector_store=vector_store,
            embedding_provider=embedding_provider,
        )

    try:
        # 2. Resolve optional user filter
        user_id_filter: int | None = None
        if args.user_email:
            user = user_repository.find_by_email(args.user_email)
            if not user:
                logger.error("User not found for email=%s", args.user_email)
                return stats
            user_id_filter = user.id
            logger.info("Filtering to user_id=%d email=%s", user.id, args.user_email)

        # 3. Scan messages
        messages = scan_messages(
            database,
            user_id=user_id_filter,
            ai_companion_id=args.ai_companion_id,
            limit=args.limit,
        )
        logger.info("Scanned %d user messages from chat history.", len(messages))

        # 4. Load already-processed message IDs for skip logic
        processed_ids = load_processed_message_ids(database)
        logger.info("Found %d messages already linked to memories.", len(processed_ids))

        # 5. Process each message
        for msg in messages:
            stats.scanned += 1
            message_id = msg["message_id"]

            if message_id in processed_ids:
                stats.skipped += 1
                continue

            try:
                candidates = await extraction_service.extract_memories(
                    user_id=msg["user_id"],
                    ai_companion_id=msg["ai_companion_id"],
                    conversation_id=msg["conversation_id"],
                    message_id=message_id,
                    message_content=msg["content"],
                )

                stats.extracted += len(candidates)

                if candidates and memory_service and not args.dry_run:
                    stored_ids = await memory_service.store_memories(
                        user_id=msg["user_id"],
                        ai_companion_id=msg["ai_companion_id"],
                        conversation_id=msg["conversation_id"],
                        message_id=message_id,
                        extracted_memories=candidates,
                    )
                    stats.stored += len(stored_ids)

                if args.dry_run and candidates:
                    logger.info(
                        "[DRY RUN] message_id=%d would produce %d candidates",
                        message_id, len(candidates),
                    )

            except Exception as e:
                stats.failed += 1
                logger.error(
                    "Failed to process message_id=%d conversation_id=%d: %s",
                    message_id, msg["conversation_id"], e,
                )
                if args.fail_fast:
                    raise

    finally:
        await runtime.shutdown()

    return stats


def main(argv: list[str] | None = None) -> None:
    """Entry point for the backfill script."""
    args = parse_args(argv)

    mode = "DRY RUN" if args.dry_run else "LIVE"
    logger.info(
        "Starting memory backfill mode=%s user_email=%s ai_companion_id=%s limit=%s fail_fast=%s",
        mode, args.user_email, args.ai_companion_id, args.limit, args.fail_fast,
    )

    stats = asyncio.run(run_backfill(args))

    summary = (
        f"\n{'=' * 50}\n"
        f"  Memory Backfill Summary ({mode})\n"
        f"{'=' * 50}\n"
        f"  Messages scanned:  {stats.scanned}\n"
        f"  Messages skipped:  {stats.skipped}\n"
        f"  Candidates found:  {stats.extracted}\n"
        f"  Memories stored:   {stats.stored}\n"
        f"  Failures:          {stats.failed}\n"
        f"{'=' * 50}\n"
    )
    print(summary)

    if stats.failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
