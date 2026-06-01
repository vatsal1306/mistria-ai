"""SQLite repository for Slow Burn archetype scoring results."""

from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod

from src.archetypes.contracts import ARCHETYPE_IDS
from src.Logging import get_logger
from src.storage.database import SQLiteDatabase
from src.storage.models import ArchetypeResultRecord

logger = get_logger(__name__)


class ArchetypeResultRepository(ABC):
    """Archetype result repository contract."""

    @abstractmethod
    def create_result(
        self,
        user_id: int,
        onboarding_pathway: str,
        trait_scores_json: str,
        primary_archetype: str,
        primary_similarity: float,
        secondary_archetype: str | None,
        secondary_similarity: float | None,
        blend_active: bool,
    ) -> ArchetypeResultRecord:
        """Persist a new archetype scoring submission."""

    @abstractmethod
    def find_latest_by_user_id(self, user_id: int) -> ArchetypeResultRecord | None:
        """Fetch the most recent archetype result for a user."""

    @abstractmethod
    def list_by_user_id(
        self, user_id: int, *, limit: int | None = None
    ) -> list[ArchetypeResultRecord]:
        """List archetype results for a user, newest first."""

    # ------------------------------------------------------------------
    # Convenience helpers – concrete so subclasses inherit them for free
    # ------------------------------------------------------------------

    def create_from_scoring(
        self,
        user_id: int,
        onboarding_pathway: str,
        trait_vector: dict[str, float],
        primary_archetype: str,
        primary_similarity: float,
        secondary_archetype: str | None = None,
        secondary_similarity: float | None = None,
        blend_active: bool = False,
    ) -> ArchetypeResultRecord:
        """Serialize a trait-vector dict and persist the result in one call.

        This keeps JSON serialization centralized so callers never build
        the ``trait_scores_json`` string themselves.
        """
        return self.create_result(
            user_id=user_id,
            onboarding_pathway=onboarding_pathway,
            trait_scores_json=json.dumps(trait_vector, sort_keys=True),
            primary_archetype=primary_archetype,
            primary_similarity=primary_similarity,
            secondary_archetype=secondary_archetype,
            secondary_similarity=secondary_similarity,
            blend_active=blend_active,
        )

    @staticmethod
    def parse_trait_scores(record: ArchetypeResultRecord) -> dict[str, float]:
        """Deserialize the stored ``trait_scores_json`` back to a typed dict."""
        return json.loads(record.trait_scores_json)


class SQLiteArchetypeResultRepository(ArchetypeResultRepository):
    """SQLite-backed implementation of the archetype result repository."""

    def __init__(self, database: SQLiteDatabase):
        self.database = database

    @staticmethod
    def _map_row(row: sqlite3.Row) -> ArchetypeResultRecord:
        data = dict(row)
        data["blend_active"] = bool(data["blend_active"])
        return ArchetypeResultRecord(**data)

    def create_result(
        self,
        user_id: int,
        onboarding_pathway: str,
        trait_scores_json: str,
        primary_archetype: str,
        primary_similarity: float,
        secondary_archetype: str | None,
        secondary_similarity: float | None,
        blend_active: bool,
    ) -> ArchetypeResultRecord:
        """Insert a new archetype scoring submission and return the created record."""
        if primary_archetype not in ARCHETYPE_IDS:
            raise ValueError(
                f"Invalid primary_archetype: '{primary_archetype}'. Must be one of {ARCHETYPE_IDS}"
            )
        if not (-3.0 <= primary_similarity <= 3.0):
            raise ValueError(
                f"Invalid primary_similarity: {primary_similarity}. Must be between -3.0 and 3.0"
            )
        if secondary_archetype is not None and secondary_archetype not in ARCHETYPE_IDS:
            raise ValueError(
                f"Invalid secondary_archetype: '{secondary_archetype}'. Must be one of {ARCHETYPE_IDS} or None"
            )
        if secondary_similarity is not None and not (-3.0 <= secondary_similarity <= 3.0):
            raise ValueError(
                f"Invalid secondary_similarity: {secondary_similarity}. Must be between -3.0 and 3.0"
            )

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO archetype_results
                    (user_id, onboarding_pathway, trait_scores_json,
                     primary_archetype, primary_similarity,
                     secondary_archetype, secondary_similarity, blend_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    onboarding_pathway,
                    trait_scores_json,
                    primary_archetype,
                    primary_similarity,
                    secondary_archetype,
                    secondary_similarity,
                    int(blend_active),
                ),
            )
            row = connection.execute(
                """
                SELECT id, user_id, onboarding_pathway, trait_scores_json,
                       primary_archetype, primary_similarity,
                       secondary_archetype, secondary_similarity,
                       blend_active, created_at
                FROM archetype_results
                WHERE id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
            connection.commit()

        record = self._map_row(row)
        logger.debug(
            "Created archetype result record_id=%s user_id=%s primary=%s",
            record.id,
            record.user_id,
            record.primary_archetype,
        )
        return record

    def find_latest_by_user_id(self, user_id: int) -> ArchetypeResultRecord | None:
        """Fetch the most recent archetype result for a user."""
        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT id, user_id, onboarding_pathway, trait_scores_json,
                       primary_archetype, primary_similarity,
                       secondary_archetype, secondary_similarity,
                       blend_active, created_at
                FROM archetype_results
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()

        if row is None:
            logger.debug("Archetype result lookup missed user_id=%s", user_id)
            return None
        record = self._map_row(row)
        logger.debug(
            "Archetype result lookup hit record_id=%s user_id=%s primary=%s",
            record.id,
            record.user_id,
            record.primary_archetype,
        )
        return record

    def list_by_user_id(
        self, user_id: int, *, limit: int | None = None
    ) -> list[ArchetypeResultRecord]:
        """Fetch archetype results for a user, newest first."""
        query = """
            SELECT id, user_id, onboarding_pathway, trait_scores_json,
                   primary_archetype, primary_similarity,
                   secondary_archetype, secondary_similarity,
                   blend_active, created_at
            FROM archetype_results
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
        """
        params: list[int] = [user_id]

        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        with self.database.connection() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()

        records = [self._map_row(row) for row in rows]
        logger.debug(
            "Archetype result list user_id=%s count=%s",
            user_id,
            len(records),
        )
        return records
