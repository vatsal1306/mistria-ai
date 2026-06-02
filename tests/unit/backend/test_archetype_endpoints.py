"""Unit tests for archetype endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.storage.database import SQLiteDatabase
from src.storage.repositories import SQLiteUserRepository


@pytest.fixture
def api_client() -> TestClient:
    """Provides a TestClient for FastAPI."""
    from main import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def override_main_repos(sqlite_db: SQLiteDatabase, monkeypatch: pytest.MonkeyPatch):
    """Override main.py repositories to use the test database."""
    import main
    from src.storage.archetype_repository import SQLiteArchetypeResultRepository
    
    user_repo = SQLiteUserRepository(sqlite_db)
    archetype_repo = SQLiteArchetypeResultRepository(sqlite_db)
    monkeypatch.setattr(main, "user_repository", user_repo)
    monkeypatch.setattr(main, "archetype_repository", archetype_repo)


@pytest.fixture
def setup_user(sqlite_db: SQLiteDatabase) -> str:
    """Create a user in the test database and return its email."""
    email = "test.archetype@example.com"
    repo = SQLiteUserRepository(sqlite_db)
    repo.create_user(email, "Test User", None)
    return email


class TestSlowBurnScoreEndpoint:
    """Tests for POST /archetype/slow-burn/score."""

    def test_score_slow_burn_success(self, api_client, setup_user):
        """Valid trait vector must return a successful scoring result."""
        payload = {
            "user_mail_id": setup_user,
            "trait_scores": {
                "power": 4.0,
                "pace": 2.0,
                "intensity": 5.0,
                "depth": 3.0,
                "soft": 1.0,
                "freedom": 5.0,
                "sharp": 4.0,
            }
        }
        response = api_client.post("/archetype/slow-burn/score", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["user_mail_id"] == setup_user
        assert data["onboarding_pathway"] == "slow_burn"
        assert "primary_archetype" in data
        assert "primary_similarity" in data
        assert "blend_active" in data
        assert "trait_scores" in data
        assert data["trait_scores"]["power"] == 4.0
        assert "created_at" in data

    def test_score_slow_burn_user_not_found(self, api_client):
        """Request for unknown user must return 404."""
        payload = {
            "user_mail_id": "unknown@example.com",
            "trait_scores": {
                "power": 4.0,
                "pace": 2.0,
                "intensity": 5.0,
                "depth": 3.0,
                "soft": 1.0,
                "freedom": 5.0,
                "sharp": 4.0,
            }
        }
        response = api_client.post("/archetype/slow-burn/score", json=payload)
        
        assert response.status_code == 404
        assert response.json()["detail"] == "User not found."

    def test_score_slow_burn_invalid_traits_missing(self, api_client, setup_user):
        """Missing trait keys must fail FastAPI Pydantic validation (422)."""
        payload = {
            "user_mail_id": setup_user,
            "trait_scores": {
                "power": 4.0,
                # missing other keys
            }
        }
        response = api_client.post("/archetype/slow-burn/score", json=payload)
        assert response.status_code == 422

    def test_score_slow_burn_invalid_traits_extra(self, api_client, setup_user):
        """Extra trait keys must fail FastAPI Pydantic validation (422)."""
        payload = {
            "user_mail_id": setup_user,
            "trait_scores": {
                "power": 4.0,
                "pace": 2.0,
                "intensity": 5.0,
                "depth": 3.0,
                "soft": 1.0,
                "freedom": 5.0,
                "sharp": 4.0,
                "extra_key": 10.0,
            }
        }
        response = api_client.post("/archetype/slow-burn/score", json=payload)
        assert response.status_code == 422

    def test_score_slow_burn_invalid_traits_out_of_bounds(self, api_client, setup_user):
        """Trait scores out of bounds must fail FastAPI Pydantic validation (422)."""
        payload = {
            "user_mail_id": setup_user,
            "trait_scores": {
                "power": 100.0,
                "pace": 2.0,
                "intensity": 5.0,
                "depth": 3.0,
                "soft": 1.0,
                "freedom": 5.0,
                "sharp": 4.0,
            }
        }
        response = api_client.post("/archetype/slow-burn/score", json=payload)
        assert response.status_code == 422

    def test_score_slow_burn_all_zero_traits(self, api_client, setup_user):
        """All-zero trait vectors must raise ZeroVectorError -> 422 via exception handler."""
        payload = {
            "user_mail_id": setup_user,
            "trait_scores": {
                "power": 0.0,
                "pace": 0.0,
                "intensity": 0.0,
                "depth": 0.0,
                "soft": 0.0,
                "freedom": 0.0,
                "sharp": 0.0,
            }
        }
        response = api_client.post("/archetype/slow-burn/score", json=payload)
        assert response.status_code == 422
        assert "all-zero trait vector" in response.json()["detail"]


class TestGetLatestArchetypeEndpoint:
    """Tests for GET /archetype/latest/{user_mail_id}."""

    def test_get_latest_success(self, api_client, setup_user):
        """Must return the latest archetype result for the user."""
        # First create a result
        payload = {
            "user_mail_id": setup_user,
            "trait_scores": {
                "power": 4.0,
                "pace": 2.0,
                "intensity": 5.0,
                "depth": 3.0,
                "soft": 1.0,
                "freedom": 5.0,
                "sharp": 4.0,
            }
        }
        api_client.post("/archetype/slow-burn/score", json=payload)

        # Now fetch it
        response = api_client.get(f"/archetype/latest/{setup_user}")
        assert response.status_code == 200
        data = response.json()
        assert data["user_mail_id"] == setup_user
        assert data["onboarding_pathway"] == "slow_burn"
        assert "primary_archetype" in data
        assert data["trait_scores"]["power"] == 4.0

    def test_get_latest_user_not_found(self, api_client):
        """Must return 404 if the user does not exist."""
        response = api_client.get("/archetype/latest/unknown@example.com")
        assert response.status_code == 404
        assert response.json()["detail"] == "User not found."

    def test_get_latest_no_archetype(self, api_client, setup_user):
        """Must return 404 if the user exists but has no archetype result."""
        response = api_client.get(f"/archetype/latest/{setup_user}")
        assert response.status_code == 404
        assert response.json()["detail"] == "No archetype result found for user."
