"""Application services for user and AI companion HTTP endpoints."""

from __future__ import annotations

import re

from pydantic import ValidationError

from src.Logging import get_logger
from src.companion.exceptions import AICompanionNotFoundError, UserNotRegisteredError
from src.companion.schemas import (
    AICompanionCreateRequest,
    AICompanionCreateResponse,
    AICompanionGenerateRequest,
    AICompanionGenerateResponse,
    AICompanionMetadata,
    AICompanionResponse,
    normalize_user_mail_id,
)
from src.backend.runtime import BaseInferenceRuntime
from src.backend.schemas import ChatMessage, InferencePromptRequest
from src.storage.models import AICompanionRecord, UserRecord
from src.storage.repositories import (
    SQLiteAICompanionRepository,
    SQLiteUserRepository,
)
from src.prompts import (
    AI_COMPANION_FIXED_NAME_INSTRUCTION,
    AI_COMPANION_METADATA_PROMPT,
    AI_COMPANION_NAME_CORRECTION_INSTRUCTION,
    AI_COMPANION_TITLE_INSTRUCTION,
    METADATA_SYSTEM_PROMPT,
)

logger = get_logger(__name__)


class CompanionService:
    """Coordinate request validation, user lookup, and persistence."""

    def __init__(
            self,
            user_repository: SQLiteUserRepository,
            ai_companion_repository: SQLiteAICompanionRepository,
            runtime: BaseInferenceRuntime,
    ):
        self.user_repository = user_repository
        self.ai_companion_repository = ai_companion_repository
        self.runtime = runtime

    async def create_ai_companion(self, payload: AICompanionCreateRequest) -> AICompanionCreateResponse:
        """Persist a new AI companion persona and return its identifier and metadata."""
        logger.info("Creating AI companion email=%s title=%s", payload.user_mail_id, payload.title or "auto")
        user = self._get_user_by_email(payload.user_mail_id)
        if payload.title and payload.description:
            title = payload.title
            description = payload.description
            logger.info("Using provided AI companion metadata email=%s", payload.user_mail_id)
        else:
            metadata = await self._generate_ai_companion_metadata(
                gender=payload.gender,
                visual_style=payload.visual_style,
                companion_ethnicity=payload.companion_ethnicity,
                eye_color=payload.eye_color,
                age=payload.age,
                hair_length=payload.hair_length,
                hair_style=payload.hair_style,
                hair_color=payload.hair_color,
                companion_personality=payload.companion_personality,
                companion_profession=payload.companion_profession,
                body_type=payload.body_type,
                bust=payload.bust,
                height=payload.height,
                intention=payload.intention,
                companion_name=payload.title,
            )

            title = payload.title or metadata.title
            description = payload.description or metadata.description

        record = self.ai_companion_repository.create(
            user_id=user.id,
            title=title,
            description=description,
            gender=payload.gender,
            visual_style=payload.visual_style,
            companion_ethnicity=payload.companion_ethnicity,
            eye_color=payload.eye_color,
            age=payload.age,
            hair_length=payload.hair_length,
            hair_style=payload.hair_style,
            hair_color=payload.hair_color,
            companion_personality=payload.companion_personality,
            companion_profession=payload.companion_profession,
            body_type=payload.body_type,
            bust=payload.bust,
            height=payload.height,
            intention=payload.intention,
        )
        logger.info("Created AI companion user_id=%s email=%s ai_companion_id=%s", user.id, user.email, record.id)
        return AICompanionCreateResponse(ai_companion_id=record.id, title=title, description=description)

    async def generate_ai_companion(self, payload: AICompanionGenerateRequest) -> AICompanionGenerateResponse:
        """Generate AI companion metadata directly from the LLM without persistence."""
        logger.info(
            "Generating AI companion metadata directly visual_style=%s personality=%s intention=%s",
            payload.visual_style,
            payload.companion_personality,
            payload.intention,
        )
        metadata = await self._generate_ai_companion_metadata(
            gender=payload.gender,
            visual_style=payload.visual_style,
            companion_ethnicity=payload.companion_ethnicity,
            eye_color=payload.eye_color,
            age=payload.age,
            hair_length=payload.hair_length,
            hair_style=payload.hair_style,
            hair_color=payload.hair_color,
            companion_personality=payload.companion_personality,
            companion_profession=payload.companion_profession,
            body_type=payload.body_type,
            bust=payload.bust,
            height=payload.height,
            intention=payload.intention,
            companion_name=None,
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

    def _get_user_by_email(self, user_mail_id: str) -> UserRecord:
        normalized_email = normalize_user_mail_id(user_mail_id)
        user = self.user_repository.find_by_email(normalized_email)
        if user is None:
            logger.warning("User lookup failed email=%s", normalized_email)
            raise UserNotRegisteredError("User not registered.")
        logger.debug("Resolved user email=%s user_id=%s", user.email, user.id)
        return user

    @staticmethod
    def _build_ai_companion_response(user_mail_id: str, record: AICompanionRecord) -> AICompanionResponse:
        return AICompanionResponse(
            id=record.id,
            user_mail_id=user_mail_id,
            title=record.title,
            description=record.description,
            gender=record.gender,
            visual_style=record.visual_style,
            companion_ethnicity=record.companion_ethnicity,
            eye_color=record.eye_color,
            age=record.age,
            hair_length=record.hair_length,
            hair_style=record.hair_style,
            hair_color=record.hair_color,
            companion_personality=record.companion_personality,
            companion_profession=record.companion_profession,
            body_type=record.body_type,
            bust=record.bust,
            height=record.height,
            intention=record.intention,
        )

    async def _generate_ai_companion_metadata(
            self,
            *,
            gender: str,
            visual_style: str,
            companion_ethnicity: str,
            eye_color: str,
            age: int,
            hair_length: str,
            hair_style: str,
            hair_color: str,
            companion_personality: str,
            companion_profession: str,
            body_type: str,
            bust: str,
            height: str,
            intention: str,
            companion_name: str | None,
    ) -> AICompanionMetadata:
        """Generate companion metadata, honouring a caller-supplied companion name when present.

        When `companion_name` is supplied it is injected into the prompt so the generated
        description refers to the companion by that name. Without it the model is asked to
        invent a name and use it consistently.
        """
        prompt = AI_COMPANION_METADATA_PROMPT.format(
            gender=gender,
            visual_style=visual_style,
            companion_ethnicity=companion_ethnicity,
            eye_color=eye_color,
            age=age,
            hair_length=hair_length,
            hair_style=hair_style,
            hair_color=hair_color,
            companion_personality=companion_personality,
            companion_profession=companion_profession,
            body_type=body_type,
            bust=bust,
            height=height,
            intention=intention,
        )

        fixed_name = self._sanitize_companion_name(companion_name)
        if fixed_name is None:
            return await self._request_ai_companion_metadata(
                prompt=prompt + AI_COMPANION_TITLE_INSTRUCTION,
                system_prompt_suffix=" and a name",
            )

        prompt += AI_COMPANION_FIXED_NAME_INSTRUCTION.format(companion_name=fixed_name)
        metadata = await self._request_ai_companion_metadata(prompt=prompt, system_prompt_suffix="")
        wrong_name = self._find_conflicting_name(metadata, fixed_name)
        if wrong_name is not None:
            logger.warning(
                "Generated description used name=%s instead of requested companion name=%s; retrying once",
                wrong_name,
                fixed_name,
            )
            metadata = await self._request_ai_companion_metadata(
                prompt=prompt + AI_COMPANION_NAME_CORRECTION_INSTRUCTION.format(
                    companion_name=fixed_name,
                    wrong_name=wrong_name,
                ),
                system_prompt_suffix="",
            )
            if self._find_conflicting_name(metadata, fixed_name) is not None:
                logger.error(
                    "Description still conflicts with requested companion name=%s after retry",
                    fixed_name,
                )

        return metadata.model_copy(update={"title": fixed_name})

    async def _request_ai_companion_metadata(self, *, prompt: str, system_prompt_suffix: str) -> AICompanionMetadata:
        """Run one structured metadata inference call and parse the JSON response."""
        req = InferencePromptRequest(
            system_prompt=f"{METADATA_SYSTEM_PROMPT} Generate a description{system_prompt_suffix}.",
            messages=[ChatMessage(role="user", content=prompt)],
            json_schema=AICompanionMetadata.model_json_schema(),
        )
        metadata_text = await self.runtime.generate_text(req)
        try:
            return AICompanionMetadata.model_validate_json(metadata_text.strip())
        except ValidationError:
            logger.error("AI companion metadata response failed schema validation raw_length=%s", len(metadata_text))
            raise

    @staticmethod
    def _sanitize_companion_name(companion_name: str | None) -> str | None:
        """Collapse a caller-supplied companion name into a single prompt-safe line."""
        if companion_name is None:
            return None
        normalized = " ".join(companion_name.split())
        return normalized or None

    @staticmethod
    def _find_conflicting_name(metadata: AICompanionMetadata, companion_name: str) -> str | None:
        """Return the rogue name the description used instead of `companion_name`, if any.

        Structured decoding emits `title` before `description`, so a title that differs from
        the requested name and also appears in the description means the model renamed the
        companion mid-generation.
        """
        generated_title = metadata.title.strip()
        if not generated_title or generated_title.casefold() == companion_name.casefold():
            return None
        if re.search(rf"\b{re.escape(generated_title)}\b", metadata.description, flags=re.IGNORECASE):
            return generated_title
        return None
