from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.companion.schemas import AICompanionCreateRequest, AICompanionGenerateRequest
from src.companion.service import CompanionService
from src.storage.models import AICompanionRecord, UserRecord


class _RuntimeStub:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.requests = []

    async def generate_text(self, request):
        self.requests.append(request)
        return self.response_text


class _UserRepositoryStub:
    def __init__(self, user: UserRecord | None):
        self.user = user

    def find_by_email(self, email: str):
        if self.user is not None and self.user.email == email:
            return self.user
        return None


class _AICompanionRepositoryStub:
    def __init__(self):
        self.created_payloads = []

    def create(self, **kwargs):
        self.created_payloads.append(kwargs)
        return AICompanionRecord(
            id=17,
            user_id=kwargs["user_id"],
            title=kwargs["title"],
            description=kwargs["description"],
            gender=kwargs["gender"],
            style=kwargs["style"],
            ethnicity=kwargs["ethnicity"],
            eye_color=kwargs["eye_color"],
            hair_style=kwargs["hair_style"],
            hair_color=kwargs["hair_color"],
            personality=kwargs["personality"],
            voice=kwargs["voice"],
            connection=kwargs["connection_value"],
            created_at="2026-04-27T00:00:00Z",
            updated_at="2026-04-27T00:00:00Z",
        )


@pytest.mark.anyio
async def test_generate_ai_companion_returns_metadata_without_storage():
    runtime = _RuntimeStub('{"title":"Nadia","description":"A poised and magnetic woman with a secretive spark and quietly dominant presence."}')
    service = CompanionService(None, None, None, runtime)
    payload = AICompanionGenerateRequest(
        gender="Female",
        style="Retro Noir",
        ethnicity="South Asian",
        eyeColor="Hazel",
        hairStyle="Long",
        hairColor="Black",
        personality="Mysterious",
        voice="Deep",
        connection="Secret Affair",
    )

    response = await service.generate_ai_companion(payload)

    assert response.title == "Nadia"
    assert "dominant presence" in response.description
    assert len(runtime.requests) == 1
    prompt = runtime.requests[0].messages[0].content
    assert "Hair Color: Black" in prompt
    assert "Connection: Secret Affair" in prompt
    assert "exactly one word" in prompt
    schema = runtime.requests[0].json_schema
    assert "Exactly one realistic human first name" in schema["properties"]["title"]["description"]


@pytest.mark.anyio
async def test_create_ai_companion_uses_provided_title_and_description_without_generation():
    runtime = _RuntimeStub('{"title":"Unused","description":"Unused"}')
    user = UserRecord(
        id=5,
        email="admin@example.com",
        name="Admin",
        encrypted_password=None,
        created_at="2026-04-27T00:00:00Z",
    )
    ai_companion_repo = _AICompanionRepositoryStub()
    service = CompanionService(_UserRepositoryStub(user), None, ai_companion_repo, runtime)
    payload = {
        "user_mail_id": "admin@example.com",
        "title": "Selene",
        "description": "A calm, observant companion with a dry wit and steady presence.",
        "gender": "Female",
        "style": "Retro Noir",
        "ethnicity": "South Asian",
        "eyeColor": "Hazel",
        "hairStyle": "Long",
        "hairColor": "Black",
        "personality": "Mysterious",
        "voice": "Deep",
        "connection": "Secret Affair",
    }

    response = await service.create_ai_companion(AICompanionCreateRequest(**payload))

    assert response.ai_companion_id == 17
    assert response.title == "Selene"
    assert response.description == payload["description"]
    assert len(runtime.requests) == 0
    assert ai_companion_repo.created_payloads == [
        {
            "user_id": 5,
            "title": "Selene",
            "description": payload["description"],
            "gender": "Female",
            "style": "Retro Noir",
            "ethnicity": "South Asian",
            "eye_color": "Hazel",
            "hair_style": "Long",
            "hair_color": "Black",
            "personality": "Mysterious",
            "voice": "Deep",
            "connection_value": "Secret Affair",
        }
    ]
