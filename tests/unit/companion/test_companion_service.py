from dataclasses import replace

import pytest

from src.companion.contracts import UserCompanionLabelCatalog
from src.companion.exceptions import AICompanionNotFoundError, UserCompanionNotFoundError, UserNotRegisteredError
from src.companion.schemas import (
    AICompanionCreateRequest,
    AICompanionGenerateRequest,
    UserCompanionUpsertRequest,
    normalize_user_mail_id,
)
from src.companion.service import CompanionService
from src.storage.models import AICompanionRecord, UserCompanionRecord, UserRecord


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

    def find_by_id(self, user_id: int):
        if self.user is not None and self.user.id == user_id:
            return self.user
        return None


class _UserCompanionRepositoryStub:
    def __init__(self, record: UserCompanionRecord | None = None):
        self.record = record
        self.upsert_payloads = []

    def find_by_user_id(self, user_id: int):
        if self.record is not None and self.record.user_id == user_id:
            return self.record
        return None

    def upsert(self, **kwargs):
        self.upsert_payloads.append(kwargs)
        self.record = UserCompanionRecord(
            id=3,
            user_id=kwargs["user_id"],
            intent_type=kwargs["intent_type"],
            dominance_mode=kwargs["dominance_mode"],
            intensity_level=kwargs["intensity_level"],
            silence_response=kwargs["silence_response"],
            secret_desire=kwargs["secret_desire"],
            title=kwargs["title"],
            description=kwargs["description"],
            created_at="2026-04-27T00:00:00Z",
            updated_at="2026-04-27T00:00:00Z",
        )
        return self.record


class _AICompanionRepositoryStub:
    def __init__(self, records: list[AICompanionRecord] | None = None):
        self.records = records or []
        self.created_payloads = []

    def create(self, **kwargs):
        self.created_payloads.append(kwargs)
        record = AICompanionRecord(
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
        self.records.append(record)
        return record

    def find_by_id(self, ai_companion_id: int):
        return next((record for record in self.records if record.id == ai_companion_id), None)

    def list_by_user_id(self, user_id: int):
        return [record for record in self.records if record.user_id == user_id]

    def find_latest_by_user_id(self, user_id: int):
        records = self.list_by_user_id(user_id)
        return records[0] if records else None


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


def test_normalize_user_mail_id_strips_lowercases_and_validates():
    assert normalize_user_mail_id(" Admin@Example.COM ") == "admin@example.com"
    with pytest.raises(ValueError, match="valid email"):
        normalize_user_mail_id("not-an-email")


def test_label_catalog_resolves_labels_and_guidance():
    payload = {
        "intent_type": "alive",
        "dominance_mode": "ai_leads",
        "intensity_level": "break_glass",
        "silence_response": "come_looking",
        "secret_desire": "both",
    }

    labels = UserCompanionLabelCatalog.resolve_payload_labels(payload)
    guidance = UserCompanionLabelCatalog.resolve_prompt_guidance(payload)

    assert labels["dominance_mode"] == "She Leads"
    assert "Take initiative" in guidance["dominance_mode"]


@pytest.mark.anyio
async def test_upsert_user_companion_generates_metadata_and_persists(sample_user):
    runtime = _RuntimeStub('{"title":"Electric Pull","description":"A vivid dynamic with active pursuit."}')
    user_companion_repo = _UserCompanionRepositoryStub()
    service = CompanionService(_UserRepositoryStub(sample_user), user_companion_repo, None, runtime)
    payload = UserCompanionUpsertRequest(
        user_mail_id=" USER@example.com ",
        intent_type="alive",
        dominance_mode="ai_leads",
        intensity_level="break_glass",
        silence_response="come_looking",
        secret_desire="both",
    )

    response = await service.upsert_user_companion(payload)

    assert response.user_mail_id == "user@example.com"
    assert response.title == "Electric Pull"
    assert user_companion_repo.upsert_payloads[0]["dominance_mode"] == "ai_leads"
    assert runtime.requests[0].json_schema["properties"]["title"]["description"].startswith("A catchy")


def test_get_user_companion_success_and_missing_preferences(sample_user, sample_user_companion):
    service = CompanionService(
        _UserRepositoryStub(sample_user),
        _UserCompanionRepositoryStub(sample_user_companion),
        None,
        _RuntimeStub("{}"),
    )

    response = service.get_user_companion("USER@example.com")

    assert response.user_mail_id == sample_user.email
    assert response.title == sample_user_companion.title

    missing_service = CompanionService(_UserRepositoryStub(sample_user), _UserCompanionRepositoryStub(None), None, _RuntimeStub("{}"))
    with pytest.raises(UserCompanionNotFoundError):
        missing_service.get_user_companion(sample_user.email)


@pytest.mark.anyio
async def test_create_ai_companion_generates_missing_metadata(sample_user):
    runtime = _RuntimeStub('{"title":"Mira","description":"A confident presence with playful control."}')
    ai_companion_repo = _AICompanionRepositoryStub()
    service = CompanionService(_UserRepositoryStub(sample_user), None, ai_companion_repo, runtime)

    response = await service.create_ai_companion(
        AICompanionCreateRequest(
            user_mail_id=sample_user.email,
            title=None,
            description=None,
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
    )

    assert response.title == "Mira"
    assert response.description == "A confident presence with playful control."
    assert len(runtime.requests) == 1


def test_list_get_and_latest_ai_companion(sample_user, sample_ai_companion):
    repository = _AICompanionRepositoryStub([sample_ai_companion])
    service = CompanionService(_UserRepositoryStub(sample_user), None, repository, _RuntimeStub("{}"))

    listed = service.list_ai_companions(sample_user.email)
    fetched = service.get_ai_companion(sample_ai_companion.id)
    latest = service.get_latest_ai_companion(sample_user.email)

    assert [record.id for record in listed] == [sample_ai_companion.id]
    assert fetched.user_mail_id == sample_user.email
    assert latest.title == sample_ai_companion.title


def test_companion_service_raises_for_missing_users_and_records(sample_user, sample_ai_companion):
    service = CompanionService(_UserRepositoryStub(None), None, _AICompanionRepositoryStub(), _RuntimeStub("{}"))
    with pytest.raises(UserNotRegisteredError):
        service.list_ai_companions("missing@example.com")

    service = CompanionService(_UserRepositoryStub(sample_user), None, _AICompanionRepositoryStub(), _RuntimeStub("{}"))
    with pytest.raises(AICompanionNotFoundError):
        service.get_ai_companion(999)
    with pytest.raises(AICompanionNotFoundError):
        service.get_latest_ai_companion(sample_user.email)

    orphan = replace(sample_ai_companion, user_id=999)
    service = CompanionService(_UserRepositoryStub(sample_user), None, _AICompanionRepositoryStub([orphan]), _RuntimeStub("{}"))
    with pytest.raises(AICompanionNotFoundError):
        service.get_ai_companion(orphan.id)


def test_generate_ai_companion_title_helper():
    payload = AICompanionCreateRequest(
        user_mail_id="user@example.com",
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

    assert CompanionService._generate_ai_companion_title(payload) == "Anime Playful Companion"
