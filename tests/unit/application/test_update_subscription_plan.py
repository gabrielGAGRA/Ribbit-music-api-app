"""Unit tests for UpdateSubscriptionPlanUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.admin_dtos import UpdateSubscriptionPlanCommand
from app.application.ports.repositories.plan_repository import PlanRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.admin.update_subscription_plan import (
    UpdateSubscriptionPlanUseCase,
)
from app.domain.exceptions import (
    BusinessRuleViolationError,
    DuplicateEntityError,
    EntityNotFoundError,
)
from app.domain.models import User
from app.domain.models.plan import Plan


def test_update_subscription_plan_not_found_raises_error() -> None:
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = None

    use_case = UpdateSubscriptionPlanUseCase(plan_repo=plan_repo)
    command = UpdateSubscriptionPlanCommand(plan_id=99, new_price=29.90)

    with pytest.raises(EntityNotFoundError, match="Plan 99 not found"):
        use_case.execute(command)

    plan_repo.save.assert_not_called()


def _identity_plan(p: Plan) -> Plan:
    return p


def test_update_subscription_plan_updates_all_provided_fields() -> None:
    plan = Plan(
        plan_id=3,
        name="Family",
        initial_monthly_price=34.90,
        initial_max_profiles=4,
    )
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = plan
    plan_repo.find_by_name.return_value = None
    plan_repo.save.side_effect = _identity_plan

    use_case = UpdateSubscriptionPlanUseCase(plan_repo=plan_repo)
    command = UpdateSubscriptionPlanCommand(
        plan_id=3,
        new_price=39.90,
        new_name="Family Plus",
        max_profiles=6,
    )
    updated_plan = use_case.execute(command)

    assert updated_plan.monthly_price == 39.90
    assert updated_plan.name == "Family Plus"
    assert updated_plan.max_profiles == 6
    plan_repo.save.assert_called_once_with(plan)


def test_update_subscription_plan_partial_update_keeps_unmodified_fields() -> None:
    plan = Plan(
        plan_id=2,
        name="Premium",
        initial_monthly_price=19.90,
        initial_max_profiles=1,
    )
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = plan
    plan_repo.save.side_effect = _identity_plan

    use_case = UpdateSubscriptionPlanUseCase(plan_repo=plan_repo)
    command = UpdateSubscriptionPlanCommand(plan_id=2, new_price=24.90)
    updated_plan = use_case.execute(command)

    assert updated_plan.monthly_price == 24.90
    assert updated_plan.name == "Premium"
    assert updated_plan.max_profiles == 1
    plan_repo.save.assert_called_once_with(plan)


def test_update_subscription_plan_invalid_price_raises_value_error() -> None:
    plan = Plan(
        plan_id=2,
        name="Premium",
        initial_monthly_price=19.90,
        initial_max_profiles=1,
    )
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = plan

    use_case = UpdateSubscriptionPlanUseCase(plan_repo=plan_repo)
    command = UpdateSubscriptionPlanCommand(plan_id=2, new_price=-5.0)

    with pytest.raises(ValueError, match="Monthly price cannot be negative"):
        use_case.execute(command)

    plan_repo.save.assert_not_called()


def test_update_subscription_plan_duplicate_name_raises_duplicate_entity_error() -> (
    None
):
    plan = Plan(
        plan_id=2,
        name="Premium",
        initial_monthly_price=19.90,
        initial_max_profiles=1,
    )
    existing_other_plan = Plan(
        plan_id=5,
        name="Family",
        initial_monthly_price=39.90,
        initial_max_profiles=6,
    )
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = plan
    plan_repo.find_by_name.return_value = existing_other_plan

    use_case = UpdateSubscriptionPlanUseCase(plan_repo=plan_repo)
    command = UpdateSubscriptionPlanCommand(plan_id=2, new_name="Family")

    with pytest.raises(DuplicateEntityError, match="Já existe um plano com esse nome"):
        use_case.execute(command)


def test_update_subscription_plan_capacity_below_active_dependents_raises_error() -> (
    None
):
    plan = Plan(
        plan_id=3,
        name="Family",
        initial_monthly_price=39.90,
        initial_max_profiles=5,
    )
    holder = User(
        user_id=10,
        email="holder@ribbit.com",
        password_hash="pw",
        display_name="Holder",
        age=40,
        plan_id=3,
        primary_account_id=None,
    )
    dep1 = User(
        user_id=11,
        email="dep1@ribbit.com",
        password_hash="pw",
        display_name="Dep 1",
        age=12,
        plan_id=3,
        primary_account_id=10,
    )
    dep2 = User(
        user_id=12,
        email="dep2@ribbit.com",
        password_hash="pw",
        display_name="Dep 2",
        age=14,
        plan_id=3,
        primary_account_id=10,
    )

    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = plan

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.list_all.return_value = [holder, dep1, dep2]
    user_repo.list_dependents.return_value = [
        dep1,
        dep2,
    ]  # 2 dependents -> holder + 2 = 3

    use_case = UpdateSubscriptionPlanUseCase(plan_repo=plan_repo, user_repo=user_repo)
    # Trying to reduce max_profiles to 2 when 3 profiles are linked
    command = UpdateSubscriptionPlanCommand(plan_id=3, max_profiles=2)

    with pytest.raises(
        BusinessRuleViolationError,
        match="O limite não pode ser menor que os perfis já vinculados",
    ):
        use_case.execute(command)
