"""User authentication orchestration."""

from __future__ import annotations

from src.auth.crypto import PasswordCipher
from src.auth.exceptions import InvalidCredentialsError, UserAlreadyExistsError
from src.storage.models import UserRecord
from src.storage.repositories import UserRepository


class AuthService:
    """Handle user lookup, signup, and login."""

    def __init__(self, user_repository: UserRepository, password_cipher: PasswordCipher):
        self.user_repository = user_repository
        self.password_cipher = password_cipher

    def find_user_by_email(self, email: str) -> UserRecord | None:
        return self.user_repository.find_by_email(email)

    def register_user(self, email: str, name: str, password: str) -> UserRecord:
        if self.user_repository.find_by_email(email) is not None:
            raise UserAlreadyExistsError("An account with this email already exists.")

        encrypted_password = self.password_cipher.encrypt(password)
        return self.user_repository.create_user(email=email, name=name, encrypted_password=encrypted_password)

    def authenticate(self, email: str, password: str) -> UserRecord:
        user = self.user_repository.find_by_email(email)
        if user is None:
            raise InvalidCredentialsError("Invalid email or password.")
        if not self.password_cipher.verify(password, user.encrypted_password):
            raise InvalidCredentialsError("Invalid email or password.")
        return user
