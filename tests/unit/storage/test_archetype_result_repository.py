"""Unit tests for archetype result persistence."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.storage.database import SQLiteDatabase
from src.storage.models import ArchetypeResultRecord
from src.storage.repositories import SQLiteArchetypeResultRepository


@pytest.fixture()
def db() -> SQLiteDatabase:
    """Yield an initialized in-memory-like SQLite database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        database = SQLiteDatabase(str(db_path))
        database.initialize()
        yield database


@pytest.fixture()
def repo(db: SQLiteDatabase) -> SQLiteArchetypeResultRepository:
    """Return an archetype result repository backed by the test database."""
    return SQLiteArchetypeResultRepository(db)


@pytest.fixture()
def user_id(db: SQLiteDatabase) -> int:
    """Insert a test user and return its id."""
    with db.connection() as conn:
        conn.execute(
            "INSERT INTO users (email, name) VALUES ('slow@example.com', 'Slow Burn User')"
        )
        uid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
    return uid


SAMPLE_TRAITS = json.dumps({
    "power": 3.0,
    "pace": 2.0,
    "intensity": 5.0,
    "depth": 3.0,
    "soft": 1.0,
    "freedom": 1.0,
    "sharp": 4.0,
})


class TestArchetypeResultTableCreation:
    """Verify that database initialization creates the archetype_results table."""

    def test_table_exists(self, db: SQLiteDatabase):
        """The archetype_results table must exist after initialization."""
        with db.connection() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='archetype_results'"
            ).fetchone()
        assert row is not None

    def test_table_has_expected_columns(self, db: SQLiteDatabase):
        """Verify the schema has all required columns."""
        with db.connection() as conn:
            columns = {
                row["name"]: row["type"]
                for row in conn.execute("PRAGMA table_info(archetype_results)").fetchall()
            }

        assert columns["id"] == "INTEGER"
        assert columns["user_id"] == "INTEGER"
        assert columns["onboarding_pathway"] == "TEXT"
        assert columns["trait_scores_json"] == "TEXT"
        assert columns["primary_archetype"] == "TEXT"
        assert columns["primary_similarity"] == "REAL"
        assert columns["secondary_archetype"] == "TEXT"
        assert columns["secondary_similarity"] == "REAL"
        assert columns["blend_active"] == "INTEGER"
        assert columns["created_at"] == "TEXT"

    def test_index_exists(self, db: SQLiteDatabase):
        """The covering index for latest-per-user lookups must exist."""
        with db.connection() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='index' AND name='idx_archetype_results_user_latest'"
            ).fetchone()
        assert row is not None


class TestArchetypeResultCreate:
    """Verify inserting archetype scoring submissions."""

    def test_create_returns_record(self, repo, user_id):
        """create() must return a fully populated ArchetypeResultRecord."""
        record = repo.create(
            user_id=user_id,
            onboarding_pathway="slow_burn",
            trait_scores_json=SAMPLE_TRAITS,
            primary_archetype="rebel",
            primary_similarity=0.94,
            secondary_archetype="muse",
            secondary_similarity=0.88,
            blend_active=True,
        )

        assert isinstance(record, ArchetypeResultRecord)
        assert record.id is not None
        assert record.user_id == user_id
        assert record.onboarding_pathway == "slow_burn"
        assert record.primary_archetype == "rebel"
        assert record.primary_similarity == pytest.approx(0.94)
        assert record.secondary_archetype == "muse"
        assert record.secondary_similarity == pytest.approx(0.88)
        assert record.blend_active is True
        assert record.created_at is not None

    def test_create_without_secondary(self, repo, user_id):
        """Submissions with no blend should store NULL for secondary fields."""
        record = repo.create(
            user_id=user_id,
            onboarding_pathway="slow_burn",
            trait_scores_json=SAMPLE_TRAITS,
            primary_archetype="soulmate",
            primary_similarity=0.97,
            secondary_archetype=None,
            secondary_similarity=None,
            blend_active=False,
        )

        assert record.secondary_archetype is None
        assert record.secondary_similarity is None
        assert record.blend_active is False

    def test_trait_scores_json_roundtrips(self, repo, user_id):
        """The trait scores JSON must survive storage and retrieval."""
        record = repo.create(
            user_id=user_id,
            onboarding_pathway="slow_burn",
            trait_scores_json=SAMPLE_TRAITS,
            primary_archetype="rebel",
            primary_similarity=0.94,
            secondary_archetype=None,
            secondary_similarity=None,
            blend_active=False,
        )

        parsed = json.loads(record.trait_scores_json)
        assert parsed["power"] == 3.0
        assert parsed["sharp"] == 4.0

    def test_does_not_mutate_companion_records(self, db, repo, user_id):
        """Archetype submissions must not affect user_companion rows."""
        with db.connection() as conn:
            before = conn.execute(
                "SELECT COUNT(*) FROM user_companion"
            ).fetchone()[0]

        repo.create(
            user_id=user_id,
            onboarding_pathway="slow_burn",
            trait_scores_json=SAMPLE_TRAITS,
            primary_archetype="rebel",
            primary_similarity=0.94,
            secondary_archetype=None,
            secondary_similarity=None,
            blend_active=False,
        )

        with db.connection() as conn:
            after = conn.execute(
                "SELECT COUNT(*) FROM user_companion"
            ).fetchone()[0]

        assert after == before


