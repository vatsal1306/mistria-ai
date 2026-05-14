"""Unit tests for the internal debug memory endpoints."""

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from unittest import mock

from main import app
from src.memory.schemas import MemoryDebugRecord
from src.storage.models import MemoryRecord, UserRecord, AICompanionRecord

@pytest.fixture
def api_client():
    return TestClient(app)

@pytest.fixture
def mock_user():
    return UserRecord(id=1, email="debug@example.com", name="Debug User", encrypted_password=None, created_at="now")

@pytest.fixture
def mock_companion():
    return AICompanionRecord(
        id=10, user_id=1, title="Debug Bot", description="desc",
        gender="F", style="R", ethnicity="E", eye_color="B",
        hair_style="S", hair_color="B", personality="P", voice="V",
        connection="C", created_at="now", updated_at="now"
    )

@pytest.mark.anyio
async def test_debug_memory_list_disabled_by_default(api_client):
    """Verify endpoint returns 404 if debug flag is disabled."""
    mock_s = mock.Mock()
    mock_s.memory.debug_endpoint_enabled = False
    with mock.patch("main.settings", new=mock_s), \
         mock.patch("main.memory_service", new=mock.Mock()):
        
        response = api_client.get("/debug/memory/test@example.com/1")
        assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.anyio
async def test_debug_memory_list_success(api_client, mock_user, mock_companion):
    """Verify memories are listed correctly for the owner."""
    mock_s = mock.Mock()
    mock_s.memory.debug_endpoint_enabled = True
    mock_s.memory.enabled = True
    with mock.patch("main.settings", new=mock_s), \
         mock.patch("main.memory_service") as mock_mem_service, \
         mock.patch("main.user_repository") as mock_user_repo, \
         mock.patch("main.ai_companion_repository") as mock_comp_repo:
        
        mock_user_repo.find_by_email.return_value = mock_user
        mock_comp_repo.find_by_id.return_value = mock_companion
        
        # Mock stored records
        record = MemoryRecord(
            id=100, user_id=1, ai_companion_id=10, 
            memory_type="fact", canonical_key="key", content="content",
            status="active", importance=3, confidence=0.9,
            created_at="2023-01-01T00:00:00", updated_at="2023-01-01T00:00:00",
            source_conversation_id=None, source_message_id=None,
            supersedes_memory_id=None, last_retrieved_at=None, retrieval_count=0
        )
        # Use AsyncMock for async service method
        mock_mem_service.list_memories = mock.AsyncMock(return_value=[record])
        
        response = api_client.get("/debug/memory/debug@example.com/10?status=active")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["user_mail_id"] == "debug@example.com"
        assert data["ai_companion_id"] == 10
        assert len(data["memories"]) == 1
        assert data["memories"][0]["id"] == 100
        assert data["memories"][0]["status"] == "active"

@pytest.mark.anyio
async def test_debug_memory_list_wrong_owner(api_client, mock_user):
    """Verify endpoint rejects requests for companions not owned by the user."""
    mock_s = mock.Mock()
    mock_s.memory.debug_endpoint_enabled = True
    mock_s.memory.enabled = True
    with mock.patch("main.settings", new=mock_s), \
         mock.patch("main.memory_service", new=mock.Mock()), \
         mock.patch("main.user_repository") as mock_user_repo, \
         mock.patch("main.ai_companion_repository") as mock_comp_repo:
        
        # Companion owned by user 999
        other_companion = AICompanionRecord(
            id=10, user_id=999, title="Other Bot", description="desc",
            gender="F", style="R", ethnicity="E", eye_color="B",
            hair_style="S", hair_color="B", personality="P", voice="V",
            connection="C", created_at="now", updated_at="now"
        )
        
        mock_user_repo.find_by_email.return_value = mock_user
        mock_comp_repo.find_by_id.return_value = other_companion
        
        response = api_client.get("/debug/memory/debug@example.com/10")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not owned by user" in response.json()["detail"]


@pytest.mark.anyio
async def test_debug_memory_list_filters(api_client, mock_user, mock_companion):
    """Verify filters are passed correctly to the service."""
    mock_s = mock.Mock()
    mock_s.memory.debug_endpoint_enabled = True
    mock_s.memory.enabled = True
    with mock.patch("main.settings", new=mock_s), \
         mock.patch("main.memory_service") as mock_mem_service, \
         mock.patch("main.user_repository") as mock_user_repo, \
         mock.patch("main.ai_companion_repository") as mock_comp_repo:
        
        mock_user_repo.find_by_email.return_value = mock_user
        mock_comp_repo.find_by_id.return_value = mock_companion
        mock_mem_service.list_memories = mock.AsyncMock(return_value=[])
        
        response = api_client.get("/debug/memory/debug@example.com/10?status=all&memory_type=fact&limit=10")
        
        assert response.status_code == status.HTTP_200_OK
        mock_mem_service.list_memories.assert_called_once_with(
            user_id=1,
            ai_companion_id=10,
            status="all",
            memory_type="fact",
            limit=10
        )
