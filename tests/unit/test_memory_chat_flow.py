"""Integration smoke test for memory persistence and isolation."""

import json
import asyncio
from unittest import mock

import pytest
from fastapi.testclient import TestClient

import main
from src.backend.schemas import UserCreateRequest
from src.companion.schemas import (
    AICompanionCreateRequest,
    UserCompanionUpsertRequest,
)
from src.memory.embeddings import BaseEmbeddingProvider
from src.memory.vector_store import BaseVectorStore, VectorStoreResult
from src.storage.conversation_store import ConversationSnapshot


class MockVectorStore(BaseVectorStore):
    def __init__(self):
        self.vectors = {}

    def bootstrap_collection(self, dimension: int) -> None:
        pass

    def upsert_memory(
        self,
        memory_id: int,
        user_id: int,
        ai_companion_id: int,
        memory_type: str,
        canonical_key: str,
        status: str,
        vector: list[float],
    ) -> None:
        self.vectors[memory_id] = {
            "user_id": user_id,
            "ai_companion_id": ai_companion_id,
            "memory_type": memory_type,
            "canonical_key": canonical_key,
            "status": status,
            "vector": vector,
        }

    def delete_memory(self, memory_id: int) -> None:
        self.vectors.pop(memory_id, None)

    def search(
        self,
        user_id: int,
        ai_companion_id: int,
        query_vector: list[float],
        limit: int,
    ) -> list[VectorStoreResult]:
        results = []
        for memory_id, data in self.vectors.items():
            if data["user_id"] == user_id and data["ai_companion_id"] == ai_companion_id and data["status"] == "active":
                # Mock a high score
                results.append(VectorStoreResult(memory_id=memory_id, score=0.9))
        return results


class MockEmbeddingProvider(BaseEmbeddingProvider):
    def get_dimension(self) -> int:
        return 384

    def embed_text(self, text: str) -> list[float]:
        return [0.1] * 384

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 384 for _ in texts]


class MockExtractionService:
    async def extract_memories(
        self,
        user_id: int,
        ai_companion_id: int,
        conversation_id: int,
        message_id: int,
        message_content: str,
        recent_messages=None,
        raise_on_error: bool = False,
    ):
        from src.memory.schemas import MemoryExtraction
        if "skydiving" in message_content.lower():
            return [
                MemoryExtraction(
                    should_remember=True,
                    memory_type="preference",
                    canonical_key="likes_skydiving",
                    content="User loves skydiving.",
                    importance=4,
                    confidence=0.9,
                    reason="Explicitly stated"
                )
            ]
        return []


@pytest.fixture
def mock_memory_infrastructure(monkeypatch, sqlite_db):
    from src.config import Memory
    mock_memory_settings = Memory(
        enabled=True,
        extraction_enabled=True,
        qdrant_url="mock",
        qdrant_collection="mock",
        embedding_model_name="mock"
    )
    
    vector_store = MockVectorStore()
    embedding_provider = MockEmbeddingProvider()
    
    from src.storage.memory_repository import SQLiteMemoryRepository
    memory_repo = SQLiteMemoryRepository(sqlite_db)

    from src.memory.service import MemoryService
    memory_service = MemoryService(
        mock_memory_settings,
        memory_repo,
        vector_store,
        embedding_provider
    )
    
    from src.memory.background import MemoryExtractionWorker
    extraction_worker = MemoryExtractionWorker(MockExtractionService(), memory_service)
    
    # Patch main globals
    monkeypatch.setattr(main, "memory_service", memory_service, raising=False)
    monkeypatch.setattr(main, "extraction_worker", extraction_worker, raising=False)
    
    # Patch the chat_service which is already in main
    monkeypatch.setattr(main.chat_service, "memory_service", memory_service)
    monkeypatch.setattr(main.chat_service, "extraction_worker", extraction_worker)

    return extraction_worker


@pytest.fixture
def api_client(sqlite_db, monkeypatch):
    """Provide a TestClient connected to the real SQLite DB with mock memory."""
    import src.storage.repositories as repos
    from src.storage.conversation_store import SQLiteConversationStore
    from src.storage.service import ChatHistoryService
    from src.storage.memory_repository import SQLiteMemoryRepository
    from src.companion.service import CompanionService
    from src.backend.service import ChatService
    from src.backend.websocket_handler import WebSocketChatHandler

    # 1. Create fresh repositories using the test DB
    user_repo = repos.SQLiteUserRepository(sqlite_db)
    user_comp_repo = repos.SQLiteUserCompanionRepository(sqlite_db)
    ai_comp_repo = repos.SQLiteAICompanionRepository(sqlite_db)
    conv_repo = repos.SQLiteConversationRepository(sqlite_db)
    conv_store = SQLiteConversationStore(conv_repo)
    history_service = ChatHistoryService(conv_store)
    memory_repo = SQLiteMemoryRepository(sqlite_db)
    
    # 2. Patch main globals so routes use them
    monkeypatch.setattr(main, "database", sqlite_db)
    monkeypatch.setattr(main, "user_repository", user_repo)
    monkeypatch.setattr(main, "user_companion_repository", user_comp_repo)
    monkeypatch.setattr(main, "ai_companion_repository", ai_comp_repo)
    monkeypatch.setattr(main, "conversation_repository", conv_repo)
    monkeypatch.setattr(main, "conversation_store", conv_store)
    monkeypatch.setattr(main, "chat_history_service", history_service)
    monkeypatch.setattr(main, "memory_repository", memory_repo, raising=False)
    
    # 3. Re-instantiate services and handlers in main
    main.chat_service = ChatService(
        main.settings.chat,
        main.runtime,
        history_service,
        None, # memory_service (will be patched by other fixture)
        None  # extraction_worker (will be patched by other fixture)
    )
    
    main.companion_service = CompanionService(
        user_repo, 
        user_comp_repo, 
        ai_comp_repo, 
        main.chat_service.runtime
    )
    
    main.websocket_handler = WebSocketChatHandler(
        main.settings.api,
        main.settings.secrets,
        main.chat_service,
        history_service,
        user_repo,
        user_comp_repo,
        ai_comp_repo
    )

    # Patch the runtime stream
    async def mock_stream_response(*args, **kwargs):
        yield '{"title": "Test Title", "description": "Test Description"}'
        
    monkeypatch.setattr(main.chat_service.runtime, "stream_text", mock_stream_response)

    with TestClient(main.app) as client:
        yield client


