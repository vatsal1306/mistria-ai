"""Unit tests for FastAPI entrypoint handlers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest
from fastapi.testclient import TestClient

import main
from src.auth.exceptions import UserAlreadyExistsError
from src.backend.exceptions import ConfigurationError
from src.backend.schemas import UserCreateRequest
from src.companion.exceptions import CompanionNotFoundError
from src.companion.schemas import (
    AICompanionCreateRequest,
    AICompanionGenerateRequest,
    UserCompanionUpsertRequest,
)
from src.storage.models import UserRecord


class _UserRepository:
    def __init__(self, user: UserRecord | None = None):
        self.user = user
        self.created = []

    def find_by_email(self, email: str):
        return self.user if self.user and self.user.email == email else None

    def create_user(self, **kwargs):
        self.created.append(kwargs)
        return UserRecord(
            id=22,
            email=kwargs["email"],
            name=kwargs["name"],
            encrypted_password=kwargs["encrypted_password"],
            created_at="2026-04-24 09:00:00",
        )


@pytest.mark.anyio
async def test_exception_handlers_return_expected_status_codes():
    configuration = await main.configuration_error_handler(None, ConfigurationError("bad config"))
    not_found = await main.companion_not_found_handler(None, CompanionNotFoundError("missing"))
    duplicate = await main.user_already_exists_handler(None, UserAlreadyExistsError("duplicate"))

    assert configuration.status_code == 500
    assert not_found.status_code == 404
    assert duplicate.status_code == 409


@pytest.mark.anyio
async def test_info_and_health_reflect_runtime_state(monkeypatch):
    runtime = SimpleNamespace(
        backend_name="mock",
        model_name="test-model",
        is_ready=True,
        startup_stage="ready",
        startup_detail="ok",
        startup_elapsed_seconds=1.2,
        startup_error=None,
    )
    monkeypatch.setattr(main, "runtime", runtime)

    info = await main.info()
    health = await main.health()

    assert info["backend"] == "mock"
    assert health.status == "ok"
    assert health.engine_ready is True

    runtime.is_ready = False
    degraded = await main.health()
    assert degraded.status == "degraded"


def test_create_user_creates_new_user(monkeypatch):
    repository = _UserRepository()
    monkeypatch.setattr(main, "user_repository", repository)

    response = main.create_user(UserCreateRequest(email="new@example.com", name="New User"))

    assert response.user_id == 22
    assert response.email == "new@example.com"
    assert repository.created == [
        {"email": "new@example.com", "name": "New User", "encrypted_password": None}
    ]


def test_create_user_rejects_duplicates(monkeypatch, sample_user):
    monkeypatch.setattr(main, "user_repository", _UserRepository(sample_user))

    with pytest.raises(UserAlreadyExistsError):
        main.create_user(UserCreateRequest(email=sample_user.email, name=sample_user.name))


@pytest.mark.anyio
async def test_lifespan_initializes_and_shutdowns_shared_resources_memory_disabled(monkeypatch):
    database = mock.Mock()
    runtime = mock.Mock()
    runtime.backend_name = "mock"
    runtime.is_ready = True
    runtime.startup_stage = "ready"
    runtime.startup = mock.AsyncMock()
    runtime.shutdown = mock.AsyncMock()
    
    mock_settings = mock.Mock()
    mock_settings.memory.enabled = False
    
    monkeypatch.setattr(main, "database", database)
    monkeypatch.setattr(main, "runtime", runtime)
    monkeypatch.setattr(main, "settings", mock_settings)
    monkeypatch.setattr(main, "extraction_worker", None)

    async with main.lifespan(main.app):
        database.initialize.assert_called_once()
        runtime.startup.assert_awaited_once()

    runtime.shutdown.assert_awaited_once()


@pytest.mark.anyio
async def test_lifespan_initializes_memory_components_when_enabled(monkeypatch):
    database = mock.Mock()
    runtime = mock.Mock()
    runtime.backend_name = "mock"
    runtime.is_ready = True
    runtime.startup_stage = "ready"
    runtime.startup = mock.AsyncMock()
    runtime.shutdown = mock.AsyncMock()
    
    vector_store = mock.Mock()
    embedding_provider = mock.Mock()
    embedding_provider.get_dimension.return_value = 384
    worker = mock.Mock()
    worker.shutdown = mock.AsyncMock()
    
    mock_settings = mock.Mock()
    mock_settings.memory.enabled = True
    
    monkeypatch.setattr(main, "database", database)
    monkeypatch.setattr(main, "runtime", runtime)
    monkeypatch.setattr(main, "settings", mock_settings)
    monkeypatch.setattr(main, "memory_vector_store", vector_store)
    monkeypatch.setattr(main, "memory_embedding_provider", embedding_provider)
    monkeypatch.setattr(main, "extraction_worker", worker)

    async with main.lifespan(main.app):
        database.initialize.assert_called_once()
        runtime.startup.assert_awaited_once()
        embedding_provider.get_dimension.assert_called_once()
        vector_store.bootstrap_collection.assert_called_once_with(384)

    runtime.shutdown.assert_awaited_once()
    worker.shutdown.assert_awaited_once()


@pytest.mark.anyio
async def test_chat_socket_delegates_to_websocket_handler(monkeypatch):
    handler = mock.Mock()
    handler.handle = mock.AsyncMock()
    monkeypatch.setattr(main, "websocket_handler", handler)
    websocket = object()

    await main.chat_socket(websocket)

    handler.handle.assert_awaited_once_with(websocket)


@pytest.mark.anyio
async def test_companion_endpoints_delegate_to_service(monkeypatch):
    upsert_response = SimpleNamespace(user_mail_id="user@example.com")
    create_response = SimpleNamespace(ai_companion_id=4)
    generate_response = SimpleNamespace(title="Mira")
    service = mock.Mock()
    service.upsert_user_companion = mock.AsyncMock(return_value=upsert_response)
    service.get_user_companion.return_value = "user-companion"
    service.create_ai_companion = mock.AsyncMock(return_value=create_response)
    service.generate_ai_companion = mock.AsyncMock(return_value=generate_response)
    service.list_ai_companions.return_value = ["one"]
    service.get_ai_companion.return_value = "ai-companion"
    monkeypatch.setattr(main, "companion_service", service)

    upsert_payload = UserCompanionUpsertRequest(
        user_mail_id="user@example.com",
        intent_type="easy",
        dominance_mode="user_leads",
        intensity_level="show_me",
        silence_response="wait",
        secret_desire="running",
    )
    create_payload = AICompanionCreateRequest(
        user_mail_id="user@example.com",
        title="Mira",
        description="A focused companion.",
        gender="Female",
        style="Anime",
        ethnicity="East Asian",
        eyeColor="Brown",
        hairStyle="Long",
        hairColor="Black",
        personality="Playful",
        voice="Calm",
        connection="New Encounter",
    )
    generate_payload = AICompanionGenerateRequest(
        gender="Female",
        style="Anime",
        ethnicity="East Asian",
        eyeColor="Brown",
        hairStyle="Long",
        hairColor="Black",
        personality="Playful",
        voice="Calm",
        connection="New Encounter",
    )

    assert await main.upsert_user_companion(upsert_payload) is upsert_response
    assert main.get_user_companion("user@example.com") == "user-companion"
    assert await main.create_ai_companion(create_payload) is create_response
    assert await main.generate_ai_companion(generate_payload) is generate_response
    assert main.list_ai_companions("user@example.com") == ["one"]
    assert main.get_ai_companion(3) == "ai-companion"


@pytest.mark.anyio
async def test_debug_memory_retrieve_returns_404_when_disabled(monkeypatch):
    mock_settings = mock.Mock()
    mock_settings.memory.debug_endpoint_enabled = False
    monkeypatch.setattr(main, "settings", mock_settings)
    monkeypatch.setattr(main, "memory_service", mock.Mock())

    from src.memory.schemas import DebugMemoryRetrieveRequest
    payload = DebugMemoryRetrieveRequest(user_mail_id="user@example.com", ai_companion_id=1, user_message="hello")

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await main.debug_memory_retrieve(payload)
    
    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_debug_memory_retrieve_returns_404_when_user_not_found(monkeypatch):
    mock_settings = mock.Mock()
    mock_settings.memory.debug_endpoint_enabled = True
    monkeypatch.setattr(main, "settings", mock_settings)
    monkeypatch.setattr(main, "memory_service", mock.Mock())

    user_repo = mock.Mock()
    user_repo.find_by_email.return_value = None
    monkeypatch.setattr(main, "user_repository", user_repo)

    from src.memory.schemas import DebugMemoryRetrieveRequest
    payload = DebugMemoryRetrieveRequest(user_mail_id="user@example.com", ai_companion_id=1, user_message="hello")

    with pytest.raises(CompanionNotFoundError, match="User not found"):
        await main.debug_memory_retrieve(payload)


@pytest.mark.anyio
async def test_debug_memory_retrieve_returns_404_when_companion_not_found(monkeypatch, sample_user):
    mock_settings = mock.Mock()
    mock_settings.memory.debug_endpoint_enabled = True
    monkeypatch.setattr(main, "settings", mock_settings)
    monkeypatch.setattr(main, "memory_service", mock.Mock())

    user_repo = mock.Mock()
    user_repo.find_by_email.return_value = sample_user
    monkeypatch.setattr(main, "user_repository", user_repo)

    companion_repo = mock.Mock()
    companion_repo.get_latest_ai_companion.return_value = None
    monkeypatch.setattr(main, "ai_companion_repository", companion_repo)

    from src.memory.schemas import DebugMemoryRetrieveRequest
    payload = DebugMemoryRetrieveRequest(user_mail_id=sample_user.email, ai_companion_id=99, user_message="hello")

    with pytest.raises(CompanionNotFoundError, match="Companion 99 not found"):
        await main.debug_memory_retrieve(payload)


@pytest.mark.anyio
async def test_debug_memory_retrieve_success(monkeypatch, sample_user):
    mock_settings = mock.Mock()
    mock_settings.memory.debug_endpoint_enabled = True
    mock_settings.memory.retrieval_top_k = 5
    monkeypatch.setattr(main, "settings", mock_settings)

    user_repo = mock.Mock()
    user_repo.find_by_email.return_value = sample_user
    monkeypatch.setattr(main, "user_repository", user_repo)

    companion_repo = mock.Mock()
    mock_companion = mock.Mock(id=99)
    companion_repo.get_latest_ai_companion.return_value = mock_companion
    monkeypatch.setattr(main, "ai_companion_repository", companion_repo)

    memory_service = mock.Mock()
    from src.memory.schemas import MemorySearchResult
    mock_result = MemorySearchResult(
        memory_id=1, memory_type="fact", content="test", canonical_key="key", score=0.9, source="semantic"
    )
    memory_service.retrieve_memories = mock.AsyncMock(return_value=[mock_result])
    monkeypatch.setattr(main, "memory_service", memory_service)

    from src.memory.schemas import DebugMemoryRetrieveRequest
    payload = DebugMemoryRetrieveRequest(user_mail_id=sample_user.email, ai_companion_id=99, user_message="hello")
    response = await main.debug_memory_retrieve(payload)

    assert response.user_mail_id == sample_user.email
    assert response.ai_companion_id == 99
    assert len(response.memories) == 1
    assert response.memories[0].memory_id == 1
    memory_service.retrieve_memories.assert_awaited_once_with(
        user_id=sample_user.id, ai_companion_id=mock_companion.id, query_text="hello", limit=5
    )
