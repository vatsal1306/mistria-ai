from types import SimpleNamespace

import pytest

from src.backend.schemas import ChatSocketRequest
from src.backend.service import ChatService
from src.memory.schemas import MemorySearchResult
from src.storage.conversation_store import ConversationSnapshot
from src.storage.models import AICompanionRecord, ConversationRecord, MessageRecord, UserCompanionRecord


class _StreamingRuntimeStub:
    def __init__(self, tokens: list[str]):
        self.tokens = tokens
        self.requests = []
        self.backend_name = "mock"

    async def stream_text(self, request):
        self.requests.append(request)
        for token in self.tokens:
            yield token


class _HistoryServiceStub:
    def __init__(self, snapshot: ConversationSnapshot | None):
        self.snapshot = snapshot
        self.saved_messages: list[tuple[int, str, str]] = []
        self.loaded: list[tuple[int, int]] = []
        self.started: list[tuple[int, int]] = []

    def load_latest(self, user_id: int, ai_companion_id: int) -> ConversationSnapshot | None:
        self.loaded.append((user_id, ai_companion_id))
        return self.snapshot

    def start_fresh(self, user_id: int, ai_companion_id: int) -> ConversationSnapshot:
        self.started.append((user_id, ai_companion_id))
        return self.snapshot

    def save_message(self, conversation_id: int, role: str, content: str):
        self.saved_messages.append((conversation_id, role, content))
        return None


class _MemoryServiceStub:
    def __init__(self, memories: list[MemorySearchResult], should_fail: bool = False):
        self.memories = memories
        self.should_fail = should_fail
        self.calls = []

    async def retrieve_memories(self, user_id, ai_companion_id, query):
        self.calls.append((user_id, ai_companion_id, query))
        if self.should_fail:
            raise Exception("Retrieval failed")
        return self.memories


@pytest.mark.anyio
async def test_stream_response_builds_companion_contract_prompt_and_trims_history():
    runtime = _StreamingRuntimeStub(tokens=["You", " lead."])
    snapshot = ConversationSnapshot(
        conversation=ConversationRecord(
            id=10,
            user_id=1,
            ai_companion_id=2,
            created_at="2026-04-24 10:00:00",
            updated_at="2026-04-24 10:00:00",
        ),
        messages=[
            MessageRecord(
                id=1,
                conversation_id=10,
                role="assistant",
                content="old message",
                created_at="2026-04-24 10:00:00",
                updated_at="2026-04-24 10:00:00",
            ),
            MessageRecord(
                id=2,
                conversation_id=10,
                role="user",
                content="remember I like when you take over",
                created_at="2026-04-24 10:01:00",
                updated_at="2026-04-24 10:01:00",
            ),
            MessageRecord(
                id=3,
                conversation_id=10,
                role="assistant",
                content="I remember that",
                created_at="2026-04-24 10:02:00",
                updated_at="2026-04-24 10:02:00",
            ),
        ],
    )
    history_service = _HistoryServiceStub(snapshot)
    service = ChatService(
        chat_config=SimpleNamespace(history_message_limit=2, system_prompt="Base chat prompt."),
        runtime=runtime,
        history_service=history_service,
    )
    request = ChatSocketRequest(
        action="chat",
        user_id="user@example.com",
        ai_companion_id=2,
        system_prompt=None,
        user_message="so what now?",
    )
    user_companion = UserCompanionRecord(
        id=1,
        user_id=1,
        intent_type="alive",
        dominance_mode="ai_leads",
        intensity_level="break_glass",
        silence_response="come_looking",
        secret_desire="both",
        title="Chased and Unapologetic",
        description="A high-intensity dynamic built on pursuit and surrender.",
        created_at="2026-04-24 09:00:00",
        updated_at="2026-04-24 09:00:00",
    )
    ai_companion = AICompanionRecord(
        id=2,
        user_id=1,
        title="Luna",
        description="A playful but controlling companion with confident energy.",
        gender="Female",
        style="Anime",
        ethnicity="East Asian",
        eye_color="Green",
        hair_style="Long",
        hair_color="Pink",
        personality="Playful",
        voice="Breathy",
        connection="Passionate Lover",
        created_at="2026-04-24 09:00:00",
        updated_at="2026-04-24 09:00:00",
    )

    chunks = []
    async for chunk in service.stream_response(
            request,
            internal_user_id=1,
            user_name="Vatsal Patel",
            user_companion=user_companion,
            ai_companion=ai_companion,
            snapshot=snapshot,
    ):
        chunks.append(chunk)

    assert chunks == ["You", " lead."]
    assert len(runtime.requests) == 1

    inference_request = runtime.requests[0]
    assert inference_request.messages[-3].content == "remember I like when you take over"
    assert inference_request.messages[-2].content == "I remember that"
    assert inference_request.messages[-1].content == "so what now?"
    assert "old message" not in [message.content for message in inference_request.messages]

    system_prompt = inference_request.system_prompt
    assert system_prompt is not None
    assert "Base chat prompt." in system_prompt
    assert "Summary Title: Chased and Unapologetic" in system_prompt
    assert "Registered First Name: Vatsal" in system_prompt
    assert "Dominance Mode: She Leads (ai_leads)" in system_prompt
    assert "You must lead. Take initiative" in system_prompt
    assert "Name: Luna" in system_prompt
    assert "Relationship Frame: Passionate Lover" in system_prompt
    assert "Use only the visible conversation history as memory." in system_prompt
    assert "use it naturally from time to time" in system_prompt
    assert "do not keep falling back to vague setup lines" in system_prompt
    assert "Then let me lead, Vatsal." in system_prompt

    assert history_service.saved_messages == [
        (10, "user", "so what now?"),
        (10, "assistant", "You lead."),
    ]


