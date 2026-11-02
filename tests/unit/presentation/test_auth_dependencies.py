"""Unit tests for user and admin authentication dependencies."""

from unittest.mock import MagicMock

import pytest

from app.domain.exceptions import (
    AuthenticationRequiredError,
    PermissionDeniedError,
)
from app.domain.models import User
from app.infrastructure.security.token_service import HMACTokenService
from app.presentation.dependencies.auth import (
    get_current_user_id,
    require_admin,
    require_user,
)


def _request_with_token_service() -> tuple[MagicMock, HMACTokenService]:
    request = MagicMock()
    token_service = HMACTokenService(secret_key="test-signing-key")
    request.app.state.container.token_service = token_service
    return request, token_service


def test_get_current_user_id_from_bearer_token() -> None:
    request, token_service = _request_with_token_service()
    token = token_service.create_access_token(user_id=42)

    user_id = get_current_user_id(request, authorization=f"Bearer {token}")

    assert user_id == 42


@pytest.mark.parametrize(
    "authorization",
    [None, "", "42", "Bearer", "Custom token", "Bearer token with spaces"],
)
def test_get_current_user_id_rejects_non_bearer_credentials(
    authorization: str | None,
) -> None:
    request, _ = _request_with_token_service()

    with pytest.raises(AuthenticationRequiredError):
        get_current_user_id(request, authorization=authorization)


def test_require_user_success() -> None:
    user = User(
        user_id=10,
        email="user@test.com",
        password_hash="pw",
        display_name="User",
        age=25,
        plan_id=1,
    )
    request = MagicMock()
    request.app.state.container.user_repo.find_by_id.return_value = user

    result = require_user(request=request, user_id=10)

    assert result == 10
    request.app.state.container.user_repo.find_by_id.assert_called_once_with(10)


def test_require_user_not_found_raises_error() -> None:
    request = MagicMock()
    request.app.state.container.user_repo.find_by_id.return_value = None

    with pytest.raises(AuthenticationRequiredError, match="User not found"):
        require_user(request=request, user_id=999)


def test_require_admin_success() -> None:
    admin_user = User(
        user_id=1,
        email="admin@ribbit.com",
        password_hash="pw",
        display_name="Admin",
        age=30,
        plan_id=1,
        is_admin=True,
    )
    request = MagicMock()
    request.app.state.container.user_repo.find_by_id.return_value = admin_user

    result = require_admin(request=request, admin_id=1)

    assert result == 1
    request.app.state.container.user_repo.find_by_id.assert_called_once_with(1)


def test_require_admin_user_not_found_raises_authentication_error() -> None:
    request = MagicMock()
    request.app.state.container.user_repo.find_by_id.return_value = None

    with pytest.raises(
        AuthenticationRequiredError, match="Administrator user not found"
    ):
        require_admin(request=request, admin_id=404)


def test_require_admin_non_admin_user_raises_permission_denied() -> None:
    regular_user = User(
        user_id=2,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="Regular",
        age=22,
        plan_id=1,
        is_admin=False,
    )
    request = MagicMock()
    request.app.state.container.user_repo.find_by_id.return_value = regular_user

    with pytest.raises(
        PermissionDeniedError, match="Access restricted to administrators"
    ):
        require_admin(request=request, admin_id=2)
