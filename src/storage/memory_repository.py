"""SQLite repository for long-term memories."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.Logging import get_logger
from src.storage.database import SQLiteDatabase
from src.storage.models import MemoryRecord

logger = get_logger(__name__)


class MemoryRepository(ABC):
    """Memory repository contract."""

    @abstractmethod
    def create_memory(
        self,
        user_id: int,
        ai_companion_id: int,
        memory_type: str,
        canonical_key: str,
        content: str,
        importance: int,
        confidence: float,
        source_conversation_id: int | None = None,
        source_message_id: int | None = None,
    ) -> MemoryRecord:
        """Create a new memory."""

    @abstractmethod
    def find_by_id(self, memory_id: int) -> MemoryRecord | None:
        """Look up a memory by its internal identifier."""

    @abstractmethod
    def list_active_for_scope(self, user_id: int, ai_companion_id: int) -> list[MemoryRecord]:
        """List all active memories for a given user and companion."""

    @abstractmethod
    def find_active_by_canonical_key(
        self, user_id: int, ai_companion_id: int, canonical_key: str
    ) -> MemoryRecord | None:
        """Find an active memory by its canonical key within a scope."""

    @abstractmethod
    def supersede(self, memory_id: int, superseded_by_id: int | None) -> MemoryRecord:
        """Mark a memory as superseded, optionally pointing to the new memory."""

    @abstractmethod
    def mark_retrieved(self, memory_id: int) -> None:
        """Update the retrieval count and timestamp for a memory."""

    @abstractmethod
    def keyword_search(self, user_id: int, ai_companion_id: int, query: str, limit: int) -> list[MemoryRecord]:
        """Perform a simple substring search on active memory content."""

    @abstractmethod
    def list_all_active(
        self,
        user_id: int | None = None,
        ai_companion_id: int | None = None,
        memory_type: str | None = None,
        limit: int | None = None,
    ) -> list[MemoryRecord]:
        """List all active memories across the entire system with optional filtering."""

    @abstractmethod
    def list_memories(
        self,
        user_id: int,
        ai_companion_id: int,
        status: str | None = "active",
        memory_type: str | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        """List memories with various filters for a specific scope."""


class SQLiteMemoryRepository(MemoryRepository):
    """SQLite-backed implementation of the memory repository."""

    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def _row_to_record(self, row: dict) -> MemoryRecord:
        return MemoryRecord(**row)

    def create_memory(
        self,
        user_id: int,
        ai_companion_id: int,
        memory_type: str,
        canonical_key: str,
        content: str,
        importance: int,
        confidence: float,
        source_conversation_id: int | None = None,
        source_message_id: int | None = None,
    ) -> MemoryRecord:
        """Create a new memory row and return the created record."""
        with self.database.connection() as connection:
            connection.execute(
                """
                INSERT INTO memories (
                    user_id, ai_companion_id, memory_type, canonical_key,
                    content, importance, confidence, source_conversation_id, source_message_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    ai_companion_id,
                    memory_type,
                    canonical_key,
                    content,
                    importance,
                    confidence,
                    source_conversation_id,
                    source_message_id,
                ),
            )
            row = connection.execute(
                "SELECT * FROM memories WHERE id = last_insert_rowid()"
            ).fetchone()
            connection.commit()

        record = self._row_to_record(dict(row))
        logger.debug("Created memory id=%s key=%s", record.id, record.canonical_key)
        return record

    def find_by_id(self, memory_id: int) -> MemoryRecord | None:
        """Fetch a memory by its internal primary key."""
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT * FROM memories WHERE id = ?",
                (memory_id,),
            ).fetchone()

        if row is None:
            return None
        return self._row_to_record(dict(row))

    def list_active_for_scope(self, user_id: int, ai_companion_id: int) -> list[MemoryRecord]:
        """List all active memories for a given user and companion."""
        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM memories
                WHERE user_id = ? AND ai_companion_id = ? AND status = 'active'
                ORDER BY importance DESC, updated_at DESC
                """,
                (user_id, ai_companion_id),
            ).fetchall()

        return [self._row_to_record(dict(row)) for row in rows]

    def find_active_by_canonical_key(
        self, user_id: int, ai_companion_id: int, canonical_key: str
    ) -> MemoryRecord | None:
        """Find an active memory by its canonical key within a scope."""
        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM memories
                WHERE user_id = ? AND ai_companion_id = ? AND canonical_key = ? AND status = 'active'
                """,
                (user_id, ai_companion_id, canonical_key),
            ).fetchone()

        if row is None:
            return None
        return self._row_to_record(dict(row))

    def supersede(self, memory_id: int, superseded_by_id: int | None) -> MemoryRecord:
        """Mark a memory as superseded, optionally pointing to the new memory."""
        with self.database.connection() as connection:
            connection.execute(
                """
                UPDATE memories
                SET status = 'superseded', supersedes_memory_id = ?
                WHERE id = ?
                """,
                (superseded_by_id, memory_id),
            )
            row = connection.execute(
                "SELECT * FROM memories WHERE id = ?",
                (memory_id,),
            ).fetchone()
            connection.commit()

        if row is None:
            raise ValueError(f"Memory with id {memory_id} not found after supersede update.")
        
        record = self._row_to_record(dict(row))
        logger.debug("Superseded memory id=%s by id=%s", memory_id, superseded_by_id)
        return record

    def mark_retrieved(self, memory_id: int) -> None:
        """Update the retrieval count and timestamp for a memory."""
        with self.database.connection() as connection:
            connection.execute(
                """
                UPDATE memories
                SET retrieval_count = retrieval_count + 1, last_retrieved_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (memory_id,),
            )
            connection.commit()

    def keyword_search(self, user_id: int, ai_companion_id: int, query: str, limit: int) -> list[MemoryRecord]:
        """Perform a simple substring search on active memory content."""
        search_pattern = f"%{query}%"
        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM memories
                WHERE user_id = ? AND ai_companion_id = ? AND status = 'active' AND content LIKE ?
                ORDER BY importance DESC, updated_at DESC
                LIMIT ?
                """,
                (user_id, ai_companion_id, search_pattern, limit),
            ).fetchall()

        return [self._row_to_record(dict(row)) for row in rows]
    def list_all_active(
        self,
        user_id: int | None = None,
        ai_companion_id: int | None = None,
        memory_type: str | None = None,
        limit: int | None = None,
    ) -> list[MemoryRecord]:
        """List all active memories across the entire system with optional filtering."""
        query = "SELECT * FROM memories WHERE status = 'active'"
        params = []

        if user_id is not None:
            query += " AND user_id = ?"
            params.append(user_id)
        if ai_companion_id is not None:
            query += " AND ai_companion_id = ?"
            params.append(ai_companion_id)
        if memory_type is not None:
            query += " AND memory_type = ?"
            params.append(memory_type)

        query += " ORDER BY id ASC"

        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        with self.database.connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()

        return [self._row_to_record(dict(row)) for row in rows]

    def list_memories(
        self,
        user_id: int,
        ai_companion_id: int,
        status: str | None = "active",
        memory_type: str | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        """List memories with various filters for a specific scope."""
        query = "SELECT * FROM memories WHERE user_id = ? AND ai_companion_id = ?"
        params = [user_id, ai_companion_id]

        if status and status != "all":
            query += " AND status = ?"
            params.append(status)
        
        if memory_type:
            query += " AND memory_type = ?"
            params.append(memory_type)

        query += " ORDER BY updated_at DESC, id DESC LIMIT ?"
        params.append(limit)

        with self.database.connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()

        return [self._row_to_record(dict(row)) for row in rows]
