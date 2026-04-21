"""Companion-domain exception hierarchy."""


class CompanionError(RuntimeError):
    """Base companion-domain failure."""


class CompanionNotFoundError(CompanionError):
    """Raised when a requested companion resource cannot be found."""


class UserNotRegisteredError(CompanionNotFoundError):
    """Raised when the provided email does not map to a user."""


class UserCompanionNotFoundError(CompanionNotFoundError):
    """Raised when a user's companion preferences have not been created yet."""


class AICompanionNotFoundError(CompanionNotFoundError):
    """Raised when an AI companion does not exist."""
