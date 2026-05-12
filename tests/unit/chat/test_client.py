"""Unit tests for the websocket chat client."""

from __future__ import annotations

import json
from dataclasses import replace
from unittest import mock

import pytest
from websocket import WebSocketException, WebSocketTimeoutException

from src.chat.client import ChatClientError, StreamingChatClient
from src.config import settings


class _FakeWebSocket:
    def __init__(self, frames: list[dict | str] | None = None):
        self.frames = list(frames or [])
        self.sent: list[str] = []
        self.closed = False
        self.connected = True

    def recv(self) -> str:
        frame = self.frames.pop(0)
        if isinstance(frame, str):
            return frame
        return json.dumps(frame)

    def send(self, payload: str) -> None:
        self.sent.append(payload)

    def close(self) -> None:
        self.closed = True
        self.connected = False


def _make_client(require_api_key: bool = False) -> StreamingChatClient:
    api_config = replace(
        settings.api,
        host="localhost",
        port=8080,
        websocket_path="/ws/chat",
        read_timeout_seconds=3.0,
        require_api_key=require_api_key,
    )
    secrets_config = replace(settings.secrets, api_key="test-key")
    return StreamingChatClient(api_config, settings.chat, secrets_config)


def test_build_websocket_url_includes_query_and_optional_api_key():
    client = _make_client(require_api_key=False)
    assert client._build_websocket_url("user@example.com", 12) == (
        "ws://localhost:8080/ws/chat?user_id=user%40example.com&ai_companion_id=12"
    )

    secure_client = _make_client(require_api_key=True)
    assert secure_client._build_websocket_url("user@example.com", 12).endswith("&api_key=test-key")


def test_connect_consumes_ready_event_and_caches_backend(monkeypatch):
    websocket = _FakeWebSocket([{"type": "ready", "backend": "mock"}])
    create_connection = mock.Mock(return_value=websocket)
    monkeypatch.setattr("src.chat.client.create_connection", create_connection)
    client = _make_client()

    client.connect("user@example.com", 1)

    assert client.is_connected is True
    assert client.backend_name == "mock"
    create_connection.assert_called_once_with(
        "ws://localhost:8080/ws/chat?user_id=user%40example.com&ai_companion_id=1",
        timeout=3.0,
    )


@pytest.mark.parametrize(
    ("exc", "message"),
    [
        (WebSocketTimeoutException("slow"), "timed out"),
        (WebSocketException("broken"), "Could not connect"),
        (OSError("down"), "Could not reach"),
    ],
)
def test_connect_wraps_transport_failures(monkeypatch, exc, message):
    monkeypatch.setattr("src.chat.client.create_connection", mock.Mock(side_effect=exc))
    client = _make_client()

    with pytest.raises(ChatClientError, match=message):
        client.connect("user@example.com", 1)

    assert client.is_connected is False


def test_connect_rejects_missing_ready_event(monkeypatch):
    monkeypatch.setattr(
        "src.chat.client.create_connection",
        mock.Mock(return_value=_FakeWebSocket([{"type": "delta", "delta": "too soon"}])),
    )
    client = _make_client()

    with pytest.raises(ChatClientError, match="ready event"):
        client.connect("user@example.com", 1)

    assert client.is_connected is False


def test_stream_reply_sends_payload_and_yields_deltas():
    websocket = _FakeWebSocket(
        [
            {"type": "delta", "delta": "hello"},
            {"type": "ignored", "detail": "noop"},
            {"type": "delta", "delta": " world"},
            {"type": "done"},
        ]
    )
    client = _make_client()
    client._websocket = websocket
    client._backend_name = "mock"

    chunks = list(client.stream_reply("Hi", "user@example.com", 4, system_prompt="system"))

    assert chunks == ["hello", " world"]
    sent_payload = json.loads(websocket.sent[0])
    assert sent_payload == {
        "action": "chat",
        "user_id": "user@example.com",
        "ai_companion_id": 4,
        "system_prompt": "system",
        "user_message": "Hi",
    }


def test_stream_reply_requires_connection():
    with pytest.raises(ChatClientError, match="No active websocket"):
        list(_make_client().stream_reply("Hi", "user@example.com", 1))


def test_stream_reply_raises_backend_error_frame():
    websocket = _FakeWebSocket([{"type": "error", "detail": "bad request"}])
    client = _make_client()
    client._websocket = websocket

    with pytest.raises(ChatClientError, match="bad request"):
        list(client.stream_reply("Hi", "user@example.com", 1))


@pytest.mark.parametrize(
    ("frames", "message"),
    [
        ([""], "empty frame"),
        (["not-json"], "malformed JSON"),
    ],
)
def test_receive_frame_validates_backend_payload(frames, message):
    client = _make_client()
    client._websocket = _FakeWebSocket(frames)

    with pytest.raises(ChatClientError, match=message):
        client._receive_frame()


@pytest.mark.parametrize(
    ("exc", "message"),
    [
        (WebSocketTimeoutException("slow"), "timed out"),
        (WebSocketException("broken"), "interrupted"),
        (OSError("down"), "unreachable"),
    ],
)
def test_stream_reply_disconnects_on_transport_errors(exc, message):
    websocket = _FakeWebSocket([{"type": "done"}])
    websocket.send = mock.Mock(side_effect=exc)
    client = _make_client()
    client._websocket = websocket

    with pytest.raises(ChatClientError, match=message):
        list(client.stream_reply("Hi", "user@example.com", 1))

    assert client.is_connected is False
