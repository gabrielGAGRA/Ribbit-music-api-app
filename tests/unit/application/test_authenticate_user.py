"""Unit tests for AuthenticateUserUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.auth_dtos import AuthenticateUserCommand
from app.application.ports.repositories.plan_repository import PlanRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.ports.services.password_hasher import PasswordHasherPort
from app.application.ports.services.token_service import TokenServicePort
from app.application.use_cases.auth.authenticate_user import AuthenticateUserUseCase
from app.domain.exceptions import (
    AuthenticationRequiredError,
    PermissionDeniedError,
)
from app.domain.models.plan import Plan
from app.domain.models.user import User


def _token_service() -> MagicMock:
    service = MagicMock(spec=TokenServicePort)
    service.create_access_token.return_value = "test-token"
    return service


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
        token_service=_token_service(),
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
        token_service=_token_service(),
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
        token_service=_token_service(),
    )
    command = AuthenticateUserCommand(
        email="frog@ribbit.com",
        password="bad_password",
    )

    with pytest.raises(AuthenticationRequiredError, match="Invalid credentials"):
        use_case.execute(command)


def test_authenticate_user_rejects_minor_on_free_plan() -> None:
    minor = User(
        user_id=11,
        email="minor@ribbit.com",
        password_hash="hashed_pw",
        display_name="Minor",
        age=15,
        plan_id=1,
    )
    free_plan = Plan(
        plan_id=1, name="Free", initial_monthly_price=0.0, initial_max_profiles=1
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_email.return_value = minor
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = free_plan
    password_hasher = MagicMock(spec=PasswordHasherPort)
    password_hasher.verify_password.return_value = True

    use_case = AuthenticateUserUseCase(
        user_repo=user_repo,
        password_hasher=password_hasher,
        token_service=_token_service(),
        plan_repo=plan_repo,
    )

    with pytest.raises(
        PermissionDeniedError, match="Minor users cannot use the Free plan"
    ):
        use_case.execute(
            AuthenticateUserCommand(email="minor@ribbit.com", password="secret")
        )


def test_authenticate_user_allows_minor_linked_to_family_plan() -> None:
    minor = User(
        user_id=12,
        email="minor-dep@ribbit.com",
        password_hash="hashed_pw",
        display_name="Minor Dep",
        age=15,
        plan_id=3,
        primary_account_id=1,
    )
    family_plan = Plan(
        plan_id=3, name="Família", initial_monthly_price=27.90, initial_max_profiles=4
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_email.return_value = minor
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = family_plan
    password_hasher = MagicMock(spec=PasswordHasherPort)
    password_hasher.verify_password.return_value = True

    use_case = AuthenticateUserUseCase(
        user_repo=user_repo,
        password_hasher=password_hasher,
        token_service=_token_service(),
        plan_repo=plan_repo,
    )

    result = use_case.execute(
        AuthenticateUserCommand(email="minor-dep@ribbit.com", password="secret")
    )
    assert result.user is minor