class TestArchetypeResultMultipleSubmissions:
    """Verify multiple submissions per user are supported."""

    def test_allows_multiple_per_user(self, repo, user_id):
        """Multiple archetype submissions for the same user must all persist."""
        for archetype in ("soulmate", "protector", "rebel"):
            repo.create(
                user_id=user_id,
                onboarding_pathway="slow_burn",
                trait_scores_json=SAMPLE_TRAITS,
                primary_archetype=archetype,
                primary_similarity=0.90,
                secondary_archetype=None,
                secondary_similarity=None,
                blend_active=False,
            )

        records = repo.find_all_by_user_id(user_id)
        assert len(records) == 3

    def test_latest_is_identifiable(self, repo, user_id):
        """The most recent submission must be returned by find_latest_by_user_id."""
        repo.create(
            user_id=user_id,
            onboarding_pathway="slow_burn",
            trait_scores_json=SAMPLE_TRAITS,
            primary_archetype="soulmate",
            primary_similarity=0.90,
            secondary_archetype=None,
            secondary_similarity=None,
            blend_active=False,
        )
        repo.create(
            user_id=user_id,
            onboarding_pathway="slow_burn",
            trait_scores_json=SAMPLE_TRAITS,
            primary_archetype="rebel",
            primary_similarity=0.95,
            secondary_archetype=None,
            secondary_similarity=None,
            blend_active=False,
        )

        latest = repo.find_latest_by_user_id(user_id)
        assert latest is not None
        assert latest.primary_archetype == "rebel"


class TestArchetypeResultLookup:
    """Verify lookup methods."""

    def test_find_latest_returns_none_for_unknown_user(self, repo):
        """No record for an unknown user must return None."""
        assert repo.find_latest_by_user_id(999999) is None

    def test_find_all_returns_empty_for_unknown_user(self, repo):
        """No records for an unknown user must return an empty list."""
        assert repo.find_all_by_user_id(999999) == []

    def test_find_all_ordered_newest_first(self, repo, user_id):
        """Results must be ordered newest first."""
        for archetype in ("soulmate", "protector", "rebel"):
            repo.create(
                user_id=user_id,
                onboarding_pathway="slow_burn",
                trait_scores_json=SAMPLE_TRAITS,
                primary_archetype=archetype,
                primary_similarity=0.90,
                secondary_archetype=None,
                secondary_similarity=None,
                blend_active=False,
            )

        records = repo.find_all_by_user_id(user_id)
        ids = [r.id for r in records]
        assert ids == sorted(ids, reverse=True)


class TestIntenseHeatNotRequired:
    """Verify Intense Heat users are not forced to have an archetype record."""

    def test_no_archetype_required_for_user(self, db):
        """A user can exist without any archetype_results rows."""
        with db.connection() as conn:
            conn.execute(
                "INSERT INTO users (email, name) VALUES ('intense@example.com', 'Intense Heat User')"
            )
            uid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.commit()

        repo = SQLiteArchetypeResultRepository(db)
        assert repo.find_latest_by_user_id(uid) is None
        assert repo.find_all_by_user_id(uid) == []