@pytest.mark.anyio
@pytest.mark.anyio
async def test_stream_response_injects_memories_when_enabled():
    runtime = _StreamingRuntimeStub(tokens=["Hi."])
    snapshot = ConversationSnapshot(
        conversation=ConversationRecord(id=1, user_id=1, ai_companion_id=2, created_at="", updated_at=""),
        messages=[],
    )
    history_service = _HistoryServiceStub(snapshot)
    
    memories = [
        MemorySearchResult(
            memory_id=1, memory_type="fact", content="User loves cats", canonical_key="cats", score=0.9, source="semantic"
        )
    ]
    memory_service = _MemoryServiceStub(memories)
    
    service = ChatService(
        chat_config=SimpleNamespace(history_message_limit=10, system_prompt="Base."),
        runtime=runtime,
        history_service=history_service,
        memory_service=memory_service,
    )
    
    user_companion = UserCompanionRecord(id=1, user_id=1, title="T", description="D", intent_type="alive", dominance_mode="ai_leads", intensity_level="break_glass", silence_response="come_looking", secret_desire="both", created_at="", updated_at="")
    ai_companion = AICompanionRecord(id=2, user_id=1, title="Luna", description="D", gender="F", style="S", ethnicity="E", eye_color="G", hair_style="L", hair_color="P", personality="P", voice="V", connection="C", created_at="", updated_at="")
    
    request = ChatSocketRequest(action="chat", user_id="u", ai_companion_id=2, system_prompt=None, user_message="hello")
    
    async for _ in service.stream_response(request, internal_user_id=1, user_name="V", user_companion=user_companion, ai_companion=ai_companion, snapshot=snapshot):
        pass

    system_prompt = runtime.requests[0].system_prompt
    assert "LONG-TERM MEMORY (CURATED)" in system_prompt
    assert "'User loves cats'" in system_prompt
    assert "Use the provided long-term memory and the visible conversation history" in system_prompt
    assert len(memory_service.calls) == 1


@pytest.mark.anyio
async def test_stream_response_graceful_fallback_on_memory_failure():
    runtime = _StreamingRuntimeStub(tokens=["Hi."])
    snapshot = ConversationSnapshot(
        conversation=ConversationRecord(id=1, user_id=1, ai_companion_id=2, created_at="", updated_at=""),
        messages=[],
    )
    history_service = _HistoryServiceStub(snapshot)
    memory_service = _MemoryServiceStub([], should_fail=True)
    
    service = ChatService(
        chat_config=SimpleNamespace(history_message_limit=10, system_prompt="Base."),
        runtime=runtime,
        history_service=history_service,
        memory_service=memory_service,
    )
    
    user_companion = UserCompanionRecord(id=1, user_id=1, title="T", description="D", intent_type="alive", dominance_mode="ai_leads", intensity_level="break_glass", silence_response="come_looking", secret_desire="both", created_at="", updated_at="")
    ai_companion = AICompanionRecord(id=2, user_id=1, title="Luna", description="D", gender="F", style="S", ethnicity="E", eye_color="G", hair_style="L", hair_color="P", personality="P", voice="V", connection="C", created_at="", updated_at="")
    
    request = ChatSocketRequest(action="chat", user_id="u", ai_companion_id=2, system_prompt=None, user_message="hello")
    
    # Should not raise exception
    async for _ in service.stream_response(request, internal_user_id=1, user_name="V", user_companion=user_companion, ai_companion=ai_companion, snapshot=snapshot):
        pass

    system_prompt = runtime.requests[0].system_prompt
    assert "LONG-TERM MEMORY" not in system_prompt
    assert "Use only the visible conversation history as memory." in system_prompt


