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
    AICompanionIdentifierResponse,
    AICompanionResponse,
    UserCompanionResponse,
    UserCompanionUpsertRequest,
)
from src.companion.service import CompanionService

__all__ = [
    "AICompanionCreateRequest",
    "AICompanionIdentifierResponse",
    "AICompanionNotFoundError",
    "AICompanionResponse",
    "CompanionError",
    "CompanionNotFoundError",
    "CompanionService",
    "UserCompanionLabelCatalog",
    "UserCompanionNotFoundError",
    "UserCompanionResponse",
    "UserCompanionUpsertRequest",
    "UserNotRegisteredError",
]
