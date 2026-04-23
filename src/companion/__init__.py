"""Expose the supported companion package API."""

from src.companion.contracts import UserCompanionLabelCatalog
from src.companion.exceptions import (
    AICompanionNotFoundError,
    CompanionError,
    CompanionNotFoundError,
    UserCompanionNotFoundError,
    UserNotRegisteredError,
)
from src.companion.schemas import (
    AICompanionCreateRequest,
    AICompanionCreateResponse,
    AICompanionResponse,
    CompanionMetadata,
    UserCompanionResponse,
    UserCompanionUpsertRequest,
    UserCompanionUpsertResponse,
)
from src.companion.service import CompanionService

__all__ = [
    "AICompanionCreateRequest",
    "AICompanionCreateResponse",
    "AICompanionNotFoundError",
    "AICompanionResponse",
    "CompanionError",
    "CompanionMetadata",
    "CompanionNotFoundError",
    "CompanionService",
    "UserCompanionLabelCatalog",
    "UserCompanionNotFoundError",
    "UserCompanionResponse",
    "UserCompanionUpsertRequest",
    "UserCompanionUpsertResponse",
    "UserNotRegisteredError",
]
