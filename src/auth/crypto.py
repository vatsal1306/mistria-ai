"""Password encryption helpers."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from src.Logging import get_logger
from src.auth.exceptions import EncryptionConfigurationError

logger = get_logger(__name__)


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
        logger.debug("Initialized password cipher")

    def encrypt(self, password: str) -> str:
        """Encrypt a plaintext password for storage."""
        logger.debug("Encrypting password payload")
        return self._cipher.encrypt(password.encode("utf-8")).decode("utf-8")

    def verify(self, password: str, encrypted_password: str | None) -> bool:
        """Check whether a plaintext password matches an encrypted value."""
        if not encrypted_password:
            logger.debug("Password verification skipped because stored password is empty")
            return False
        try:
            decrypted = self._cipher.decrypt(encrypted_password.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            logger.warning("Password verification failed due to invalid encrypted token")
            return False
        return decrypted == password

    @staticmethod
    def _normalize_key(secret_key: str) -> bytes:
        key_bytes = secret_key.strip().encode("utf-8")
        try:
            Fernet(key_bytes)
            logger.debug("Using provided Fernet key as-is")
            return key_bytes
        except Exception:
            derived_key = base64.urlsafe_b64encode(hashlib.sha256(key_bytes).digest())
            Fernet(derived_key)
            logger.debug("Derived Fernet-compatible key from configured secret")
            return derived_key
