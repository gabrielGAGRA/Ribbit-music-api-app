"""Unit tests for user and admin authentication dependencies."""

from unittest.mock import MagicMock

import pytest

from app.domain.exceptions import (
    AuthenticationRequiredError,
    PermissionDeniedError,
)
from app.domain.models import User
from app.presentation.dependencies.auth import (
    get_admin_id,
    get_current_user_id,
    require_admin,
    require_user,
)


def test_get_current_user_id_bearer_token() -> None:
    user_id = get_current_user_id(authorization="Bearer 42")
    assert user_id == 42


def test_get_current_user_id_raw_authorization_header() -> None:
    user_id = get_current_user_id(authorization="100")
    assert user_id == 100


def test_get_current_user_id_x_user_id_header() -> None:
    user_id = get_current_user_id(x_user_id="77")
    assert user_id == 77


def test_get_current_user_id_query_param_fallback() -> None:
    user_id = get_current_user_id(user_id="88")
    assert user_id == 88


def test_get_current_user_id_precedence() -> None:
    assert (
        get_current_user_id(authorization="Bearer 1", x_user_id="2", user_id="3") == 1
    )
    assert get_current_user_id(x_user_id="2", user_id="3") == 2


def test_get_current_user_id_whitespace_fallback() -> None:
    assert get_current_user_id(authorization="   ", x_user_id="55") == 55
    assert get_current_user_id(authorization="   ", x_user_id="  ", user_id="66") == 66


def test_get_current_user_id_missing_all_raises_error() -> None:
    with pytest.raises(AuthenticationRequiredError, match="Authentication required"):
        get_current_user_id()


def test_get_current_user_id_invalid_int_raises_error() -> None:
    with pytest.raises(AuthenticationRequiredError, match="Invalid user ID"):
        get_current_user_id(authorization="Bearer not_a_number")

    with pytest.raises(AuthenticationRequiredError, match="Invalid user ID"):
        get_current_user_id(authorization="CustomScheme token extra")

    with pytest.raises(AuthenticationRequiredError, match="Invalid user ID"):
        get_current_user_id(x_user_id="invalid")

    with pytest.raises(AuthenticationRequiredError, match="Invalid user ID"):
        get_current_user_id(user_id="bad_id")


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


def test_get_admin_id_valid_header_returns_int() -> None:
    assert get_admin_id(header="1") == 1


def test_get_admin_id_missing_header_raises_error() -> None:
    with pytest.raises(
        AuthenticationRequiredError, match="Administrator ID header missing"
    ):
        get_admin_id(header=None)


def test_get_admin_id_invalid_int_raises_error() -> None:
    with pytest.raises(
        AuthenticationRequiredError, match="Invalid administrator ID header"
    ):
        get_admin_id(header="not_an_int")


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
