"""Unit tests for HMACTokenService."""

import pytest

from app.domain.exceptions import AuthenticationRequiredError
from app.infrastructure.security.token_service import HMACTokenService


def test_create_and_decode_valid_access_token() -> None:
    service = HMACTokenService(secret_key="my-very-secret-test-key-32-chars")
    token = service.create_access_token(
        user_id=123, is_admin=False, expires_in_seconds=3600
    )

    assert isinstance(token, str)
    parts = token.split(".")
    assert len(parts) == 3

    payload = service.decode_access_token(token)
    assert payload["sub"] == "123"
    assert payload["is_admin"] is False
    assert "exp" in payload
    assert "iat" in payload


def test_create_and_decode_admin_access_token() -> None:
    service = HMACTokenService(secret_key="my-very-secret-test-key-32-chars")
    token = service.create_access_token(user_id=1, is_admin=True)

    payload = service.decode_access_token(token)
    assert payload["sub"] == "1"
    assert payload["is_admin"] is True


def test_decode_token_with_tampered_signature_raises_error() -> None:
    service = HMACTokenService(secret_key="my-very-secret-test-key-32-chars")
    token = service.create_access_token(user_id=123, is_admin=False)
    header, payload, sig = token.split(".")

    # Tamper first character of signature to guarantee data bits difference
    tampered_sig = ("B" if sig[0] == "A" else "A") + sig[1:]
    tampered_token = f"{header}.{payload}.{tampered_sig}"

    with pytest.raises(AuthenticationRequiredError, match="Invalid token signature"):
        service.decode_access_token(tampered_token)


def test_decode_token_with_tampered_padding_bits_raises_error() -> None:
    service = HMACTokenService(secret_key="my-very-secret-test-key-32-chars")
    token = service.create_access_token(user_id=123, is_admin=False)
    header, payload, sig = token.split(".")

    # A 32-byte SHA256 digest produces 43 base64url characters.
    # The 43rd character has 2 unused padding bits.
    # Tampering unused padding bits must be rejected to prevent signature malleability.
    b64_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    last_char = sig[-1]
    last_char_idx = b64_chars.index(last_char)
    tampered_sig = sig[:-1] + b64_chars[last_char_idx ^ 1]
    tampered_token = f"{header}.{payload}.{tampered_sig}"

    with pytest.raises(AuthenticationRequiredError):
        service.decode_access_token(tampered_token)


def test_decode_token_signed_with_different_secret_raises_error() -> None:
    service_a = HMACTokenService(secret_key="secret-key-a-1234567890123456789")
    service_b = HMACTokenService(secret_key="secret-key-b-1234567890123456789")

    token = service_a.create_access_token(user_id=42)

    with pytest.raises(AuthenticationRequiredError, match="Invalid token signature"):
        service_b.decode_access_token(token)


def test_decode_expired_token_raises_error() -> None:
    service = HMACTokenService(secret_key="my-very-secret-test-key-32-chars")
    # Expired 10 seconds ago
    token = service.create_access_token(user_id=123, expires_in_seconds=-10)

    with pytest.raises(AuthenticationRequiredError, match="Token has expired"):
        service.decode_access_token(token)


def test_decode_malformed_token_format_raises_error() -> None:
    service = HMACTokenService(secret_key="my-very-secret-test-key-32-chars")

    with pytest.raises(AuthenticationRequiredError, match="Invalid token format"):
        service.decode_access_token("not-a-jwt")

    with pytest.raises(AuthenticationRequiredError, match="Invalid token format"):
        service.decode_access_token("part1.part2")

    with pytest.raises(AuthenticationRequiredError, match="Invalid token format"):
        service.decode_access_token("p1.p2.p3.p4")


def test_decode_corrupted_payload_raises_error() -> None:
    service = HMACTokenService(secret_key="my-very-secret-test-key-32-chars")
    # Valid header, non-json base64 payload, dummy sig
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.bm90LWpzb24.dGVzdA"

    with pytest.raises(AuthenticationRequiredError):
        service.decode_access_token(token)


def test_empty_secret_key_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Secret key cannot be empty"):
        HMACTokenService(secret_key="")
