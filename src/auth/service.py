"""User authentication orchestration."""

from __future__ import annotations

from src.Logging import get_logger
from src.auth.crypto import PasswordCipher
from src.auth.exceptions import InvalidCredentialsError, UserAlreadyExistsError
from src.storage.models import UserRecord
from src.storage.repositories import UserRepository

logger = get_logger(__name__)


class AuthService:
    """Handle user lookup, signup, and login."""

    def __init__(self, user_repository: UserRepository, password_cipher: PasswordCipher):
        self.user_repository = user_repository
        self.password_cipher = password_cipher

    def find_user_by_email(self, email: str) -> UserRecord | None:
        """Return the user record for the given email, if it exists."""
        logger.debug("Looking up user by email in auth service email=%s", email)
        return self.user_repository.find_by_email(email)

    def register_user(self, email: str, name: str, password: str) -> UserRecord:
        """Create a new user account after enforcing email uniqueness."""
        logger.info("Registering user email=%s", email)
        if self.user_repository.find_by_email(email) is not None:
            logger.warning("Rejected duplicate user registration email=%s", email)
            raise UserAlreadyExistsError("An account with this email already exists.")

        encrypted_password = self.password_cipher.encrypt(password)
        user = self.user_repository.create_user(email=email, name=name, encrypted_password=encrypted_password)
        logger.info("Registered user user_id=%s email=%s", user.id, user.email)
        return user

    def authenticate(self, email: str, password: str) -> UserRecord:
        """Validate credentials and return the matching user record."""
        logger.info("Authenticating user email=%s", email)
        user = self.user_repository.find_by_email(email)
        if user is None:
            logger.warning("Authentication failed because user does not exist email=%s", email)
            raise InvalidCredentialsError("Invalid email or password.")
        if not self.password_cipher.verify(password, user.encrypted_password):
            logger.warning("Authentication failed because password verification failed email=%s", email)
            raise InvalidCredentialsError("Invalid email or password.")
        logger.info("Authentication succeeded user_id=%s email=%s", user.id, user.email)
        return user
