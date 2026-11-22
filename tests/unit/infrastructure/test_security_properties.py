"""Property-based tests for HMACTokenService and PBKDF2PasswordHasher."""

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from app.domain.exceptions import AuthenticationRequiredError
from app.infrastructure.security.password_hasher import PBKDF2PasswordHasher
from app.infrastructure.security.token_service import HMACTokenService


@given(
    secret_key=st.text(min_size=1, max_size=64),
    user_id=st.integers(min_value=-(10**9), max_value=10**9),
    is_admin=st.booleans(),
    expires_in_seconds=st.integers(min_value=60, max_value=86400),
)
@settings(max_examples=50, deadline=None)
def test_hmac_token_service_round_trip(
    secret_key: str,
    user_id: int,
    is_admin: bool,
    expires_in_seconds: int,
) -> None:
    service = HMACTokenService(secret_key)
    token = service.create_access_token(
        user_id=user_id,
        is_admin=is_admin,
        expires_in_seconds=expires_in_seconds,
    )
    payload = service.decode_access_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["is_admin"] is is_admin


@given(
    secret_a=st.text(min_size=1, max_size=64),
    secret_b=st.text(min_size=1, max_size=64),
    user_id=st.integers(min_value=1, max_value=10**6),
    is_admin=st.booleans(),
)
@settings(max_examples=50, deadline=None)
def test_hmac_token_service_rejects_cross_secret_tokens(
    secret_a: str,
    secret_b: str,
    user_id: int,
    is_admin: bool,
) -> None:
    assume(secret_a != secret_b)
    signer = HMACTokenService(secret_a)
    verifier = HMACTokenService(secret_b)
    token = signer.create_access_token(user_id=user_id, is_admin=is_admin)

    with pytest.raises(AuthenticationRequiredError):
        verifier.decode_access_token(token)


@given(
    secret_key=st.text(min_size=1, max_size=64),
    raw_token=st.one_of(
        st.text(max_size=100),
        st.tuples(st.text(max_size=40), st.text(max_size=40), st.text(max_size=40)).map(
            ".".join
        ),
    ),
)
@settings(max_examples=50, deadline=None)
def test_hmac_token_service_rejects_arbitrary_tokens(
    secret_key: str,
    raw_token: str,
) -> None:
    service = HMACTokenService(secret_key)

    with pytest.raises(AuthenticationRequiredError):
        service.decode_access_token(raw_token)


@given(password=st.text(max_size=64))
@settings(max_examples=50, deadline=None)
def test_pbkdf2_password_hasher_round_trip(password: str) -> None:
    hasher = PBKDF2PasswordHasher(iterations=1)
    hashed = hasher.hash_password(password)

    assert hasher.verify_password(password, hashed) is True


@given(password=st.text(max_size=64), other_password=st.text(max_size=64))
@settings(max_examples=50, deadline=None)
def test_pbkdf2_password_hasher_rejects_different_password(
    password: str,
    other_password: str,
) -> None:
    assume(other_password != password)
    hasher = PBKDF2PasswordHasher(iterations=1)
    hashed = hasher.hash_password(password)

    assert hasher.verify_password(other_password, hashed) is False


@given(password=st.text(max_size=64), corrupted_hash=st.text(max_size=128))
@settings(max_examples=50, deadline=None)
def test_pbkdf2_password_hasher_never_raises_on_corrupted_hash(
    password: str,
    corrupted_hash: str,
) -> None:
    hasher = PBKDF2PasswordHasher(iterations=1)
    result = hasher.verify_password(password, corrupted_hash)

    assert isinstance(result, bool)
