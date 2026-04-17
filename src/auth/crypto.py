"""Password encryption helpers."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from src.auth.exceptions import EncryptionConfigurationError


class PasswordCipher:
    """Encrypt and verify passwords using a symmetric Fernet key."""

    def __init__(self, secret_key: str):
        if not secret_key:
            raise EncryptionConfigurationError(
                "MISTRIA_AUTH_ENCRYPTION_KEY is not configured. Add a valid Fernet key to .env."
            )

        try:
            self._cipher = Fernet(self._normalize_key(secret_key))
        except Exception as exc:
            raise EncryptionConfigurationError(
                "MISTRIA_AUTH_ENCRYPTION_KEY is invalid. Provide a valid secret string or Fernet key."
            ) from exc

    def encrypt(self, password: str) -> str:
        """Encrypt a plaintext password for storage."""
        return self._cipher.encrypt(password.encode("utf-8")).decode("utf-8")

    def verify(self, password: str, encrypted_password: str | None) -> bool:
        """Check whether a plaintext password matches an encrypted value."""
        if not encrypted_password:
            return False
        try:
            decrypted = self._cipher.decrypt(encrypted_password.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            return False
        return decrypted == password

    @staticmethod
    def _normalize_key(secret_key: str) -> bytes:
        key_bytes = secret_key.strip().encode("utf-8")
        try:
            Fernet(key_bytes)
            return key_bytes
        except Exception:
            derived_key = base64.urlsafe_b64encode(hashlib.sha256(key_bytes).digest())
            Fernet(derived_key)
            return derived_key
