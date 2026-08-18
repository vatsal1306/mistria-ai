from dataclasses import replace

import pytest

from src.companion.exceptions import AICompanionNotFoundError, UserNotRegisteredError
from src.companion.schemas import (
    AICompanionCreateRequest,
    AICompanionGenerateRequest,
    normalize_user_mail_id,
)
from src.companion.service import CompanionService
from src.storage.models import AICompanionRecord, UserRecord


class _RuntimeStub:
    def __init__(self, response_text: str, *args: str):
        self.response_texts = [response_text, *args]
        self.requests = []

    async def generate_text(self, request):
        self.requests.append(request)
        index = min(len(self.requests) - 1, len(self.response_texts) - 1)
        return self.response_texts[index]


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
            visual_style=kwargs["visual_style"],
            companion_ethnicity=kwargs["companion_ethnicity"],
            eye_color=kwargs["eye_color"],
            age=kwargs["age"],
            hair_length=kwargs["hair_length"],
            hair_style=kwargs["hair_style"],
            hair_color=kwargs["hair_color"],
            companion_personality=kwargs["companion_personality"],
            companion_profession=kwargs["companion_profession"],
            body_type=kwargs["body_type"],
            bust=kwargs["bust"],
            height=kwargs["height"],
            intention=kwargs["intention"],
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
    service = CompanionService(None, None, runtime)
    payload = AICompanionGenerateRequest(
        gender="Female",
        visual_style="Retro Noir",
        companion_ethnicity="South Asian",
        eye_color="Hazel",
        age="28",
        hair_length="Long",
        hair_style="Pixie",
        hair_color="Black",
        companion_personality="Mysterious",
        companion_profession="Writer",
        body_type="Natural",
        bust="Natural",
        height="Average",
        intention="Secret Affair",
    )

    response = await service.generate_ai_companion(payload)

    assert response.title == "Nadia"
    assert "dominant presence" in response.description
    assert len(runtime.requests) == 1
    prompt = runtime.requests[0].messages[0].content
    assert "Hair Color: Black" in prompt
    assert "Intention: Secret Affair" in prompt
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
    service = CompanionService(_UserRepositoryStub(user), ai_companion_repo, runtime)
    payload = {
        "user_mail_id": "admin@example.com",
        "title": "Selene",
        "description": "A calm, observant companion with a dry wit and steady presence.",
        "gender": "Female",
        "visual_style": "Retro Noir",
        "companion_ethnicity": "South Asian",
        "eye_color": "Hazel",
        "age": "28",
        "hair_length": "Long",
        "hair_style": "Pixie",
        "hair_color": "Black",
        "companion_personality": "Mysterious",
        "companion_profession": "Writer",
        "body_type": "Natural",
        "bust": "Natural",
        "height": "Average",
        "intention": "Secret Affair",
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
            "visual_style": "Retro Noir",
            "companion_ethnicity": "South Asian",
            "eye_color": "Hazel",
            "age": 28,
            "hair_length": "Long",
            "hair_style": "Pixie",
            "hair_color": "Black",
            "companion_personality": "Mysterious",
            "companion_profession": "Writer",
            "body_type": "Natural",
            "bust": "Natural",
            "height": "Average",
            "intention": "Secret Affair",
        }
    ]


def test_normalize_user_mail_id_strips_lowercases_and_validates():
    assert normalize_user_mail_id(" Admin@Example.COM ") == "admin@example.com"
    with pytest.raises(ValueError, match="valid email"):
        normalize_user_mail_id("not-an-email")


@pytest.mark.anyio
async def test_create_ai_companion_generates_missing_metadata(sample_user):
    runtime = _RuntimeStub('{"title":"Mira","description":"A confident presence with playful control."}')
    ai_companion_repo = _AICompanionRepositoryStub()
    service = CompanionService(_UserRepositoryStub(sample_user), ai_companion_repo, runtime)

    response = await service.create_ai_companion(
        AICompanionCreateRequest(
            user_mail_id=sample_user.email,
            title=None,
            description=None,
            gender="Female",
            visual_style="Anime",
            companion_ethnicity="East Asian",
            eye_color="Brown",
            age=28,
            hair_length="Long",
            hair_style="Straight",
            hair_color="Black",
            companion_personality="Playful",
            companion_profession="Writer",
            body_type="Natural",
            bust="Natural",
            height="Average",
            intention="New Encounter",
        )
    )

    assert response.title == "Mira"
    assert response.description == "A confident presence with playful control."
    assert len(runtime.requests) == 1


