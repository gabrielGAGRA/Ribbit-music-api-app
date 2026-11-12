"""Unit tests for RegisterAdministratorUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos import RegisterAdministratorCommand
from app.application.ports.repositories.audit_log_repository import (
    AuditLogRepositoryPort,
)
from app.application.ports.repositories.plan_repository import PlanRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.ports.services.password_hasher import PasswordHasherPort
from app.application.use_cases.admin.register_administrator import (
    RegisterAdministratorUseCase,
)
from app.domain.exceptions import (
    BusinessRuleViolationError,
    DuplicateEntityError,
    EntityNotFoundError,
)
from app.domain.models import Plan, User


def test_register_administrator_succeeds_for_eligible_email() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_email.return_value = None
    user_repo.save.side_effect = lambda u: u

    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_name.return_value = Plan(
        plan_id=1,
        name="Free",
        initial_monthly_price=0.0,
        initial_max_profiles=1,
    )

    password_hasher = MagicMock(spec=PasswordHasherPort)
    password_hasher.hash_password.return_value = "hashed_secret"

    audit_log_repo = MagicMock(spec=AuditLogRepositoryPort)

    use_case = RegisterAdministratorUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        password_hasher=password_hasher,
        audit_log_repo=audit_log_repo,
        eligible_emails=("gabriel.agra@usp.br", "admin@ribbit.example.com"),
    )

    cmd = RegisterAdministratorCommand(
        creator_admin_id=1,
        email="Gabriel.Agra@usp.br",
        password="ValidPassword123",
        display_name="Gabriel Agra",
        age=25,
    )

    result = use_case.execute(cmd)

    assert result.is_admin is True
    assert result.email == "gabriel.agra@usp.br"
    assert result.display_name == "Gabriel Agra"
    assert result.password_hash == "hashed_secret"
    assert result.plan_id == 1
    user_repo.save.assert_called_once()
    audit_log_repo.log_event.assert_called_once_with(
        "ADMIN_REGISTERED:gabriel.agra@usp.br", "OK"
    )


def test_register_administrator_fails_for_ineligible_email() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    password_hasher = MagicMock(spec=PasswordHasherPort)

    use_case = RegisterAdministratorUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        password_hasher=password_hasher,
        eligible_emails=("gabriel.agra@usp.br",),
    )

    cmd = RegisterAdministratorCommand(
        creator_admin_id=1,
        email="unauthorized@example.com",
        password="ValidPassword123",
        display_name="Attacker",
    )

    with pytest.raises(
        BusinessRuleViolationError,
        match="Email unauthorized@example.com is not eligible",
    ):
        use_case.execute(cmd)

    user_repo.save.assert_not_called()


def test_register_administrator_fails_for_duplicate_email() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_email.return_value = User(
        user_id=2,
        email="gabriel.agra@usp.br",
        password_hash="pw",
        display_name="Existing Gabriel",
        age=25,
        plan_id=1,
    )
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    password_hasher = MagicMock(spec=PasswordHasherPort)

    use_case = RegisterAdministratorUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        password_hasher=password_hasher,
        eligible_emails=("gabriel.agra@usp.br",),
    )

    cmd = RegisterAdministratorCommand(
        creator_admin_id=1,
        email="gabriel.agra@usp.br",
        password="ValidPassword123",
        display_name="Gabriel Agra",
    )

    with pytest.raises(DuplicateEntityError, match="already in use"):
        use_case.execute(cmd)

    user_repo.save.assert_not_called()


def test_register_administrator_fails_when_free_plan_missing() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_email.return_value = None
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_name.return_value = None
    password_hasher = MagicMock(spec=PasswordHasherPort)

    use_case = RegisterAdministratorUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        password_hasher=password_hasher,
        eligible_emails=("gabriel.agra@usp.br",),
    )

    cmd = RegisterAdministratorCommand(
        creator_admin_id=1,
        email="gabriel.agra@usp.br",
        password="ValidPassword123",
        display_name="Gabriel Agra",
    )

    with pytest.raises(EntityNotFoundError, match="Default Free plan not found"):
        use_case.execute(cmd)
