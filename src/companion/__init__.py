"""Expose the supported companion package API."""

from src.companion.exceptions import (
    AICompanionNotFoundError,
    CompanionError,
    CompanionNotFoundError,
    UserNotRegisteredError,
)
from src.companion.schemas import (
    AICompanionCreateRequest,
    AICompanionCreateResponse,
    AICompanionGenerateRequest,
    AICompanionGenerateResponse,
    AICompanionResponse,
)
from src.companion.service import CompanionService

__all__ = [
    "AICompanionCreateRequest",
    "AICompanionCreateResponse",
    "AICompanionGenerateRequest",
    "AICompanionGenerateResponse",
    "AICompanionNotFoundError",
    "AICompanionResponse",
    "CompanionError",
    "CompanionNotFoundError",
    "CompanionService",
    "UserNotRegisteredError",
]