def test_list_get_and_latest_ai_companion(sample_user, sample_ai_companion):
    repository = _AICompanionRepositoryStub([sample_ai_companion])
    service = CompanionService(_UserRepositoryStub(sample_user), repository, _RuntimeStub("{}"))

    listed = service.list_ai_companions(sample_user.email)
    fetched = service.get_ai_companion(sample_ai_companion.id)
    latest = service.get_latest_ai_companion(sample_user.email)

    assert [record.id for record in listed] == [sample_ai_companion.id]
    assert fetched.user_mail_id == sample_user.email
    assert latest.title == sample_ai_companion.title


def test_companion_service_raises_for_missing_users_and_records(sample_user, sample_ai_companion):
    service = CompanionService(_UserRepositoryStub(None), _AICompanionRepositoryStub(), _RuntimeStub("{}"))
    with pytest.raises(UserNotRegisteredError):
        service.list_ai_companions("missing@example.com")

    service = CompanionService(_UserRepositoryStub(sample_user), _AICompanionRepositoryStub(), _RuntimeStub("{}"))
    with pytest.raises(AICompanionNotFoundError):
        service.get_ai_companion(999)
    with pytest.raises(AICompanionNotFoundError):
        service.get_latest_ai_companion(sample_user.email)

    orphan = replace(sample_ai_companion, user_id=999)
    service = CompanionService(_UserRepositoryStub(sample_user), _AICompanionRepositoryStub([orphan]), _RuntimeStub("{}"))
    with pytest.raises(AICompanionNotFoundError):
        service.get_ai_companion(orphan.id)


def _create_payload(**overrides) -> AICompanionCreateRequest:
    payload = {
        "user_mail_id": "user@example.com",
        "title": None,
        "description": None,
        "gender": "Female",
        "visual_style": "Realistic",
        "companion_ethnicity": "East Asian",
        "eye_color": "Brown",
        "age": 24,
        "hair_length": "Medium",
        "hair_style": "Curly",
        "hair_color": "Blonde",
        "companion_personality": "Flirty",
        "companion_profession": "Bartender",
        "body_type": "Petite",
        "bust": "Natural",
        "height": "Short",
        "intention": "quick",
    }
    payload.update(overrides)
    return AICompanionCreateRequest(**payload)


@pytest.mark.anyio
async def test_create_ai_companion_passes_provided_name_into_generation_prompt(sample_user):
    runtime = _RuntimeStub('{"title":"jimmy","description":"jimmy pours drinks with a flirty, easy confidence."}')
    ai_companion_repo = _AICompanionRepositoryStub()
    service = CompanionService(_UserRepositoryStub(sample_user), ai_companion_repo, runtime)

    response = await service.create_ai_companion(
        _create_payload(user_mail_id=sample_user.email, title="jimmy")
    )

    assert response.title == "jimmy"
    assert len(runtime.requests) == 1
    prompt = runtime.requests[0].messages[0].content
    assert 'Set the `title` field to exactly "jimmy"' in prompt
    assert "exactly one word" not in prompt
    assert "jimmy" in response.description


@pytest.mark.anyio
async def test_create_ai_companion_retries_when_description_uses_a_different_name(sample_user):
    runtime = _RuntimeStub(
        '{"title":"Yuna","description":"Yuna, a 24-year-old bartender with a flirty spark."}',
        '{"title":"jimmy","description":"jimmy, a 24-year-old bartender with a flirty spark."}',
    )
    service = CompanionService(_UserRepositoryStub(sample_user), _AICompanionRepositoryStub(), runtime)

    response = await service.create_ai_companion(
        _create_payload(user_mail_id=sample_user.email, title="jimmy")
    )

    assert len(runtime.requests) == 2
    assert "Yuna" in runtime.requests[1].messages[0].content
    assert response.title == "jimmy"
    assert "Yuna" not in response.description


@pytest.mark.anyio
async def test_create_ai_companion_keeps_provided_description_and_generates_only_the_name(sample_user):
    runtime = _RuntimeStub('{"title":"Mira","description":"Generated description that must not be stored."}')
    ai_companion_repo = _AICompanionRepositoryStub()
    service = CompanionService(_UserRepositoryStub(sample_user), ai_companion_repo, runtime)

    response = await service.create_ai_companion(
        _create_payload(user_mail_id=sample_user.email, description="A steady, dry-witted bartender.")
    )

    assert response.title == "Mira"
    assert response.description == "A steady, dry-witted bartender."


@pytest.mark.anyio
async def test_create_ai_companion_does_not_retry_when_description_omits_any_name(sample_user):
    runtime = _RuntimeStub('{"title":"Yuna","description":"A petite bartender with a flirty, magnetic presence."}')
    service = CompanionService(_UserRepositoryStub(sample_user), _AICompanionRepositoryStub(), runtime)

    response = await service.create_ai_companion(
        _create_payload(user_mail_id=sample_user.email, title="jimmy")
    )

    assert len(runtime.requests) == 1
    assert response.title == "jimmy"
