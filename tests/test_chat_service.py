from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.backend.schemas import ChatSocketRequest
from src.backend.service import ChatService
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
    def __init__(self, snapshot: ConversationSnapshot):
        self.snapshot = snapshot
        self.saved_messages: list[tuple[int, str, str]] = []

    def load_latest(self, user_id: int, ai_companion_id: int) -> ConversationSnapshot:
        return self.snapshot

    def start_fresh(self, user_id: int, ai_companion_id: int) -> ConversationSnapshot:
        return self.snapshot

    def save_message(self, conversation_id: int, role: str, content: str):
        self.saved_messages.append((conversation_id, role, content))
        return None


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
