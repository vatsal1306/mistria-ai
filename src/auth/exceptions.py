"""Authentication-domain exception hierarchy."""


class AuthError(RuntimeError):
    """Base class for authentication failures."""


class InvalidCredentialsError(AuthError):
    """Raised when the supplied credentials do not match a user."""


class UserAlreadyExistsError(AuthError):
    """Raised when attempting to create a duplicate user."""


class EncryptionConfigurationError(AuthError):
    """Raised when the password encryption key is missing or invalid."""
