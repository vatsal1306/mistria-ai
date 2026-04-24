"""Application services for user and AI companion HTTP endpoints."""

from __future__ import annotations

from src.Logging import get_logger
from src.companion.contracts import UserCompanionLabelCatalog
from src.companion.exceptions import AICompanionNotFoundError, UserCompanionNotFoundError, UserNotRegisteredError
from src.companion.schemas import (
    AICompanionCreateRequest,
    AICompanionCreateResponse,
    AICompanionGenerateRequest,
    AICompanionGenerateResponse,
    AICompanionMetadata,
    AICompanionResponse,
    CompanionMetadata,
    UserCompanionResponse,
    UserCompanionUpsertRequest,
    UserCompanionUpsertResponse,
    normalize_user_mail_id,
)
from src.backend.runtime import BaseInferenceRuntime
from src.backend.schemas import ChatMessage, InferencePromptRequest
from src.storage.models import AICompanionRecord, UserCompanionRecord, UserRecord
from src.storage.repositories import (
    SQLiteAICompanionRepository,
    SQLiteUserCompanionRepository,
    SQLiteUserRepository,
)
from src.prompts import (
    AI_COMPANION_METADATA_PROMPT,
    AI_COMPANION_TITLE_INSTRUCTION,
    METADATA_SYSTEM_PROMPT,
    USER_COMPANION_METADATA_PROMPT,
)

logger = get_logger(__name__)


