"""Unit tests for authentication router functions."""

from unittest.mock import MagicMock

from app.application.dtos import AuthenticateUserCommand, RegisterUserCommand
from app.application.dtos.auth_dtos import AuthResult
from app.application.ports.services.token_service import TokenServicePort
from app.application.use_cases.auth import (
    AuthenticateUserUseCase,
    RegisterUserUseCase,
)
from app.domain.models import User
from app.presentation.routers.auth import login, register
from app.presentation.schemas import LoginRequest, RegisterUserRequest


def test_register_issues_bearer_token_and_returns_user() -> None:
    mock_use_case = MagicMock(spec=RegisterUserUseCase)
    token_service = MagicMock(spec=TokenServicePort)
    user = User(
        user_id=1,
        email="new@ribbit.com",
        password_hash="hashed",
        display_name="New Frog",
        age=21,
        plan_id=2,
        blocked_genres=["Jazz"],
    )
    mock_use_case.execute.return_value = user
    token_service.create_access_token.return_value = "signed-token"
    req = RegisterUserRequest(
        email="new@ribbit.com",
        password="test-password",
        display_name="New Frog",
        age=21,
        plan_id=2,
        blocked_genres=["Jazz"],
    )

    res = register(req=req, use_case=mock_use_case, token_service=token_service)

    assert res.access_token == "signed-token"
    assert res.token_type == "bearer"
    assert res.user.user_id == 1
    token_service.create_access_token.assert_called_once_with(user_id=1, is_admin=False)
    mock_use_case.execute.assert_called_once_with(
        RegisterUserCommand(
            email="new@ribbit.com",
            password="test-password",
            display_name="New Frog",
            age=21,
            plan_id=2,
            birth_date=None,
            blocked_genres=("Jazz",),
        )
    )


def test_login_returns_authentication_result() -> None:
    mock_use_case = MagicMock(spec=AuthenticateUserUseCase)
    user = User(
        user_id=5,
        email="member@ribbit.com",
        password_hash="hashed",
        display_name="Member",
        age=28,
        plan_id=1,
    )
    mock_use_case.execute.return_value = AuthResult(
        user=user,
        access_token="signed-token",
    )
    req = LoginRequest(email="member@ribbit.com", password="test-password")

    res = login(req=req, use_case=mock_use_case)

    assert res.access_token == "signed-token"
    assert res.token_type == "bearer"
    assert res.user.user_id == 5
    mock_use_case.execute.assert_called_once_with(
        AuthenticateUserCommand(
            email="member@ribbit.com",
            password="test-password",
        )
    )


def test_auth_router_exposes_only_english_routes() -> None:
    from app.presentation.routers.auth import router

    paths = [getattr(route, "path", None) for route in router.routes]
    assert paths == ["/api/auth/register", "/api/auth/login", "/api/auth/google"]


def test_auth_router_google_login_success() -> None:
    from app.application.dtos.auth_dtos import (
        AuthenticateWithGoogleCommand,
        AuthResult,
    )
    from app.application.use_cases.auth.authenticate_with_google import (
        AuthenticateWithGoogleUseCase,
    )
    from app.presentation.routers.auth import login_with_google
    from app.presentation.schemas.auth import GoogleLoginRequest

    mock_use_case = MagicMock(spec=AuthenticateWithGoogleUseCase)
    mock_use_case.execute.return_value = AuthResult(
        user=User(
            user_id=12,
            email="google@ribbit.com",
            password_hash="oauth_dummy",
            display_name="Google User",
            plan_id=1,
        ),
        access_token="google_access_jwt",
    )

    response = login_with_google(
        req=GoogleLoginRequest(id_token="valid_id_token"),
        use_case=mock_use_case,
    )

    assert response.access_token == "google_access_jwt"
    assert response.user.email == "google@ribbit.com"
    mock_use_case.execute.assert_called_once_with(
        AuthenticateWithGoogleCommand(id_token="valid_id_token")
    )
