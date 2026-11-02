"""Unit tests for AuthenticateAdminUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.auth_dtos import AuthenticateAdminCommand
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.ports.services.password_hasher import PasswordHasherPort
from app.application.use_cases.auth.authenticate_admin import AuthenticateAdminUseCase
from app.domain.exceptions import AuthenticationRequiredError, PermissionDeniedError
from app.domain.models.user import User


def test_authenticate_admin_success_returns_admin_user() -> None:
    admin_user = User(
        user_id=1,
        email="admin@ribbit.com",
        password_hash="hashed_secret",
        display_name="Admin Frog",
        age=30,
        plan_id=1,
        is_admin=True,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_email.return_value = admin_user

    password_hasher = MagicMock(spec=PasswordHasherPort)
    password_hasher.verify_password.return_value = True

    use_case = AuthenticateAdminUseCase(
        user_repo=user_repo,
        password_hasher=password_hasher,
    )
    command = AuthenticateAdminCommand(
        email="  Admin@Ribbit.com  ",
        password="plain_password",
    )

    result = use_case.execute(command)

    assert result.user is admin_user
    assert result.is_admin is True
    user_repo.find_by_email.assert_called_once_with("admin@ribbit.com")
    password_hasher.verify_password.assert_called_once_with(
        "plain_password",
        "hashed_secret",
    )


def test_authenticate_admin_with_token_service_generates_bearer_token() -> None:
    from app.application.ports.services.token_service import TokenServicePort

    admin_user = User(
        user_id=1,
        email="admin@ribbit.com",
        password_hash="hashed_secret",
        display_name="Admin Frog",
        age=30,
        plan_id=1,
        is_admin=True,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_email.return_value = admin_user

    password_hasher = MagicMock(spec=PasswordHasherPort)
    password_hasher.verify_password.return_value = True

    token_service = MagicMock(spec=TokenServicePort)
    token_service.create_access_token.return_value = "admin_bearer_jwt_token"

    use_case = AuthenticateAdminUseCase(
        user_repo=user_repo,
        password_hasher=password_hasher,
        token_service=token_service,
    )
    command = AuthenticateAdminCommand(
        email="admin@ribbit.com",
        password="plain_password",
    )

    result = use_case.execute(command)

    assert result.user is admin_user
    assert result.access_token == "admin_bearer_jwt_token"
    token_service.create_access_token.assert_called_once_with(user_id=1, is_admin=True)


def test_authenticate_admin_user_not_found_raises_authentication_required() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_email.return_value = None
    password_hasher = MagicMock(spec=PasswordHasherPort)

    use_case = AuthenticateAdminUseCase(
        user_repo=user_repo,
        password_hasher=password_hasher,
    )
    command = AuthenticateAdminCommand(
        email="unknown@ribbit.com",
        password="secret",
    )

    with pytest.raises(AuthenticationRequiredError, match="Invalid credentials"):
        use_case.execute(command)

    password_hasher.verify_password.assert_not_called()


def test_authenticate_admin_wrong_password_raises_authentication_required() -> None:
    admin_user = User(
        user_id=1,
        email="admin@ribbit.com",
        password_hash="hashed_secret",
        display_name="Admin Frog",
        age=30,
        plan_id=1,
        is_admin=True,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_email.return_value = admin_user

    password_hasher = MagicMock(spec=PasswordHasherPort)
    password_hasher.verify_password.return_value = False

    use_case = AuthenticateAdminUseCase(
        user_repo=user_repo,
        password_hasher=password_hasher,
    )
    command = AuthenticateAdminCommand(
        email="admin@ribbit.com",
        password="wrong_password",
    )

    with pytest.raises(AuthenticationRequiredError, match="Invalid credentials"):
        use_case.execute(command)


def test_authenticate_admin_non_admin_user_raises_permission_denied() -> None:
    regular_user = User(
        user_id=2,
        email="user@ribbit.com",
        password_hash="hashed_secret",
        display_name="Regular Frog",
        age=25,
        plan_id=1,
        is_admin=False,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_email.return_value = regular_user

    password_hasher = MagicMock(spec=PasswordHasherPort)
    password_hasher.verify_password.return_value = True

    use_case = AuthenticateAdminUseCase(
        user_repo=user_repo,
        password_hasher=password_hasher,
    )
    command = AuthenticateAdminCommand(
        email="user@ribbit.com",
        password="plain_password",
    )

    with pytest.raises(PermissionDeniedError, match="administrators"):
        use_case.execute(command)
