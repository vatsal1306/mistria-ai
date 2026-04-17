"""Application services for user and AI companion HTTP endpoints."""

from __future__ import annotations

from src.companion.contracts import UserCompanionLabelCatalog
from src.companion.exceptions import AICompanionNotFoundError, UserCompanionNotFoundError, UserNotRegisteredError
from src.companion.schemas import (
    AICompanionCreateRequest,
    AICompanionIdentifierResponse,
    AICompanionResponse,
    UserCompanionResponse,
    UserCompanionUpsertRequest,
    normalize_user_mail_id,
)
from src.storage.models import AICompanionRecord, UserCompanionRecord, UserRecord
from src.storage.repositories import (
    SQLiteAICompanionRepository,
    SQLiteUserCompanionRepository,
    SQLiteUserRepository,
)


class CompanionService:
    """Coordinate request validation, user lookup, and persistence."""

    def __init__(
            self,
            user_repository: SQLiteUserRepository,
            user_companion_repository: SQLiteUserCompanionRepository,
            ai_companion_repository: SQLiteAICompanionRepository,
    ):
        self.user_repository = user_repository
        self.user_companion_repository = user_companion_repository
        self.ai_companion_repository = ai_companion_repository

    def upsert_user_companion(self, payload: UserCompanionUpsertRequest) -> UserCompanionResponse:
        """Create or replace the saved user-companion preferences for one user."""
        user = self._get_user_by_email(payload.user_mail_id)
        self.user_companion_repository.upsert(
            user_id=user.id,
            intent_type=payload.intent_type,
            dominance_mode=payload.dominance_mode,
            intensity_level=payload.intensity_level,
            silence_response=payload.silence_response,
            secret_desire=payload.secret_desire,
        )
        return self.get_user_companion(user.email)

    def get_user_companion(self, user_mail_id: str) -> UserCompanionResponse:
        """Load the stored user-companion preferences for the given email address."""
        user = self._get_user_by_email(user_mail_id)
        record = self.user_companion_repository.find_by_user_id(user.id)
        if record is None:
            raise UserCompanionNotFoundError("User companion preferences not found.")
        return self._build_user_companion_response(user.email, record)

    def create_ai_companion(self, payload: AICompanionCreateRequest) -> AICompanionIdentifierResponse:
        """Persist a new AI companion persona and return only its identifier."""
        user = self._get_user_by_email(payload.user_mail_id)
        title = payload.title or self._generate_ai_companion_title(payload)
        record = self.ai_companion_repository.create(
            user_id=user.id,
            title=title,
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
        return AICompanionIdentifierResponse(id=record.id)

    def list_ai_companions(self, user_mail_id: str) -> list[AICompanionResponse]:
        """Return every AI companion persona owned by the given user."""
        user = self._get_user_by_email(user_mail_id)
        records = self.ai_companion_repository.list_by_user_id(user.id)
        return [self._build_ai_companion_response(user.email, record) for record in records]

    def get_ai_companion(self, ai_companion_id: int) -> AICompanionResponse:
        """Load one AI companion persona by id."""
        record = self.ai_companion_repository.find_by_id(ai_companion_id)
        if record is None:
            raise AICompanionNotFoundError("AI companion not found.")

        user = self.user_repository.find_by_id(record.user_id)
        if user is None:
            raise AICompanionNotFoundError("AI companion not found.")

        return self._build_ai_companion_response(user.email, record)

    def get_latest_ai_companion(self, user_mail_id: str) -> AICompanionResponse:
        """Return the most recently created AI companion persona for a user."""
        user = self._get_user_by_email(user_mail_id)
        record = self.ai_companion_repository.find_latest_by_user_id(user.id)
        if record is None:
            raise AICompanionNotFoundError("AI companion not found.")
        return self._build_ai_companion_response(user.email, record)

    def get_user_companion_labels(self, user_mail_id: str) -> dict[str, str]:
        """Resolve label metadata for the stored user-companion selections."""
        user = self._get_user_by_email(user_mail_id)
        record = self.user_companion_repository.find_by_user_id(user.id)
        if record is None:
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
        user = self.user_repository.find_by_email(normalize_user_mail_id(user_mail_id))
        if user is None:
            raise UserNotRegisteredError("User not registered.")
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
        )

    @staticmethod
    def _build_ai_companion_response(user_mail_id: str, record: AICompanionRecord) -> AICompanionResponse:
        return AICompanionResponse(
            id=record.id,
            user_mail_id=user_mail_id,
            title=record.title,
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
