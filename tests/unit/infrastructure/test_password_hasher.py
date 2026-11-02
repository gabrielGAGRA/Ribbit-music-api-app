"""Unit tests for PBKDF2PasswordHasher adapter."""

from app.infrastructure.security.password_hasher import (
    PBKDF2PasswordHasher,
)


def test_hash_and_verify_password_success() -> None:
    hasher = PBKDF2PasswordHasher(iterations=1_000)
    raw_password = "SuperSecretPassword123!"

    hashed = hasher.hash_password(raw_password)

    assert hashed != raw_password
    assert "$" in hashed
    assert hasher.verify_password(raw_password, hashed) is True


def test_verify_password_failure_on_wrong_password() -> None:
    hasher = PBKDF2PasswordHasher(iterations=1_000)
    raw_password = "SuperSecretPassword123!"

    hashed = hasher.hash_password(raw_password)

    assert hasher.verify_password("WrongPassword!", hashed) is False


def test_verify_password_failure_on_corrupt_hash() -> None:
    hasher = PBKDF2PasswordHasher(iterations=1_000)

    assert hasher.verify_password("Password", "invalid_hash_without_delimiter") is False
    assert hasher.verify_password("Password", "not_hex$not_hex") is False