@pytest.mark.anyio
async def test_stream_response_discards_mismatched_prefetched_snapshot_and_starts_fresh(
    sample_user_companion,
    sample_ai_companion,
):
    runtime = _StreamingRuntimeStub(tokens=[])
    fresh_snapshot = ConversationSnapshot(
        conversation=ConversationRecord(
            id=20,
            user_id=1,
            ai_companion_id=2,
            created_at="2026-04-24 10:00:00",
            updated_at="2026-04-24 10:00:00",
        ),
        messages=[],
    )
    mismatched_snapshot = ConversationSnapshot(
        conversation=ConversationRecord(
            id=99,
            user_id=999,
            ai_companion_id=2,
            created_at="2026-04-24 10:00:00",
            updated_at="2026-04-24 10:00:00",
        ),
        messages=[MessageRecord(1, 99, "user", "wrong history", "t", "t")],
    )
    history_service = _HistoryServiceStub(snapshot=fresh_snapshot)
    service = ChatService(
        chat_config=SimpleNamespace(history_message_limit=2, system_prompt="Base chat prompt."),
        runtime=runtime,
        history_service=history_service,
    )
    request = ChatSocketRequest(user_id="user@example.com", ai_companion_id=2, user_message="hello")

    chunks = [
        chunk
        async for chunk in service.stream_response(
            request,
            internal_user_id=1,
            user_name=None,
            user_companion=sample_user_companion,
            ai_companion=sample_ai_companion,
            snapshot=mismatched_snapshot,
        )
    ]

    assert chunks == []
    assert history_service.loaded == [(1, 2)]
    assert history_service.started == []
    assert history_service.saved_messages == [(20, "user", "hello")]


@pytest.mark.anyio
async def test_stream_response_starts_fresh_when_no_history_exists(sample_user_companion, sample_ai_companion):
    fresh_snapshot = ConversationSnapshot(
        conversation=ConversationRecord(30, 1, 2, "2026-04-24 10:00:00", "2026-04-24 10:00:00"),
        messages=[],
    )

    class _History(_HistoryServiceStub):
        def load_latest(self, user_id: int, ai_companion_id: int):
            self.loaded.append((user_id, ai_companion_id))
            return None

        def start_fresh(self, user_id: int, ai_companion_id: int):
            self.started.append((user_id, ai_companion_id))
            return fresh_snapshot

    runtime = _StreamingRuntimeStub(tokens=["done"])
    history_service = _History(snapshot=None)
    service = ChatService(
        chat_config=SimpleNamespace(history_message_limit=2, system_prompt="Base chat prompt."),
        runtime=runtime,
        history_service=history_service,
    )

    chunks = [
        chunk
        async for chunk in service.stream_response(
            ChatSocketRequest(user_id="user@example.com", ai_companion_id=2, user_message="hello"),
            1,
            None,
            sample_user_companion,
            sample_ai_companion,
        )
    ]

    assert chunks == ["done"]
    assert history_service.started == [(1, 2)]
    assert history_service.saved_messages[-1] == (30, "assistant", "done")


@pytest.mark.anyio
async def test_stream_response_propagates_runtime_failure(sample_user_companion, sample_ai_companion, sample_conversation):
    class _FailingRuntime(_StreamingRuntimeStub):
        async def stream_text(self, request):
            self.requests.append(request)
            raise RuntimeError("runtime failed")
            yield  # pragma: no cover

    snapshot = ConversationSnapshot(sample_conversation, [])
    history_service = _HistoryServiceStub(snapshot)
    service = ChatService(
        chat_config=SimpleNamespace(history_message_limit=2, system_prompt="Base chat prompt."),
        runtime=_FailingRuntime(tokens=[]),
        history_service=history_service,
    )

    with pytest.raises(RuntimeError, match="runtime failed"):
        async for _ in service.stream_response(
            ChatSocketRequest(user_id="user@example.com", ai_companion_id=2, user_message="hello"),
            1,
            None,
            sample_user_companion,
            sample_ai_companion,
            snapshot,
        ):
            pass

    assert history_service.saved_messages == [(sample_conversation.id, "user", "hello")]