@pytest.mark.anyio
async def test_memory_chat_flow_persistence_and_isolation(api_client, mock_memory_infrastructure, monkeypatch):
    """Test that memories survive sessions and are isolated by companion."""
    # 1. Create User John
    user_res = api_client.post("/users", json={"email": "john@example.com", "name": "John Doe"})
    assert user_res.status_code in (200, 201)
    
    # 2. Create user companion preferences
    pref_res = api_client.post("/user-companion", json={
        "user_mail_id": "john@example.com",
        "intent_type": "alive",
        "dominance_mode": "ai_leads",
        "intensity_level": "break_glass",
        "silence_response": "come_looking",
        "secret_desire": "both"
    })
    assert pref_res.status_code in (200, 201)
    
    # 3. Create Sara and Luna
    sara_res = api_client.post("/ai-companion", json={
        "user_mail_id": "john@example.com",
        "title": "Sara",
        "description": "A kind companion.",
        "gender": "Female",
        "style": "Realistic",
        "ethnicity": "East Asian",
        "eyeColor": "Green",
        "hairStyle": "Long",
        "hairColor": "Pink",
        "personality": "Caring",
        "voice": "Soft",
        "connection": "New Encounter"
    })
    assert sara_res.status_code in (200, 201), sara_res.json()
    sara_id = sara_res.json()["ai_companion_id"]
    
    luna_res = api_client.post("/ai-companion", json={
        "user_mail_id": "john@example.com",
        "title": "Luna",
        "description": "A fierce companion.",
        "gender": "Female",
        "style": "Anime",
        "ethnicity": "East Asian",
        "eyeColor": "Green",
        "hairStyle": "Long",
        "hairColor": "Pink",
        "personality": "Dominant",
        "voice": "Confident",
        "connection": "Dominant Partner"
    })
    assert luna_res.status_code in (200, 201), luna_res.json()
    luna_id = luna_res.json()["ai_companion_id"]
    
    # Spy on runtime stream to verify context
    stream_calls = []
    async def mock_stream_text(request):
        stream_calls.append(request.system_prompt)
        yield "I hear you."
    
    monkeypatch.setattr(main.chat_service.runtime, "stream_text", mock_stream_text)
    
    # 4. Chat with Sara (send explicit preference)
    ws_path = main.settings.api.websocket_path
    ws_url = f"{ws_path}?user_id=john@example.com&ai_companion_id={sara_id}&api_key=local-dev-api-key"
    
    with api_client.websocket_connect(ws_url) as ws:
        ready = ws.receive_json()
        assert ready["type"] == "ready"
        
        ws.send_json({
            "action": "chat",
            "user_id": "john@example.com",
            "ai_companion_id": sara_id,
            "user_message": "I love skydiving."
        })
        
        while True:
            resp = ws.receive_json()
            if resp["type"] == "done":
                break
                
    # 5. Wait for extraction to complete
    # The worker uses asyncio.create_task, so we just wait for its tasks
    if mock_memory_infrastructure._tasks:
        await asyncio.wait(mock_memory_infrastructure._tasks, timeout=5.0)
    
    # 6. Reconnect to Sara and verify memory injection
    stream_calls.clear()
    with api_client.websocket_connect(ws_url) as ws:
        ready = ws.receive_json()
        assert ready["type"] == "ready"
        
        ws.send_json({
            "action": "chat",
            "user_id": "john@example.com",
            "ai_companion_id": sara_id,
            "user_message": "What should we do today?"
        })
        
        while True:
            resp = ws.receive_json()
            if resp["type"] == "done":
                break
                
    # Check that system prompt injected the memory
    assert len(stream_calls) == 1
    sara_prompt = stream_calls[0]
    assert "User loves skydiving" in sara_prompt
    assert "LONG-TERM MEMORY (CURATED)" in sara_prompt
    
    # 7. Chat with Luna and verify isolation
    stream_calls.clear()
    luna_ws_url = f"{ws_path}?user_id=john@example.com&ai_companion_id={luna_id}&api_key=local-dev-api-key"
    with api_client.websocket_connect(luna_ws_url) as ws:
        ready = ws.receive_json()
        assert ready["type"] == "ready"
        
        ws.send_json({
            "action": "chat",
            "user_id": "john@example.com",
            "ai_companion_id": luna_id,
            "user_message": "Any ideas?"
        })
        
        while True:
            resp = ws.receive_json()
            if resp["type"] == "done":
                break
                
    # Luna should NOT have the skydiving memory
    assert len(stream_calls) == 1
    luna_prompt = stream_calls[0]
    assert "User loves skydiving" not in luna_prompt
