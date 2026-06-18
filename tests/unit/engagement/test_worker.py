"""Unit tests for the engagement scoring background worker."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest

from src.backend.schemas import InferencePromptRequest
from src.config import Engagement
from src.engagement import state
from src.engagement.worker import EngagementScoringWorker
from src.storage.models import MessageRecord


class _RuntimeStub:
    def __init__(self, output: str = "75", should_fail: bool = False):
        self.output = output
        self.should_fail = should_fail
        self.requests: list[InferencePromptRequest] = []
        self.backend_name = "vllm"

    async def generate_text(self, request: InferencePromptRequest) -> str:
        self.requests.append(request)
        if self.should_fail:
            raise RuntimeError("inference failed")
        return self.output


class _HistoryServiceStub:
    def __init__(self, messages: list[MessageRecord] | None = None):
        self.messages = messages or []
        self.calls: list[tuple[int, int]] = []

    def list_recent_messages(self, conversation_id: int, limit: int) -> list[MessageRecord]:
        self.calls.append((conversation_id, limit))
        return self.messages[-limit:]


@pytest.fixture(autouse=True)
def _clear_engagement_state() -> None:
    state.clear_scores()


@pytest.fixture
def engagement_config() -> Engagement:
    return Engagement(
        external_backend_webhook_url="http://backend.test/engagement",
        history_limit=4,
    )


@pytest.mark.anyio
async def test_worker_dispatches_webhook_when_score_changes(
    engagement_config: Engagement,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _RuntimeStub(output="82")
    history_service = _HistoryServiceStub(
        messages=[
            MessageRecord(1, 10, "user", "hey", "t", "t"),
            MessageRecord(2, 10, "assistant", "hi there", "t", "t"),
        ]
    )
    worker = EngagementScoringWorker(runtime, history_service, engagement_config)
    posted_payloads: list[dict[str, object]] = []

    class _FakeResponse:
        status_code = 200

        @staticmethod
        def raise_for_status() -> None:
            return None

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, json: dict[str, object]):
            posted_payloads.append({"url": url, "json": json})
            return _FakeResponse()

    monkeypatch.setattr("src.engagement.worker.httpx.AsyncClient", _FakeClient)

    worker.schedule(conversation_id="10", user_id="user@example.com", companion_id="2")
    await asyncio.sleep(0.1)

    assert history_service.calls == [(10, 4)]
    assert len(runtime.requests) == 1
    assert runtime.requests[0].max_tokens == 5
    assert runtime.requests[0].temperature == 0.1
    assert posted_payloads == [{
        "url": "http://backend.test/engagement",
        "json": {
            "user_id": "user@example.com",
            "ai_companion_id": 2,
            "engagement_score": 82,
        },
    }]
    assert state.get_last_score("10") == 82


@pytest.mark.anyio
async def test_worker_skips_webhook_when_score_is_unchanged(
    engagement_config: Engagement,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state.set_last_score("10", 82)
    runtime = _RuntimeStub(output="82")
    history_service = _HistoryServiceStub(
        messages=[MessageRecord(1, 10, "user", "hey", "t", "t")]
    )
    worker = EngagementScoringWorker(runtime, history_service, engagement_config)
    post_calls: list[dict[str, object]] = []

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, json: dict[str, object]):
            post_calls.append(json)
            response = SimpleNamespace(status_code=200)
            response.raise_for_status = lambda: None
            return response

    monkeypatch.setattr("src.engagement.worker.httpx.AsyncClient", _FakeClient)

    worker.schedule(conversation_id="10", user_id="user@example.com", companion_id="2")
    await asyncio.sleep(0.1)

    assert post_calls == []


@pytest.mark.anyio
async def test_worker_aborts_on_invalid_llm_output(
    engagement_config: Engagement,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _RuntimeStub(output="not a score")
    history_service = _HistoryServiceStub(
        messages=[MessageRecord(1, 10, "user", "hey", "t", "t")]
    )
    worker = EngagementScoringWorker(runtime, history_service, engagement_config)
    post_calls: list[dict[str, object]] = []

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, json: dict[str, object]):
            post_calls.append(json)
            response = SimpleNamespace(status_code=200)
            response.raise_for_status = lambda: None
            return response

    monkeypatch.setattr("src.engagement.worker.httpx.AsyncClient", _FakeClient)

    worker.schedule(conversation_id="10", user_id="user@example.com", companion_id="2")
    await asyncio.sleep(0.1)

    assert post_calls == []
    assert state.get_last_score("10") is None


@pytest.mark.anyio
async def test_worker_logs_and_continues_on_webhook_request_error(
    engagement_config: Engagement,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _RuntimeStub(output="55")
    history_service = _HistoryServiceStub(
        messages=[MessageRecord(1, 10, "user", "hey", "t", "t")]
    )
    worker = EngagementScoringWorker(runtime, history_service, engagement_config)

    class _FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, json: dict[str, object]):
            raise httpx.RequestError("network down", request=httpx.Request("POST", url))

    monkeypatch.setattr("src.engagement.worker.httpx.AsyncClient", _FailingClient)

    worker.schedule(conversation_id="10", user_id="user@example.com", companion_id="2")
    await asyncio.sleep(0.1)

    assert state.get_last_score("10") == 55


@pytest.mark.anyio
async def test_worker_does_not_schedule_when_disabled() -> None:
    runtime = _RuntimeStub(output="55")
    history_service = _HistoryServiceStub(
        messages=[MessageRecord(1, 10, "user", "hey", "t", "t")]
    )
    worker = EngagementScoringWorker(
        runtime,
        history_service,
        Engagement(external_backend_webhook_url=None, history_limit=10),
    )

    worker.schedule(conversation_id="10", user_id="user@example.com", companion_id="2")
    await asyncio.sleep(0.1)

    assert history_service.calls == []
    assert runtime.requests == []


@pytest.mark.anyio
async def test_worker_skips_when_no_history_exists(
    engagement_config: Engagement,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _RuntimeStub(output="55")
    history_service = _HistoryServiceStub(messages=[])
    worker = EngagementScoringWorker(runtime, history_service, engagement_config)
    post_calls: list[dict[str, object]] = []

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, json: dict[str, object]):
            post_calls.append(json)
            response = SimpleNamespace(status_code=200)
            response.raise_for_status = lambda: None
            return response

    monkeypatch.setattr("src.engagement.worker.httpx.AsyncClient", _FakeClient)

    worker.schedule(conversation_id="10", user_id="user@example.com", companion_id="2")
    await asyncio.sleep(0.1)

    assert runtime.requests == []
    assert post_calls == []


@pytest.mark.anyio
async def test_worker_handles_inference_failure_gracefully(
    engagement_config: Engagement,
) -> None:
    runtime = _RuntimeStub(should_fail=True)
    history_service = _HistoryServiceStub(
        messages=[MessageRecord(1, 10, "user", "hey", "t", "t")]
    )
    worker = EngagementScoringWorker(runtime, history_service, engagement_config)

    worker.schedule(conversation_id="10", user_id="user@example.com", companion_id="2")
    await asyncio.sleep(0.1)

    assert state.get_last_score("10") is None


@pytest.mark.anyio
async def test_worker_uses_random_score_for_mock_backend(
    engagement_config: Engagement,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _MockBackendRuntime:
        backend_name = "mock"

        async def generate_text(self, request: InferencePromptRequest) -> str:
            raise AssertionError("mock engagement scoring should not call the inference runtime")

    runtime = _MockBackendRuntime()
    history_service = _HistoryServiceStub(
        messages=[MessageRecord(1, 10, "user", "hey", "t", "t")]
    )
    worker = EngagementScoringWorker(runtime, history_service, engagement_config)
    posted_payloads: list[dict[str, object]] = []

    class _FakeResponse:
        status_code = 200

        @staticmethod
        def raise_for_status() -> None:
            return None

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, json: dict[str, object]):
            posted_payloads.append(json)
            return _FakeResponse()

    monkeypatch.setattr("src.engagement.worker.random.randint", lambda low, high: 67)
    monkeypatch.setattr("src.engagement.worker.httpx.AsyncClient", _FakeClient)

    worker.schedule(conversation_id="10", user_id="user@example.com", companion_id="2")
    await asyncio.sleep(0.1)

    assert posted_payloads == [{
        "user_id": "user@example.com",
        "ai_companion_id": 2,
        "engagement_score": 67,
    }]


@pytest.mark.anyio
async def test_worker_shutdown_awaits_pending_jobs() -> None:
    runtime = _RuntimeStub(output="60")

    class _SlowHistoryService(_HistoryServiceStub):
        def list_recent_messages(self, conversation_id: int, limit: int):
            self.calls.append((conversation_id, limit))
            return self.messages

    history_service = _SlowHistoryService(
        messages=[MessageRecord(1, 10, "user", "hey", "t", "t")]
    )
    worker = EngagementScoringWorker(
        runtime,
        history_service,
        Engagement(external_backend_webhook_url="http://backend.test/engagement", history_limit=10),
    )

    async def _slow_score(*args, **kwargs):
        await asyncio.sleep(0.05)

    worker.calculate_and_dispatch_score = _slow_score  # type: ignore[method-assign]
    worker.schedule(conversation_id="10", user_id="user@example.com", companion_id="2")
    assert len(worker._tasks) == 1

    await worker.shutdown()
    assert len(worker._tasks) == 0
