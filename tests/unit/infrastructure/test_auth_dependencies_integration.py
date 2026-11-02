"""Unit tests verifying auth dependencies with HMAC tokens and repositories."""

from unittest.mock import MagicMock

import pytest

from app.domain.exceptions import AuthenticationRequiredError, PermissionDeniedError
from app.domain.models import User
from app.infrastructure.security.token_service import HMACTokenService
from app.presentation.dependencies.auth import (
    get_current_user_id,
    require_admin,
    require_user,
)


def test_get_current_user_id_with_hmac_bearer_token() -> None:
    token_service = HMACTokenService(secret_key="my-test-secret-key-32chars-min")
    token = token_service.create_access_token(user_id=888)

    request = MagicMock()
    request.app.state.container.token_service = token_service

    extracted_id = get_current_user_id(
        request=request,
        authorization=f"Bearer {token}",
    )
    assert extracted_id == 888


def test_get_current_user_id_with_expired_hmac_token_raises_error() -> None:
    token_service = HMACTokenService(secret_key="my-test-secret-key-32chars-min")
    expired_token = token_service.create_access_token(
        user_id=888, expires_in_seconds=-5
    )

    request = MagicMock()
    request.app.state.container.token_service = token_service

    with pytest.raises(AuthenticationRequiredError, match="Token has expired"):
        get_current_user_id(
            request=request,
            authorization=f"Bearer {expired_token}",
        )


def test_require_user_with_token_resolves_and_populates_request_state() -> None:
    user = User(
        user_id=123,
        email="tokenuser@example.com",
        password_hash="pw",
        display_name="Token User",
        age=25,
        plan_id=1,
    )
    request = MagicMock()
    request.app.state.container.user_repo.find_by_id.return_value = user

    user_id = require_user(request=request, user_id=123)
    assert user_id == 123
    assert request.state.user == user


def test_require_admin_with_bearer_token() -> None:
    token_service = HMACTokenService(secret_key="my-test-secret-key-32chars-min")
    admin_token = token_service.create_access_token(user_id=1, is_admin=True)

    admin_user = User(
        user_id=1,
        email="admin@example.com",
        password_hash="pw",
        display_name="Admin",
        age=30,
        plan_id=1,
        is_admin=True,
    )
    request = MagicMock()
    request.app.state.container.token_service = token_service
    request.app.state.container.user_repo.find_by_id.return_value = admin_user

    result = require_admin(request=request, authorization=f"Bearer {admin_token}")
    assert result == 1
    assert request.state.admin_user == admin_user


def test_require_admin_with_non_admin_bearer_token_raises_forbidden() -> None:
    token_service = HMACTokenService(secret_key="my-test-secret-key-32chars-min")
    user_token = token_service.create_access_token(user_id=2, is_admin=False)

    regular_user = User(
        user_id=2,
        email="user@example.com",
        password_hash="pw",
        display_name="Regular",
        age=20,
        plan_id=1,
        is_admin=False,
    )
    request = MagicMock()
    request.app.state.container.token_service = token_service
    request.app.state.container.user_repo.find_by_id.return_value = regular_user

    with pytest.raises(
        PermissionDeniedError, match="Access restricted to administrators"
    ):
        require_admin(request=request, authorization=f"Bearer {user_token}")