class TestArchetypeResultConstraintsAndValidation:
    """Verify CHECK constraints and repository validation rules."""

    def test_repo_validates_primary_archetype(self, repo, user_id):
        """Repository must reject invalid primary archetype ID with ValueError."""
        with pytest.raises(ValueError, match="Invalid primary_archetype"):
            repo.create(
                user_id=user_id,
                onboarding_pathway="slow_burn",
                trait_scores_json=SAMPLE_TRAITS,
                primary_archetype="not-real",
                primary_similarity=0.95,
                secondary_archetype=None,
                secondary_similarity=None,
                blend_active=False,
            )

    def test_repo_validates_secondary_archetype(self, repo, user_id):
        """Repository must reject invalid secondary archetype ID with ValueError."""
        with pytest.raises(ValueError, match="Invalid secondary_archetype"):
            repo.create(
                user_id=user_id,
                onboarding_pathway="slow_burn",
                trait_scores_json=SAMPLE_TRAITS,
                primary_archetype="soulmate",
                primary_similarity=0.95,
                secondary_archetype="not-real-secondary",
                secondary_similarity=0.88,
                blend_active=True,
            )

    def test_repo_validates_primary_similarity_range(self, repo, user_id):
        """Repository must reject primary_similarity outside [-3.0, 3.0] with ValueError."""
        with pytest.raises(ValueError, match="Invalid primary_similarity"):
            repo.create(
                user_id=user_id,
                onboarding_pathway="slow_burn",
                trait_scores_json=SAMPLE_TRAITS,
                primary_archetype="soulmate",
                primary_similarity=4.0,
                secondary_archetype=None,
                secondary_similarity=None,
                blend_active=False,
            )
        with pytest.raises(ValueError, match="Invalid primary_similarity"):
            repo.create(
                user_id=user_id,
                onboarding_pathway="slow_burn",
                trait_scores_json=SAMPLE_TRAITS,
                primary_archetype="soulmate",
                primary_similarity=-3.1,
                secondary_archetype=None,
                secondary_similarity=None,
                blend_active=False,
            )

    def test_repo_validates_secondary_similarity_range(self, repo, user_id):
        """Repository must reject secondary_similarity outside [-3.0, 3.0] with ValueError."""
        with pytest.raises(ValueError, match="Invalid secondary_similarity"):
            repo.create(
                user_id=user_id,
                onboarding_pathway="slow_burn",
                trait_scores_json=SAMPLE_TRAITS,
                primary_archetype="soulmate",
                primary_similarity=0.95,
                secondary_archetype="devotee",
                secondary_similarity=3.5,
                blend_active=True,
            )
        with pytest.raises(ValueError, match="Invalid secondary_similarity"):
            repo.create(
                user_id=user_id,
                onboarding_pathway="slow_burn",
                trait_scores_json=SAMPLE_TRAITS,
                primary_archetype="soulmate",
                primary_similarity=0.95,
                secondary_archetype="devotee",
                secondary_similarity=-3.2,
                blend_active=True,
            )

    def test_db_enforces_primary_archetype_check(self, db, user_id):
        """SQLite must raise IntegrityError for invalid primary_archetype."""
        with db.connection() as conn:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO archetype_results
                        (user_id, trait_scores_json, primary_archetype, primary_similarity, blend_active)
                    VALUES (?, ?, 'not-real', 0.95, 0)
                    """,
                    (user_id, SAMPLE_TRAITS),
                )

    def test_db_enforces_secondary_archetype_check(self, db, user_id):
        """SQLite must raise IntegrityError for invalid secondary_archetype."""
        with db.connection() as conn:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO archetype_results
                        (user_id, trait_scores_json, primary_archetype, primary_similarity, secondary_archetype, blend_active)
                    VALUES (?, ?, 'soulmate', 0.95, 'not-real', 0)
                    """,
                    (user_id, SAMPLE_TRAITS),
                )

    def test_db_enforces_primary_similarity_range_check(self, db, user_id):
        """SQLite must raise IntegrityError for primary_similarity outside [-3.0, 3.0]."""
        with db.connection() as conn:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO archetype_results
                        (user_id, trait_scores_json, primary_archetype, primary_similarity, blend_active)
                    VALUES (?, ?, 'soulmate', 3.5, 0)
                    """,
                    (user_id, SAMPLE_TRAITS),
                )
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO archetype_results
                        (user_id, trait_scores_json, primary_archetype, primary_similarity, blend_active)
                    VALUES (?, ?, 'soulmate', -3.5, 0)
                    """,
                    (user_id, SAMPLE_TRAITS),
                )

    def test_db_enforces_secondary_similarity_range_check(self, db, user_id):
        """SQLite must raise IntegrityError for secondary_similarity outside [-3.0, 3.0]."""
        with db.connection() as conn:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO archetype_results
                        (user_id, trait_scores_json, primary_archetype, primary_similarity, secondary_archetype, secondary_similarity, blend_active)
                    VALUES (?, ?, 'soulmate', 0.95, 'devotee', 3.5, 1)
                    """,
                    (user_id, SAMPLE_TRAITS),
                )
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO archetype_results
                        (user_id, trait_scores_json, primary_archetype, primary_similarity, secondary_archetype, secondary_similarity, blend_active)
                    VALUES (?, ?, 'soulmate', 0.95, 'devotee', -3.5, 1)
                    """,
                    (user_id, SAMPLE_TRAITS),
                )

    def test_db_enforces_blend_active_check(self, db, user_id):
        """SQLite must raise IntegrityError for blend_active outside 0/1."""
        with db.connection() as conn:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO archetype_results
                        (user_id, trait_scores_json, primary_archetype, primary_similarity, blend_active)
                    VALUES (?, ?, 'soulmate', 0.95, 2)
                    """,
                    (user_id, SAMPLE_TRAITS),
                )
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO archetype_results
                        (user_id, trait_scores_json, primary_archetype, primary_similarity, blend_active)
                    VALUES (?, ?, 'soulmate', 0.95, -1)
                    """,
                    (user_id, SAMPLE_TRAITS),
                )

