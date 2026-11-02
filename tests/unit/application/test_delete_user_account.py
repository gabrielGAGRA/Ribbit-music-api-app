"""Unit tests for DeleteUserAccountUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.user.delete_user_account import DeleteUserAccountUseCase
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.user import User


def test_delete_user_account_not_found_raises_error() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None

    use_case = DeleteUserAccountUseCase(user_repo=user_repo)

    with pytest.raises(EntityNotFoundError, match="User with ID 42 not found"):
        use_case.execute(user_id=42)

    user_repo.delete.assert_not_called()


def test_delete_user_account_deletes_and_returns_true() -> None:
    user = User(
        user_id=42,
        email="bye@test.com",
        password_hash="hash",
        display_name="Bye",
        age=25,
        plan_id=1,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user
    user_repo.delete.return_value = True

    use_case = DeleteUserAccountUseCase(user_repo=user_repo)
    result = use_case.execute(user_id=42)

    assert result is True
    user_repo.find_by_id.assert_called_once_with(42)
    user_repo.delete.assert_called_once_with(42)


def test_delete_user_account_unlinks_dependents_to_free_plan() -> None:
    from app.application.ports.repositories.plan_repository import PlanRepositoryPort
    from app.domain.models.plan import Plan

    user = User(
        user_id=1,
        email="parent@test.com",
        password_hash="hash",
        display_name="Parent",
        age=40,
        plan_id=3,
    )
    dep = User(
        user_id=2,
        email="child@test.com",
        password_hash="hash",
        display_name="Child",
        age=12,
        plan_id=3,
        primary_account_id=1,
    )
    free_plan = Plan(
        plan_id=1,
        name="Free",
        initial_monthly_price=0.0,
        initial_max_profiles=1,
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user
    user_repo.list_dependents.return_value = [dep]
    user_repo.delete.return_value = True

    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_name.return_value = free_plan

    use_case = DeleteUserAccountUseCase(user_repo=user_repo, plan_repo=plan_repo)
    result = use_case.execute(user_id=1)

    assert result is True
    assert dep.primary_account_id is None
    assert dep.plan_id == 1
    user_repo.save.assert_called_once_with(dep)
    user_repo.delete.assert_called_once_with(1)


def test_delete_user_account_missing_free_plan_raises_entity_not_found() -> None:
    from app.application.ports.repositories.plan_repository import PlanRepositoryPort

    user = User(
        user_id=1,
        email="parent@test.com",
        password_hash="hash",
        display_name="Parent",
        age=40,
        plan_id=3,
    )
    dep = User(
        user_id=2,
        email="child@test.com",
        password_hash="hash",
        display_name="Child",
        age=12,
        plan_id=3,
        primary_account_id=1,
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user
    user_repo.list_dependents.return_value = [dep]

    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_name.return_value = None

    use_case = DeleteUserAccountUseCase(user_repo=user_repo, plan_repo=plan_repo)
    with pytest.raises(EntityNotFoundError, match="Default Free plan not found"):
        use_case.execute(user_id=1)
