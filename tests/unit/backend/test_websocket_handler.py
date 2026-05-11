"""Unit tests for websocket request handling."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest import mock

import pytest

from src.backend.exceptions import AuthenticationError
from src.backend.websocket_handler import WebSocketChatHandler
from src.config import Api, Secrets
from src.storage.conversation_store import ConversationSnapshot


class _FakeWebSocket:
    def __init__(
        self,
        *,
        query_params: dict[str, str] | None = None,
        incoming: list[str] | None = None,
        send_raises: Exception | None = None,
    ):
        self.query_params = query_params or {}
        self.client = SimpleNamespace(host="127.0.0.1", port=12345)
        self.incoming = list(incoming or [])
        self.sent: list[dict] = []
        self.accepted = False
        self.closed_codes: list[int | None] = []
        self.send_raises = send_raises

    async def accept(self):
        self.accepted = True

    async def receive_text(self):
        if not self.incoming:
            from fastapi import WebSocketDisconnect

            raise WebSocketDisconnect()
        return self.incoming.pop(0)

    async def send_text(self, payload: str):
        if self.send_raises:
            raise self.send_raises
        self.sent.append(json.loads(payload))

    async def close(self, code: int | None = None):
        self.closed_codes.append(code)


class _Repository:
    def __init__(self, value=None):
        self.value = value

    def find_by_email(self, email: str):
        return self.value if getattr(self.value, "email", None) == email else None

    def find_by_user_id(self, user_id: int):
        return self.value if getattr(self.value, "user_id", None) == user_id else None

    def find_by_id(self, item_id: int):
        return self.value if getattr(self.value, "id", None) == item_id else None


class _HistoryService:
    def __init__(self, snapshot=None):
        self.snapshot = snapshot

    def load_latest(self, user_id: int, ai_companion_id: int):
        return self.snapshot


class _ChatService:
    def __init__(self, tokens: list[str] | None = None, exc: Exception | None = None):
        self.runtime = SimpleNamespace(backend_name="mock")
        self.tokens = tokens or []
        self.exc = exc
        self.calls = []

    async def stream_response(self, *args):
        self.calls.append(args)
        if self.exc:
            raise self.exc
        for token in self.tokens:
            yield token


def _handler(
    *,
    service=None,
    history_service=None,
    user_repo=None,
    user_companion_repo=None,
    ai_companion_repo=None,
    require_api_key: bool = False,
) -> WebSocketChatHandler:
    return WebSocketChatHandler(
        Api(require_api_key=require_api_key),
        Secrets(api_key="secret", hf_token="", auth_encryption_key="key"),
        service or _ChatService(["ok"]),
        history_service or _HistoryService(),
        user_repo or _Repository(),
        user_companion_repo or _Repository(),
        ai_companion_repo or _Repository(),
    )


def test_authorize_allows_disabled_api_key():
    websocket = _FakeWebSocket()

    _handler(require_api_key=False)._authorize(websocket)


def test_authorize_rejects_invalid_api_key():
    websocket = _FakeWebSocket(query_params={"api_key": "bad"})

    with pytest.raises(AuthenticationError):
        _handler(require_api_key=True)._authorize(websocket)


@pytest.mark.anyio
async def test_handle_sends_ready_and_closes_on_auth_failure():
    websocket = _FakeWebSocket(query_params={"api_key": "bad"})

    await _handler(require_api_key=True).handle(websocket)

    assert websocket.accepted is True
    assert websocket.sent[0]["type"] == "error"
    assert websocket.closed_codes


@pytest.mark.anyio
async def test_handle_prefetches_history_from_query_and_processes_first_message(
    sample_user,
    sample_user_companion,
    sample_ai_companion,
    sample_conversation,
):
    snapshot = ConversationSnapshot(sample_conversation, [])
    request = {
        "action": "chat",
        "user_id": sample_user.email,
        "ai_companion_id": sample_ai_companion.id,
        "user_message": "Hello",
    }
    service = _ChatService(["A", "B"])
    websocket = _FakeWebSocket(
        query_params={"user_id": sample_user.email, "ai_companion_id": str(sample_ai_companion.id)},
        incoming=[json.dumps(request)],
    )

    await _handler(
        service=service,
        history_service=_HistoryService(snapshot),
        user_repo=_Repository(sample_user),
        user_companion_repo=_Repository(sample_user_companion),
        ai_companion_repo=_Repository(sample_ai_companion),
    ).handle(websocket)

    assert [event["type"] for event in websocket.sent] == ["ready", "delta", "delta", "done"]
    assert [event.get("delta") for event in websocket.sent if event["type"] == "delta"] == ["A", "B"]
    assert service.calls[0][-1] == snapshot


@pytest.mark.anyio
async def test_handle_request_rejects_invalid_json():
    websocket = _FakeWebSocket()

    await _handler()._handle_request_message(websocket, "{bad json")

    assert websocket.sent[0]["type"] == "error"
    assert "json_invalid" in websocket.sent[0]["detail"]


@pytest.mark.anyio
async def test_handle_request_rejects_missing_user(sample_ai_companion):
    websocket = _FakeWebSocket()
    request = json.dumps(
        {"action": "chat", "user_id": "missing@example.com", "ai_companion_id": sample_ai_companion.id, "user_message": "Hi"}
    )

    await _handler(ai_companion_repo=_Repository(sample_ai_companion))._handle_request_message(websocket, request)

    assert "User not found" in websocket.sent[0]["detail"]


@pytest.mark.anyio
async def test_handle_request_rejects_missing_user_companion(sample_user, sample_ai_companion):
    websocket = _FakeWebSocket()
    request = json.dumps(
        {"action": "chat", "user_id": sample_user.email, "ai_companion_id": sample_ai_companion.id, "user_message": "Hi"}
    )

    await _handler(
        user_repo=_Repository(sample_user),
        ai_companion_repo=_Repository(sample_ai_companion),
    )._handle_request_message(websocket, request)

    assert "preferences are missing" in websocket.sent[0]["detail"]


@pytest.mark.anyio
async def test_handle_request_rejects_ai_companion_not_owned(sample_user, sample_user_companion, sample_ai_companion):
    wrong_companion = mock.Mock(id=sample_ai_companion.id, user_id=999)
    websocket = _FakeWebSocket()
    request = json.dumps(
        {"action": "chat", "user_id": sample_user.email, "ai_companion_id": sample_ai_companion.id, "user_message": "Hi"}
    )

    await _handler(
        user_repo=_Repository(sample_user),
        user_companion_repo=_Repository(sample_user_companion),
        ai_companion_repo=_Repository(wrong_companion),
    )._handle_request_message(websocket, request)

    assert "not owned" in websocket.sent[0]["detail"]


@pytest.mark.anyio
async def test_handle_request_unhandled_exception_sends_error_frame(
    sample_user,
    sample_user_companion,
    sample_ai_companion,
):
    websocket = _FakeWebSocket()
    request = json.dumps(
        {"action": "chat", "user_id": sample_user.email, "ai_companion_id": sample_ai_companion.id, "user_message": "Hi"}
    )

    await _handler(
        service=_ChatService(exc=RuntimeError("stream exploded")),
        user_repo=_Repository(sample_user),
        user_companion_repo=_Repository(sample_user_companion),
        ai_companion_repo=_Repository(sample_ai_companion),
    )._handle_request_message(websocket, request)

    assert websocket.sent[0]["type"] == "error"
    assert websocket.sent[0]["detail"] == "Unhandled server error: RuntimeError"


@pytest.mark.anyio
async def test_safe_close_ignores_runtime_error():
    websocket = mock.Mock()
    websocket.close = mock.AsyncMock(side_effect=RuntimeError("already closed"))

    await WebSocketChatHandler._safe_close(websocket)

    websocket.close.assert_awaited_once()


def test_client_label_handles_missing_client():
    websocket = mock.Mock(client=None)
    assert WebSocketChatHandler._client_label(websocket) == "unknown"
