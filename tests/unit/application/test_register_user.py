"""Unit tests for RegisterUserUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.auth_dtos import RegisterUserCommand
from app.application.ports.repositories.plan_repository import PlanRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.ports.services.password_hasher import PasswordHasherPort
from app.application.use_cases.auth.register_user import RegisterUserUseCase
from app.domain.exceptions import (
    BusinessRuleViolationError,
    DuplicateEntityError,
    EntityNotFoundError,
)
from app.domain.models.plan import Plan
from app.domain.models.user import User


def test_register_user_with_default_free_plan_succeeds() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_email.return_value = None
    user_repo.save.side_effect = lambda u: u

    free_plan = Plan(
        plan_id=1,
        name=Plan.DEFAULT_FREE_PLAN_NAME,
        initial_monthly_price=0.0,
        initial_max_profiles=1,
    )
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_name.return_value = free_plan

    password_hasher = MagicMock(spec=PasswordHasherPort)
    password_hasher.hash_password.return_value = "hashed_pw_123"

    use_case = RegisterUserUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        password_hasher=password_hasher,
    )
    command = RegisterUserCommand(
        email="  NewUser@Ribbit.com  ",
        password="raw_password",
        display_name="  Lily Pad  ",
        age=22,
        plan_id=None,
    )

    result = use_case.execute(command)

    assert result.email == "newuser@ribbit.com"
    assert result.display_name == "Lily Pad"
    assert result.password_hash == "hashed_pw_123"
    assert result.age == 22
    assert result.plan_id == 1
    assert result.is_admin is False
    plan_repo.find_by_name.assert_called_once_with(Plan.DEFAULT_FREE_PLAN_NAME)
    password_hasher.hash_password.assert_called_once_with("raw_password")
    user_repo.save.assert_called_once()


def test_register_user_with_explicit_plan_id_succeeds() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_email.return_value = None
    user_repo.save.side_effect = lambda u: u

    premium_plan = Plan(
        plan_id=2,
        name="Premium",
        initial_monthly_price=19.90,
        initial_max_profiles=1,
    )
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = premium_plan

    password_hasher = MagicMock(spec=PasswordHasherPort)
    password_hasher.hash_password.return_value = "hashed_pw_456"

    use_case = RegisterUserUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        password_hasher=password_hasher,
    )
    command = RegisterUserCommand(
        email="premium@ribbit.com",
        password="raw_password",
        display_name="Premium Frog",
        age=19,
        plan_id=2,
    )

    result = use_case.execute(command)

    assert result.plan_id == 2
    plan_repo.find_by_id.assert_called_once_with(2)
    plan_repo.find_by_name.assert_not_called()


def test_register_user_duplicate_email_raises_duplicate_entity_error() -> None:
    existing_user = User(
        user_id=5,
        email="taken@ribbit.com",
        password_hash="hash",
        display_name="Existing",
        age=25,
        plan_id=1,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_email.return_value = existing_user

    plan_repo = MagicMock(spec=PlanRepositoryPort)
    password_hasher = MagicMock(spec=PasswordHasherPort)

    use_case = RegisterUserUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        password_hasher=password_hasher,
    )
    command = RegisterUserCommand(
        email="taken@ribbit.com",
        password="pw",
        display_name="New",
        age=20,
    )

    with pytest.raises(DuplicateEntityError, match="already in use"):
        use_case.execute(command)

    user_repo.save.assert_not_called()


def test_register_user_missing_default_free_plan_raises_entity_not_found() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_email.return_value = None

    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_name.return_value = None

    password_hasher = MagicMock(spec=PasswordHasherPort)

    use_case = RegisterUserUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        password_hasher=password_hasher,
    )
    command = RegisterUserCommand(
        email="user@ribbit.com",
        password="pw",
        display_name="User",
        age=20,
        plan_id=None,
    )

    with pytest.raises(EntityNotFoundError, match="Default Free plan not found"):
        use_case.execute(command)

    user_repo.save.assert_not_called()


def test_register_user_explicit_plan_not_found_raises_entity_not_found() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_email.return_value = None

    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = None

    password_hasher = MagicMock(spec=PasswordHasherPort)

    use_case = RegisterUserUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        password_hasher=password_hasher,
    )
    command = RegisterUserCommand(
        email="user@ribbit.com",
        password="pw",
        display_name="User",
        age=20,
        plan_id=999,
    )

    with pytest.raises(EntityNotFoundError, match="Plan with ID 999 not found"):
        use_case.execute(command)

    user_repo.save.assert_not_called()


def test_register_user_with_adult_birth_date_succeeds() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_email.return_value = None
    user_repo.save.side_effect = lambda u: u

    free_plan = Plan(
        plan_id=1,
        name=Plan.DEFAULT_FREE_PLAN_NAME,
        initial_monthly_price=0.0,
        initial_max_profiles=1,
    )
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_name.return_value = free_plan

    password_hasher = MagicMock(spec=PasswordHasherPort)
    password_hasher.hash_password.return_value = "hashed_pw"

    use_case = RegisterUserUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        password_hasher=password_hasher,
    )
    command = RegisterUserCommand(
        email="adult@ribbit.com",
        password="password123",
        display_name="Adult Frog",
        birth_date="1995-05-15",
    )

    result = use_case.execute(command)

    assert result.email == "adult@ribbit.com"
    assert result.birth_date == "1995-05-15"
    assert result.age >= 18


def test_register_user_underage_birth_date_raises_business_rule_violation() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_email.return_value = None
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    password_hasher = MagicMock(spec=PasswordHasherPort)

    use_case = RegisterUserUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        password_hasher=password_hasher,
    )
    command = RegisterUserCommand(
        email="minor@ribbit.com",
        password="password123",
        display_name="Minor Frog",
        birth_date="2015-01-01",
    )

    with pytest.raises(
        BusinessRuleViolationError,
        match="Cadastro direto permitido apenas para maiores de 18 anos",
    ):
        use_case.execute(command)


def test_register_user_future_birth_date_raises_business_rule_violation() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_email.return_value = None
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    password_hasher = MagicMock(spec=PasswordHasherPort)

    use_case = RegisterUserUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        password_hasher=password_hasher,
    )
    command = RegisterUserCommand(
        email="future@ribbit.com",
        password="password123",
        display_name="Future Frog",
        birth_date="2099-01-01",
    )

    with pytest.raises(BusinessRuleViolationError, match="não pode estar no futuro"):
        use_case.execute(command)


def test_register_user_underage_age_without_birth_date_raises_violation() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_email.return_value = None
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    password_hasher = MagicMock(spec=PasswordHasherPort)

    use_case = RegisterUserUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        password_hasher=password_hasher,
    )
    command = RegisterUserCommand(
        email="minor@ribbit.com",
        password="password123",
        display_name="Minor Frog",
        age=16,
    )

    with pytest.raises(
        BusinessRuleViolationError,
        match="Cadastro direto permitido apenas para maiores de 18 anos",
    ):
        use_case.execute(command)
