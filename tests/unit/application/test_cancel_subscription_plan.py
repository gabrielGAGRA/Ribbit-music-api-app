"""Unit tests for CancelSubscriptionPlanUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.plan_repository import PlanRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.user.cancel_subscription_plan import (
    CancelSubscriptionPlanUseCase,
)
from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError
from app.domain.models.plan import Plan
from app.domain.models.user import User


def test_cancel_subscription_plan_user_not_found_raises_error() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None
    plan_repo = MagicMock(spec=PlanRepositoryPort)

    use_case = CancelSubscriptionPlanUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(EntityNotFoundError, match="User with ID 1 not found"):
        use_case.execute(user_id=1)

    user_repo.save.assert_not_called()


def test_cancel_subscription_plan_free_plan_missing_raises_error() -> None:
    user = User(
        user_id=1,
        email="prem@test.com",
        password_hash="hash",
        display_name="Prem",
        age=25,
        plan_id=2,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_name.return_value = None

    use_case = CancelSubscriptionPlanUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(EntityNotFoundError, match="Default Free plan not found"):
        use_case.execute(user_id=1)

    user_repo.save.assert_not_called()


def test_cancel_subscription_plan_free_plan_without_id_raises_error() -> None:
    user = User(
        user_id=1,
        email="prem@test.com",
        password_hash="hash",
        display_name="Prem",
        age=25,
        plan_id=2,
    )
    unpersisted_free_plan = Plan(
        plan_id=None,
        name=Plan.DEFAULT_FREE_PLAN_NAME,
        initial_monthly_price=0.0,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_name.return_value = unpersisted_free_plan

    use_case = CancelSubscriptionPlanUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(EntityNotFoundError, match="Default Free plan not found"):
        use_case.execute(user_id=1)

    user_repo.save.assert_not_called()


def test_cancel_subscription_plan_reverts_user_to_free_plan() -> None:
    user = User(
        user_id=1,
        email="prem@test.com",
        password_hash="hash",
        display_name="Prem",
        age=25,
        plan_id=2,
    )
    free_plan = Plan(
        plan_id=1,
        name=Plan.DEFAULT_FREE_PLAN_NAME,
        initial_monthly_price=0.0,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user
    user_repo.save.side_effect = lambda u: u
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_name.return_value = free_plan

    use_case = CancelSubscriptionPlanUseCase(user_repo=user_repo, plan_repo=plan_repo)
    updated_user = use_case.execute(user_id=1)

    assert updated_user.plan_id == 1
    plan_repo.find_by_name.assert_called_once_with(Plan.DEFAULT_FREE_PLAN_NAME)
    user_repo.save.assert_called_once_with(user)


def test_cancel_subscription_plan_by_dependent_raises_permission_denied() -> None:
    dependent = User(
        user_id=2,
        email="dep@test.com",
        password_hash="hash",
        display_name="Dep",
        age=20,
        plan_id=3,
        primary_account_id=1,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = dependent
    plan_repo = MagicMock(spec=PlanRepositoryPort)

    use_case = CancelSubscriptionPlanUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(
        PermissionDeniedError, match="Dependentes não podem cancelar o plano"
    ):
        use_case.execute(user_id=2)


def test_cancel_subscription_plan_unlinks_all_dependents_to_free_plan() -> None:
    titular = User(
        user_id=1,
        email="titular@test.com",
        password_hash="hash",
        display_name="Titular",
        age=35,
        plan_id=3,
    )
    dep1 = User(
        user_id=2,
        email="dep1@test.com",
        password_hash="hash",
        display_name="Dep1",
        age=12,
        plan_id=3,
        primary_account_id=1,
    )
    free_plan = Plan(
        plan_id=1,
        name=Plan.DEFAULT_FREE_PLAN_NAME,
        initial_monthly_price=0.0,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = titular
    user_repo.list_dependents.return_value = [dep1]
    user_repo.save.side_effect = lambda u: u

    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_name.return_value = free_plan

    use_case = CancelSubscriptionPlanUseCase(user_repo=user_repo, plan_repo=plan_repo)
    res = use_case.execute(user_id=1)

    assert res.plan_id == 1
    assert dep1.plan_id == 1
    assert dep1.primary_account_id is None
    assert user_repo.save.call_count == 2
