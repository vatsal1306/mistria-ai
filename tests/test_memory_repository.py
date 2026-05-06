"""Tests for the memory repository."""

from pathlib import Path
import sys
import tempfile
import sqlite3

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.storage.database import SQLiteDatabase
from src.storage.models import MemoryRecord
from src.storage.memory_repository import SQLiteMemoryRepository
from src.storage.exceptions import RepositoryError


@pytest.fixture
def test_db():
    """Provide an initialized in-memory database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = SQLiteDatabase(str(db_path))
        db.initialize()
        yield db


@pytest.fixture
def repo(test_db):
    """Provide a SQLiteMemoryRepository connected to the test database."""
    return SQLiteMemoryRepository(test_db)


@pytest.fixture
def scoped_ids(test_db):
    """Create a user and companion to provide a valid scope."""
    with test_db.connection() as conn:
        conn.execute("INSERT INTO users (email, name) VALUES ('test@example.com', 'Test')")
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        conn.execute(
            """
            INSERT INTO ai_companion (user_id, title, description, gender, style, ethnicity, eye_color, hair_style, hair_color, personality, voice, connection)
            VALUES (?, 'Aria', 'Desc', 'Female', 'Anime', 'Asian', 'Brown', 'Long', 'Black', 'Sweet', 'Soft', 'Friend')
            """, (user_id,)
        )
        ai_companion_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        
    return user_id, ai_companion_id


def test_create_memory_and_find_by_id(repo, scoped_ids):
    user_id, ai_companion_id = scoped_ids
    
    memory = repo.create_memory(
        user_id=user_id,
        ai_companion_id=ai_companion_id,
        memory_type="fact",
        canonical_key="user_name",
        content="The user's name is Test.",
        importance=5,
        confidence=0.9,
    )
    
    assert memory.id > 0
    assert memory.canonical_key == "user_name"
    assert memory.status == "active"
    assert memory.retrieval_count == 0
    
    found = repo.find_by_id(memory.id)
    assert found is not None
    assert found.id == memory.id
    assert found.content == "The user's name is Test."


def test_list_active_for_scope_excludes_superseded(repo, scoped_ids):
    user_id, ai_companion_id = scoped_ids
    
    mem1 = repo.create_memory(user_id, ai_companion_id, "fact", "key1", "val1", 1, 1.0)
    mem2 = repo.create_memory(user_id, ai_companion_id, "fact", "key2", "val2", 2, 1.0)
    
    repo.supersede(mem1.id, None)
    
    active_memories = repo.list_active_for_scope(user_id, ai_companion_id)
    assert len(active_memories) == 1
    assert active_memories[0].id == mem2.id


def test_find_active_by_canonical_key(repo, scoped_ids):
    user_id, ai_companion_id = scoped_ids
    
    repo.create_memory(user_id, ai_companion_id, "fact", "key_active", "val", 1, 1.0)
    mem_sup = repo.create_memory(user_id, ai_companion_id, "fact", "key_sup", "val", 1, 1.0)
    repo.supersede(mem_sup.id, None)
    
    found = repo.find_active_by_canonical_key(user_id, ai_companion_id, "key_active")
    assert found is not None
    
    not_found_sup = repo.find_active_by_canonical_key(user_id, ai_companion_id, "key_sup")
    assert not_found_sup is None


def test_supersede_updates_status_and_pointer(repo, scoped_ids):
    user_id, ai_companion_id = scoped_ids
    
    mem_old = repo.create_memory(user_id, ai_companion_id, "fact", "key1", "val_old", 1, 1.0)
    mem_new = repo.create_memory(user_id, ai_companion_id, "fact", "key1", "val_new", 1, 1.0)
    
    updated_old = repo.supersede(mem_old.id, mem_new.id)
    assert updated_old.status == "superseded"
    assert updated_old.supersedes_memory_id == mem_new.id


def test_mark_retrieved_increments_count(repo, scoped_ids):
    user_id, ai_companion_id = scoped_ids
    
    memory = repo.create_memory(user_id, ai_companion_id, "fact", "key1", "val", 1, 1.0)
    assert memory.retrieval_count == 0
    assert memory.last_retrieved_at is None
    
    repo.mark_retrieved(memory.id)
    
    updated = repo.find_by_id(memory.id)
    assert updated.retrieval_count == 1
    assert updated.last_retrieved_at is not None


def test_companion_isolation_across_reads(test_db, repo):
    with test_db.connection() as conn:
        conn.execute("INSERT INTO users (email, name) VALUES ('u1@a.com', 'U1'), ('u2@a.com', 'U2')")
        u1 = 1
        u2 = 2
        
        conn.execute(
            """
            INSERT INTO ai_companion (user_id, title, description, gender, style, ethnicity, eye_color, hair_style, hair_color, personality, voice, connection)
            VALUES 
            (1, 'A1', 'D', 'F', 'S', 'E', 'B', 'L', 'B', 'P', 'V', 'C'),
            (2, 'A2', 'D', 'F', 'S', 'E', 'B', 'L', 'B', 'P', 'V', 'C')
            """
        )
        c1 = 1
        c2 = 2
        conn.commit()

    repo.create_memory(u1, c1, "fact", "k1", "u1c1", 1, 1.0)
    repo.create_memory(u2, c2, "fact", "k1", "u2c2", 1, 1.0)
    
    u1c1_mems = repo.list_active_for_scope(u1, c1)
    assert len(u1c1_mems) == 1
    assert u1c1_mems[0].content == "u1c1"

    search_res = repo.keyword_search(u1, c1, "u", 10)
    assert len(search_res) == 1
    assert search_res[0].content == "u1c1"


def test_keyword_search_scopes_and_limits(repo, scoped_ids):
    user_id, ai_companion_id = scoped_ids
    
    repo.create_memory(user_id, ai_companion_id, "fact", "k1", "apple pie", 1, 1.0)
    repo.create_memory(user_id, ai_companion_id, "fact", "k2", "apple juice", 2, 1.0)
    repo.create_memory(user_id, ai_companion_id, "fact", "k3", "banana", 1, 1.0)
    mem_sup = repo.create_memory(user_id, ai_companion_id, "fact", "k4", "apple crisp", 3, 1.0)
    repo.supersede(mem_sup.id, None)
    
    results = repo.keyword_search(user_id, ai_companion_id, "apple", 10)
    assert len(results) == 2
    # Ordered by importance DESC
    assert results[0].content == "apple juice"
    assert results[1].content == "apple pie"
    
    results_limit = repo.keyword_search(user_id, ai_companion_id, "apple", 1)
    assert len(results_limit) == 1
    assert results_limit[0].content == "apple juice"
