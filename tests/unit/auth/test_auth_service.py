"""Unit tests for password encryption and authentication services."""

from __future__ import annotations

from unittest import mock

import pytest
from cryptography.fernet import Fernet

from src.auth.crypto import PasswordCipher
from src.auth.exceptions import EncryptionConfigurationError, InvalidCredentialsError, UserAlreadyExistsError
from src.auth.service import AuthService
from src.storage.models import UserRecord


class _UserRepositoryStub:
    def __init__(self, user: UserRecord | None = None):
        self.user = user
        self.created_payloads: list[dict[str, str | None]] = []

    def find_by_email(self, email: str) -> UserRecord | None:
        if self.user is not None and self.user.email == email:
            return self.user
        return None

    def create_user(self, email: str, name: str, encrypted_password: str | None) -> UserRecord:
        self.created_payloads.append(
            {"email": email, "name": name, "encrypted_password": encrypted_password}
        )
        return UserRecord(
            id=7,
            email=email,
            name=name,
            encrypted_password=encrypted_password,
            created_at="2026-04-24 09:00:00",
        )


def test_password_cipher_encrypts_and_verifies_with_derived_key():
    cipher = PasswordCipher("plain-secret")

    encrypted = cipher.encrypt("correct horse")

    assert encrypted != "correct horse"
    assert cipher.verify("correct horse", encrypted) is True
    assert cipher.verify("wrong", encrypted) is False
    assert cipher.verify("correct horse", None) is False
    assert cipher.verify("correct horse", "not-a-token") is False


def test_password_cipher_accepts_fernet_key_as_is():
    key = Fernet.generate_key().decode("utf-8")
    cipher = PasswordCipher(key)

    encrypted = cipher.encrypt("secret")

    assert cipher.verify("secret", encrypted) is True


def test_password_cipher_requires_secret_key():
    with pytest.raises(EncryptionConfigurationError, match="not configured"):
        PasswordCipher("")


def test_password_cipher_wraps_invalid_normalized_key(monkeypatch):
    monkeypatch.setattr("src.auth.crypto.Fernet", mock.Mock(side_effect=ValueError("bad key")))

    with pytest.raises(EncryptionConfigurationError, match="invalid"):
        PasswordCipher("bad-key")


def test_auth_service_registers_new_user():
    repository = _UserRepositoryStub()
    cipher = mock.Mock(spec=PasswordCipher)
    cipher.encrypt.return_value = "encrypted"
    service = AuthService(repository, cipher)

    user = service.register_user("user@example.com", "User", "password")

    assert user.id == 7
    assert user.encrypted_password == "encrypted"
    cipher.encrypt.assert_called_once_with("password")
    assert repository.created_payloads == [
        {"email": "user@example.com", "name": "User", "encrypted_password": "encrypted"}
    ]


def test_auth_service_rejects_duplicate_registration(sample_user):
    service = AuthService(_UserRepositoryStub(sample_user), mock.Mock(spec=PasswordCipher))

    with pytest.raises(UserAlreadyExistsError):
        service.register_user(sample_user.email, sample_user.name, "password")


def test_auth_service_authenticates_valid_credentials(sample_user):
    cipher = mock.Mock(spec=PasswordCipher)
    cipher.verify.return_value = True
    service = AuthService(_UserRepositoryStub(sample_user), cipher)

    assert service.find_user_by_email(sample_user.email) == sample_user
    assert service.authenticate(sample_user.email, "password") == sample_user
    cipher.verify.assert_called_once_with("password", sample_user.encrypted_password)


def test_auth_service_rejects_missing_user_and_bad_password(sample_user):
    missing_service = AuthService(_UserRepositoryStub(None), mock.Mock(spec=PasswordCipher))
    with pytest.raises(InvalidCredentialsError):
        missing_service.authenticate("missing@example.com", "password")

    cipher = mock.Mock(spec=PasswordCipher)
    cipher.verify.return_value = False
    bad_password_service = AuthService(_UserRepositoryStub(sample_user), cipher)
    with pytest.raises(InvalidCredentialsError):
        bad_password_service.authenticate(sample_user.email, "wrong")
