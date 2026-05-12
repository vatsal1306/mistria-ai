"""Unit tests for docker-compose smoke helpers."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest import mock

import pytest

from scripts import smoke_stack


class _Response:
    def __init__(self, status: int = 200, body: bytes = b"{}"):
        self.status = status
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._body


class _FakeConnection:
    def __init__(self, frames: list[dict]):
        self.frames = [json.dumps(frame) for frame in frames]
        self.sent: list[str] = []
        self.closed = False

    def recv(self):
        return self.frames.pop(0)

    def send(self, payload: str):
        self.sent.append(payload)

    def close(self):
        self.closed = True


def test_build_ws_url_appends_required_query_params():
    assert smoke_stack.build_ws_url("ws://host/ws", "user@example.com", 3, "") == (
        "ws://host/ws?user_id=user%40example.com&ai_companion_id=3"
    )
    assert smoke_stack.build_ws_url("ws://host/ws?debug=1", "u", 4, "key").endswith(
        "&user_id=u&ai_companion_id=4&api_key=key"
    )


def test_assert_ready_frame_validates_type():
    smoke_stack.assert_ready_frame({"type": "ready"})
    with pytest.raises(RuntimeError, match="Expected ready frame"):
        smoke_stack.assert_ready_frame({"type": "delta"})


def test_wait_for_http_succeeds_after_retry(monkeypatch):
    monkeypatch.setattr(
        smoke_stack.urllib.request,
        "urlopen",
        mock.Mock(side_effect=[smoke_stack.urllib.error.URLError("down"), _Response(status=200)]),
    )
    monkeypatch.setattr(smoke_stack.time, "sleep", mock.Mock())

    smoke_stack.wait_for_http("http://example.com", timeout_seconds=5)


def test_wait_for_http_rejects_bad_scheme_and_timeout(monkeypatch):
    with pytest.raises(RuntimeError, match="Unsupported readiness"):
        smoke_stack.wait_for_http("ftp://example.com", timeout_seconds=1)

    times = iter([0.0, 2.0])
    monkeypatch.setattr(smoke_stack.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(smoke_stack.time, "sleep", mock.Mock())
    monkeypatch.setattr(smoke_stack.urllib.request, "urlopen", mock.Mock(return_value=_Response(status=503)))

    with pytest.raises(RuntimeError, match="Timed out"):
        smoke_stack.wait_for_http("http://example.com", timeout_seconds=1)


def test_post_json_sends_payload_and_parses_response(monkeypatch):
    urlopen = mock.Mock(return_value=_Response(body=b'{"ok": true}'))
    monkeypatch.setattr(smoke_stack.urllib.request, "urlopen", urlopen)

    payload = smoke_stack._post_json("http://backend/", "/users", {"email": "u@example.com"})

    assert payload == {"ok": True}
    request = urlopen.call_args.args[0]
    assert request.full_url == "http://backend/users"
    assert request.method == "POST"


def test_seed_smoke_user_posts_required_records(monkeypatch):
    responses = [{}, {}, {"ai_companion_id": 42}]
    posted = []

    def fake_post_json(base_url, path, payload):
        posted.append((base_url, path, payload))
        return responses.pop(0)

    monkeypatch.setattr(smoke_stack, "_post_json", fake_post_json)
    monkeypatch.setattr(smoke_stack, "uuid4", mock.Mock(return_value=SimpleNamespace(hex="abcdef123456")))

    email, ai_companion_id = smoke_stack.seed_smoke_user("http://backend")

    assert email == "smoke-abcdef12@ci.test"
    assert ai_companion_id == 42
    assert [path for _, path, _ in posted] == ["/users", "/user-companion", "/ai-companion"]


def test_run_websocket_round_trip_collects_deltas(monkeypatch):
    connection = _FakeConnection(
        [
            {"type": "ready", "backend": "mock"},
            {"type": "delta", "delta": "hi"},
            {"type": "done"},
        ]
    )
    monkeypatch.setattr(smoke_stack, "create_connection", mock.Mock(return_value=connection))

    smoke_stack.run_websocket_round_trip("ws://backend/ws", "user@example.com", 3)

    assert connection.closed is True
    assert json.loads(connection.sent[0])["user_id"] == "user@example.com"


@pytest.mark.parametrize(
    ("frames", "message"),
    [
        ([{"type": "ready"}, {"type": "done"}], "any websocket delta"),
        ([{"type": "ready"}, {"type": "error", "detail": "bad"}], "Backend returned an error"),
        ([{"type": "ready"}, {"type": "weird"}], "Unexpected websocket frame"),
    ],
)
def test_run_websocket_round_trip_rejects_bad_frame_sequences(monkeypatch, frames, message):
    monkeypatch.setattr(smoke_stack, "create_connection", mock.Mock(return_value=_FakeConnection(frames)))

    with pytest.raises(RuntimeError, match=message):
        smoke_stack.run_websocket_round_trip("ws://backend/ws", "user@example.com", 3)


def test_main_runs_full_sequence(monkeypatch):
    monkeypatch.setattr(
        smoke_stack,
        "parse_args",
        lambda: SimpleNamespace(
            frontend_url="http://frontend",
            backend_health_url="http://backend/health",
            websocket_url="ws://backend/ws",
            api_key="key",
            timeout_seconds=1,
        ),
    )
    wait_for_http = mock.Mock()
    seed = mock.Mock(return_value=("user@example.com", 9))
    round_trip = mock.Mock()
    monkeypatch.setattr(smoke_stack, "wait_for_http", wait_for_http)
    monkeypatch.setattr(smoke_stack, "seed_smoke_user", seed)
    monkeypatch.setattr(smoke_stack, "run_websocket_round_trip", round_trip)

    assert smoke_stack.main() == 0
    assert wait_for_http.call_count == 2
    seed.assert_called_once_with("http://backend")
    round_trip.assert_called_once()


def test_parse_args_reads_cli_arguments(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "smoke_stack.py",
            "--frontend-url",
            "http://frontend",
            "--backend-health-url",
            "http://backend/health",
            "--websocket-url",
            "ws://backend/ws",
            "--api-key",
            "key",
        ],
    )

    args = smoke_stack.parse_args()

    assert args.frontend_url == "http://frontend"
    assert args.api_key == "key"
