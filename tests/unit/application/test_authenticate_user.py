"""Unit tests for AuthenticateUserUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.auth_dtos import AuthenticateUserCommand
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.ports.services.password_hasher import PasswordHasherPort
from app.application.use_cases.auth.authenticate_user import AuthenticateUserUseCase
from app.domain.exceptions import AuthenticationRequiredError
from app.domain.models.user import User


def test_authenticate_user_success_normalizes_email_and_returns_user() -> None:
    user = User(
        user_id=10,
        email="frog@ribbit.com",
        password_hash="hashed_pw",
        display_name="Frog",
        age=21,
        plan_id=1,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_email.return_value = user

    password_hasher = MagicMock(spec=PasswordHasherPort)
    password_hasher.verify_password.return_value = True

    use_case = AuthenticateUserUseCase(
        user_repo=user_repo,
        password_hasher=password_hasher,
    )
    command = AuthenticateUserCommand(
        email="  FROG@Ribbit.com ",
        password="secret_password",
    )

    result = use_case.execute(command)

    assert result.user is user
    assert result.user_id == 10
    user_repo.find_by_email.assert_called_once_with("frog@ribbit.com")
    password_hasher.verify_password.assert_called_once_with(
        "secret_password",
        "hashed_pw",
    )


def test_authenticate_user_with_token_service_generates_bearer_token() -> None:
    from app.application.ports.services.token_service import TokenServicePort

    user = User(
        user_id=10,
        email="frog@ribbit.com",
        password_hash="hashed_pw",
        display_name="Frog",
        age=21,
        plan_id=1,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_email.return_value = user

    password_hasher = MagicMock(spec=PasswordHasherPort)
    password_hasher.verify_password.return_value = True

    token_service = MagicMock(spec=TokenServicePort)
    token_service.create_access_token.return_value = "mock_bearer_jwt_token"

    use_case = AuthenticateUserUseCase(
        user_repo=user_repo,
        password_hasher=password_hasher,
        token_service=token_service,
    )
    command = AuthenticateUserCommand(
        email="frog@ribbit.com",
        password="secret_password",
    )

    result = use_case.execute(command)

    assert result.user is user
    assert result.access_token == "mock_bearer_jwt_token"
    token_service.create_access_token.assert_called_once_with(
        user_id=10, is_admin=False
    )


def test_authenticate_user_not_found_raises_authentication_required() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_email.return_value = None
    password_hasher = MagicMock(spec=PasswordHasherPort)

    use_case = AuthenticateUserUseCase(
        user_repo=user_repo,
        password_hasher=password_hasher,
    )
    command = AuthenticateUserCommand(
        email="missing@ribbit.com",
        password="secret_password",
    )

    with pytest.raises(AuthenticationRequiredError, match="Invalid credentials"):
        use_case.execute(command)

    password_hasher.verify_password.assert_not_called()


def test_authenticate_user_invalid_password_raises_authentication_required() -> None:
    user = User(
        user_id=10,
        email="frog@ribbit.com",
        password_hash="hashed_pw",
        display_name="Frog",
        age=21,
        plan_id=1,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_email.return_value = user

    password_hasher = MagicMock(spec=PasswordHasherPort)
    password_hasher.verify_password.return_value = False

    use_case = AuthenticateUserUseCase(
        user_repo=user_repo,
        password_hasher=password_hasher,
    )
    command = AuthenticateUserCommand(
        email="frog@ribbit.com",
        password="bad_password",
    )

    with pytest.raises(AuthenticationRequiredError, match="Invalid credentials"):
        use_case.execute(command)