class CompanionService:
    """Coordinate request validation, user lookup, and persistence."""

    def __init__(
            self,
            user_repository: SQLiteUserRepository,
            user_companion_repository: SQLiteUserCompanionRepository,
            ai_companion_repository: SQLiteAICompanionRepository,
            runtime: BaseInferenceRuntime,
    ):
        self.user_repository = user_repository
        self.user_companion_repository = user_companion_repository
        self.ai_companion_repository = ai_companion_repository
        self.runtime = runtime

    async def upsert_user_companion(self, payload: UserCompanionUpsertRequest) -> UserCompanionUpsertResponse:
        """Create or replace the saved user-companion preferences for one user."""
        logger.info("Upserting user companion preferences email=%s", payload.user_mail_id)
        user = self._get_user_by_email(payload.user_mail_id)
        
        prompt = USER_COMPANION_METADATA_PROMPT.format(
            intent=payload.intent_type,
            dominance=payload.dominance_mode,
            intensity=payload.intensity_level,
            silence=payload.silence_response,
            secret_desire=payload.secret_desire
        )

        req = InferencePromptRequest(
            system_prompt=METADATA_SYSTEM_PROMPT,
            messages=[ChatMessage(role="user", content=prompt)],
            json_schema=CompanionMetadata.model_json_schema()
        )
        metadata_text = await self.runtime.generate_text(req)
        metadata = CompanionMetadata.model_validate_json(metadata_text.strip())
        
        self.user_companion_repository.upsert(
            user_id=user.id,
            intent_type=payload.intent_type,
            dominance_mode=payload.dominance_mode,
            intensity_level=payload.intensity_level,
            silence_response=payload.silence_response,
            secret_desire=payload.secret_desire,
            title=metadata.title,
            description=metadata.description,
        )
        logger.info("Upserted user companion preferences user_id=%s email=%s", user.id, user.email)
        return UserCompanionUpsertResponse(
            user_mail_id=payload.user_mail_id,
            title=metadata.title,
            description=metadata.description,
        )

    def get_user_companion(self, user_mail_id: str) -> UserCompanionResponse:
        """Load the stored user-companion preferences for the given email address."""
        logger.debug("Fetching user companion preferences email=%s", user_mail_id)
        user = self._get_user_by_email(user_mail_id)
        record = self.user_companion_repository.find_by_user_id(user.id)
        if record is None:
            logger.warning("User companion preferences not found user_id=%s email=%s", user.id, user.email)
            raise UserCompanionNotFoundError("User companion preferences not found.")
        return self._build_user_companion_response(user.email, record)

    async def create_ai_companion(self, payload: AICompanionCreateRequest) -> AICompanionCreateResponse:
        """Persist a new AI companion persona and return its identifier and metadata."""
        logger.info("Creating AI companion email=%s title=%s", payload.user_mail_id, payload.title or "auto")
        user = self._get_user_by_email(payload.user_mail_id)
        metadata = await self._generate_ai_companion_metadata(
            gender=payload.gender,
            style=payload.style,
            ethnicity=payload.ethnicity,
            eye_color=payload.eyeColor,
            hair_style=payload.hairStyle,
            hair_color=payload.hairColor,
            personality=payload.personality,
            voice=payload.voice,
            connection=payload.connection,
            generate_title=not payload.title,
        )

        title = payload.title or metadata.title
        description = metadata.description

        record = self.ai_companion_repository.create(
            user_id=user.id,
            title=title,
            description=description,
            gender=payload.gender,
            style=payload.style,
            ethnicity=payload.ethnicity,
            eye_color=payload.eyeColor,
            hair_style=payload.hairStyle,
            hair_color=payload.hairColor,
            personality=payload.personality,
            voice=payload.voice,
            connection_value=payload.connection,
        )
        logger.info("Created AI companion user_id=%s email=%s ai_companion_id=%s", user.id, user.email, record.id)
        return AICompanionCreateResponse(ai_companion_id=record.id, title=title, description=description)

    async def generate_ai_companion(self, payload: AICompanionGenerateRequest) -> AICompanionGenerateResponse:
        """Generate AI companion metadata directly from the LLM without persistence."""
        logger.info(
            "Generating AI companion metadata directly style=%s personality=%s voice=%s",
            payload.style,
            payload.personality,
            payload.voice,
        )
        metadata = await self._generate_ai_companion_metadata(
            gender=payload.gender,
            style=payload.style,
            ethnicity=payload.ethnicity,
            eye_color=payload.eyeColor,
            hair_style=payload.hairStyle,
            hair_color=payload.hairColor,
            personality=payload.personality,
            voice=payload.voice,
            connection=payload.connection,
            generate_title=True,
        )
        return AICompanionGenerateResponse(title=metadata.title, description=metadata.description)

    def list_ai_companions(self, user_mail_id: str) -> list[AICompanionResponse]:
        """Return every AI companion persona owned by the given user."""
        logger.debug("Listing AI companions email=%s", user_mail_id)
        user = self._get_user_by_email(user_mail_id)
        records = self.ai_companion_repository.list_by_user_id(user.id)
        logger.debug("Listed AI companions user_id=%s email=%s count=%s", user.id, user.email, len(records))
        return [self._build_ai_companion_response(user.email, record) for record in records]

    def get_ai_companion(self, ai_companion_id: int) -> AICompanionResponse:
        """Load one AI companion persona by id."""
        logger.debug("Fetching AI companion ai_companion_id=%s", ai_companion_id)
        record = self.ai_companion_repository.find_by_id(ai_companion_id)
        if record is None:
            logger.warning("AI companion not found ai_companion_id=%s", ai_companion_id)
            raise AICompanionNotFoundError("AI companion not found.")

        user = self.user_repository.find_by_id(record.user_id)
        if user is None:
            logger.error("AI companion owner missing ai_companion_id=%s owner_user_id=%s", record.id, record.user_id)
            raise AICompanionNotFoundError("AI companion not found.")

        return self._build_ai_companion_response(user.email, record)

    def get_latest_ai_companion(self, user_mail_id: str) -> AICompanionResponse:
        """Return the most recently created AI companion persona for a user."""
        logger.debug("Fetching latest AI companion email=%s", user_mail_id)
        user = self._get_user_by_email(user_mail_id)
        record = self.ai_companion_repository.find_latest_by_user_id(user.id)
        if record is None:
            logger.warning("Latest AI companion not found user_id=%s email=%s", user.id, user.email)
            raise AICompanionNotFoundError("AI companion not found.")
        return self._build_ai_companion_response(user.email, record)

    def get_user_companion_labels(self, user_mail_id: str) -> dict[str, str]:
        """Resolve label metadata for the stored user-companion selections."""
        logger.debug("Resolving user companion labels email=%s", user_mail_id)
        user = self._get_user_by_email(user_mail_id)
        record = self.user_companion_repository.find_by_user_id(user.id)
        if record is None:
            logger.warning("Cannot resolve companion labels without preferences user_id=%s email=%s", user.id, user.email)
            raise UserCompanionNotFoundError("User companion preferences not found.")
        return UserCompanionLabelCatalog.resolve_payload_labels(
            {
                "intent_type": record.intent_type,
                "dominance_mode": record.dominance_mode,
                "intensity_level": record.intensity_level,
                "silence_response": record.silence_response,
                "secret_desire": record.secret_desire,
            }
        )

    def _get_user_by_email(self, user_mail_id: str) -> UserRecord:
        normalized_email = normalize_user_mail_id(user_mail_id)
        user = self.user_repository.find_by_email(normalized_email)
        if user is None:
            logger.warning("User lookup failed email=%s", normalized_email)
            raise UserNotRegisteredError("User not registered.")
        logger.debug("Resolved user email=%s user_id=%s", user.email, user.id)
        return user

    @staticmethod
    def _build_user_companion_response(user_mail_id: str, record: UserCompanionRecord) -> UserCompanionResponse:
        return UserCompanionResponse(
            user_mail_id=user_mail_id,
            intent_type=record.intent_type,
            dominance_mode=record.dominance_mode,
            intensity_level=record.intensity_level,
            silence_response=record.silence_response,
            secret_desire=record.secret_desire,
            title=record.title,
            description=record.description,
        )

    @staticmethod
    def _build_ai_companion_response(user_mail_id: str, record: AICompanionRecord) -> AICompanionResponse:
        return AICompanionResponse(
            id=record.id,
            user_mail_id=user_mail_id,
            title=record.title,
            description=record.description,
            gender=record.gender,
            style=record.style,
            ethnicity=record.ethnicity,
            eyeColor=record.eye_color,
            hairStyle=record.hair_style,
            hairColor=record.hair_color,
            personality=record.personality,
            voice=record.voice,
            connection=record.connection,
        )

    @staticmethod
    def _generate_ai_companion_title(payload: AICompanionCreateRequest) -> str:
        return f"{payload.style} {payload.personality} Companion"

    async def _generate_ai_companion_metadata(
            self,
            *,
            gender: str,
            style: str,
            ethnicity: str,
            eye_color: str,
            hair_style: str,
            hair_color: str,
            personality: str,
            voice: str,
            connection: str,
            generate_title: bool,
    ) -> AICompanionMetadata:
        prompt = AI_COMPANION_METADATA_PROMPT.format(
            gender=gender,
            style=style,
            ethnicity=ethnicity,
            eye_color=eye_color,
            hair_style=hair_style,
            hair_color=hair_color,
            personality=personality,
            voice=voice,
            connection=connection,
        )

        title_instruction = ""
        if generate_title:
            prompt += AI_COMPANION_TITLE_INSTRUCTION
            title_instruction = " and a name"

        req = InferencePromptRequest(
            system_prompt=f"{METADATA_SYSTEM_PROMPT} Generate a description{title_instruction}.",
            messages=[ChatMessage(role="user", content=prompt)],
            json_schema=AICompanionMetadata.model_json_schema(),
        )
        metadata_text = await self.runtime.generate_text(req)
        return AICompanionMetadata.model_validate_json(metadata_text.strip())
