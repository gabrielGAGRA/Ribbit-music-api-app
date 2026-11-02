"""Unit tests for authentication router functions."""

from unittest.mock import MagicMock

from app.application.dtos import (
    AuthenticateUserCommand,
    RegisterUserCommand,
)
from app.application.use_cases.auth import (
    AuthenticateUserUseCase,
    RegisterUserUseCase,
)
from app.domain.models import User
from app.presentation.routers.auth import login, register
from app.presentation.schemas import LoginRequest, RegisterUserRequest


def test_register_forwards_command_and_returns_user_response() -> None:
    mock_use_case = MagicMock(spec=RegisterUserUseCase)
    user = User(
        user_id=1,
        email="new@ribbit.com",
        password_hash="hashed_pw",
        display_name="New Frog",
        age=21,
        plan_id=2,
    )
    mock_use_case.execute.return_value = user
    req = RegisterUserRequest(
        email="new@ribbit.com",
        password="secretpassword",
        display_name="New Frog",
        age=21,
        plan_id=2,
    )

    res = register(req=req, use_case=mock_use_case)

    assert res.user_id == 1
    assert res.email == "new@ribbit.com"
    assert res.display_name == "New Frog"
    assert res.age == 21
    assert res.plan_id == 2
    mock_use_case.execute.assert_called_once_with(
        RegisterUserCommand(
            email="new@ribbit.com",
            password="secretpassword",
            display_name="New Frog",
            age=21,
            plan_id=2,
        )
    )


def test_login_forwards_command_and_returns_user_response() -> None:
    mock_use_case = MagicMock(spec=AuthenticateUserUseCase)
    user = User(
        user_id=5,
        email="member@ribbit.com",
        password_hash="hashed_pw",
        display_name="Member",
        age=28,
        plan_id=1,
    )
    mock_use_case.execute.return_value = user
    req = LoginRequest(email="member@ribbit.com", password="mypassword")

    res = login(req=req, use_case=mock_use_case)

    assert res.user_id == 5
    assert res.email == "member@ribbit.com"
    mock_use_case.execute.assert_called_once_with(
        AuthenticateUserCommand(
            email="member@ribbit.com",
            password="mypassword",
        )
    )


def test_register_with_token_service_returns_auth_response_with_token() -> None:
    from app.application.ports.services.token_service import TokenServicePort

    mock_use_case = MagicMock(spec=RegisterUserUseCase)
    mock_token_service = MagicMock(spec=TokenServicePort)
    user = User(
        user_id=10,
        email="token@ribbit.com",
        password_hash="hashed_pw",
        display_name="Token Frog",
        age=22,
        plan_id=1,
    )
    mock_use_case.execute.return_value = user
    mock_token_service.create_access_token.return_value = "fake-jwt-token"

    req = RegisterUserRequest(
        email="token@ribbit.com",
        password="secretpassword",
        display_name="Token Frog",
        birth_date="2002-01-01",
    )

    res = register(req=req, use_case=mock_use_case, token_service=mock_token_service)

    assert res.access_token == "fake-jwt-token"
    assert res.token == "fake-jwt-token"
    assert res.token_type == "bearer"
    assert res.user.user_id == 10
    assert res.usuario.user_id == 10
    mock_token_service.create_access_token.assert_called_once_with(
        user_id=10, is_admin=False
    )


def test_login_with_auth_result_returns_auth_response() -> None:
    from app.application.dtos.auth_dtos import AuthResult

    mock_use_case = MagicMock(spec=AuthenticateUserUseCase)
    user = User(
        user_id=42,
        email="authed@ribbit.com",
        password_hash="hashed_pw",
        display_name="Authed User",
        age=30,
        plan_id=2,
    )
    mock_use_case.execute.return_value = AuthResult(
        user=user,
        access_token="authenticated-bearer-token",
    )

    req = LoginRequest(email="authed@ribbit.com", password="mypassword")
    res = login(req=req, use_case=mock_use_case)

    assert res.access_token == "authenticated-bearer-token"
    assert res.token == "authenticated-bearer-token"
    assert res.token_type == "bearer"
    assert res.user.email == "authed@ribbit.com"
    assert res.usuario.email == "authed@ribbit.com"


def test_auth_router_has_cadastrar_and_entrar_routes() -> None:
    from app.presentation.routers.auth import router

    paths = [route.path for route in router.routes]  # type: ignore[attr-defined]
    assert "/api/auth/register" in paths
    assert "/api/auth/cadastrar" in paths
    assert "/api/auth/login" in paths
    assert "/api/auth/entrar" in paths
