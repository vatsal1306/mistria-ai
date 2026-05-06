"""Tests for the database schema."""

from pathlib import Path
import sys
import tempfile
import sqlite3

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.storage.database import SQLiteDatabase


def test_database_initializes_and_creates_memories_table():
    """Verify that a fresh database creates the memories table with the expected schema."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = SQLiteDatabase(str(db_path))
        db.initialize()

        with db.connection() as conn:
            # Verify the memories table exists
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memories'")
            table = cursor.fetchone()
            assert table is not None

            # Verify the schema has the correct columns
            cursor = conn.execute("PRAGMA table_info(memories)")
            columns = {row["name"]: row["type"] for row in cursor.fetchall()}
            
            assert columns["id"] == "INTEGER"
            assert columns["user_id"] == "INTEGER"
            assert columns["ai_companion_id"] == "INTEGER"
            assert columns["memory_type"] == "TEXT"
            assert columns["canonical_key"] == "TEXT"
            assert columns["content"] == "TEXT"
            assert columns["importance"] == "INTEGER"
            assert columns["confidence"] == "REAL"
            assert columns["status"] == "TEXT"


def test_database_memories_constraints():
    """Verify that the memories table enforces CHECK constraints."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = SQLiteDatabase(str(db_path))
        db.initialize()

        with db.connection() as conn:
            # Create a user and a companion first
            conn.execute("INSERT INTO users (email, name) VALUES ('test@example.com', 'Test User')")
            user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            conn.execute(
                """
                INSERT INTO ai_companion (user_id, title, description, gender, style, ethnicity, eye_color, hair_style, hair_color, personality, voice, connection)
                VALUES (?, 'Aria', 'Desc', 'Female', 'Anime', 'East Asian', 'Brown', 'Long', 'Black', 'Sweet', 'Soft', 'Friend')
                """, (user_id,)
            )
            companion_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Valid insert
            conn.execute(
                """
                INSERT INTO memories (user_id, ai_companion_id, memory_type, canonical_key, content, importance, confidence)
                VALUES (?, ?, 'fact', 'user_likes_coffee', 'User likes coffee', 1, 1.0)
                """, (user_id, companion_id)
            )

            # Invalid memory_type
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO memories (user_id, ai_companion_id, memory_type, canonical_key, content, importance, confidence)
                    VALUES (?, ?, 'invalid_type', 'key', 'content', 1, 1.0)
                    """, (user_id, companion_id)
                )

            # Invalid status
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO memories (user_id, ai_companion_id, memory_type, canonical_key, content, importance, confidence, status)
                    VALUES (?, ?, 'fact', 'key', 'content', 1, 1.0, 'invalid_status')
                    """, (user_id, companion_id)
                )
