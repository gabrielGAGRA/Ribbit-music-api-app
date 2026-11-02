"""Unit tests for ChangeSubscriptionPlanUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.plan_repository import PlanRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.user.change_subscription_plan import (
    ChangeSubscriptionPlanUseCase,
)
from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    PermissionDeniedError,
)
from app.domain.models.plan import Plan
from app.domain.models.user import User


def test_change_subscription_plan_user_not_found_raises_error() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None
    plan_repo = MagicMock(spec=PlanRepositoryPort)

    use_case = ChangeSubscriptionPlanUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(EntityNotFoundError, match="User with ID 1 not found"):
        use_case.execute(user_id=1, new_plan_id=2)

    user_repo.save.assert_not_called()


def test_change_subscription_plan_target_plan_not_found_raises_error() -> None:
    user = User(
        user_id=1,
        email="user@test.com",
        password_hash="hash",
        display_name="User",
        age=22,
        plan_id=1,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = None

    use_case = ChangeSubscriptionPlanUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(EntityNotFoundError, match="Plan with ID 99 not found"):
        use_case.execute(user_id=1, new_plan_id=99)

    user_repo.save.assert_not_called()


def test_change_subscription_plan_updates_and_saves_user() -> None:
    user = User(
        user_id=1,
        email="user@test.com",
        password_hash="hash",
        display_name="User",
        age=22,
        plan_id=1,
    )
    premium_plan = Plan(
        plan_id=2,
        name="Premium",
        initial_monthly_price=19.90,
        initial_max_profiles=1,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user
    user_repo.save.side_effect = lambda u: u
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = premium_plan

    use_case = ChangeSubscriptionPlanUseCase(user_repo=user_repo, plan_repo=plan_repo)
    updated_user = use_case.execute(user_id=1, new_plan_id=2)

    assert updated_user.plan_id == 2
    plan_repo.find_by_id.assert_called_once_with(2)
    user_repo.save.assert_called_once_with(user)


def test_change_subscription_plan_by_dependent_raises_permission_denied() -> None:
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

    use_case = ChangeSubscriptionPlanUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(
        PermissionDeniedError, match="Dependentes não podem alterar o plano"
    ):
        use_case.execute(user_id=2, new_plan_id=1)


def test_change_subscription_plan_capacity_exceeded_raises_violation() -> None:
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
    dep2 = User(
        user_id=3,
        email="dep2@test.com",
        password_hash="hash",
        display_name="Dep2",
        age=14,
        plan_id=3,
        primary_account_id=1,
    )
    # Individual plan accommodates only 1 profile (titular only, cannot fit 2 dependents)
    individual_plan = Plan(
        plan_id=1,
        name="Individual",
        initial_monthly_price=19.90,
        initial_max_profiles=1,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = titular
    user_repo.list_dependents.return_value = [dep1, dep2]

    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = individual_plan

    use_case = ChangeSubscriptionPlanUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(
        BusinessRuleViolationError, match="não comporta os membros vinculados"
    ):
        use_case.execute(user_id=1, new_plan_id=1)


def test_change_subscription_plan_updates_titular_and_all_dependents() -> None:
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
    # Mega Family plan accommodates up to 10 profiles
    mega_family_plan = Plan(
        plan_id=4,
        name="Mega Family",
        initial_monthly_price=49.90,
        initial_max_profiles=10,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = titular
    user_repo.list_dependents.return_value = [dep1]
    user_repo.save.side_effect = lambda u: u

    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = mega_family_plan

    use_case = ChangeSubscriptionPlanUseCase(user_repo=user_repo, plan_repo=plan_repo)
    res = use_case.execute(user_id=1, new_plan_id=4)

    assert res.plan_id == 4
    assert dep1.plan_id == 4
    assert user_repo.save.call_count == 2
