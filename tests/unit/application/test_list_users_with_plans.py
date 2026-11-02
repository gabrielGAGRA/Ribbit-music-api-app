"""Unit tests for ListUsersWithPlansUseCase."""

from unittest.mock import MagicMock

from app.application.dtos.admin_dtos import UserPlanSummaryResult
from app.application.ports.repositories.plan_repository import PlanRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.admin.list_users_with_plans import (
    ListUsersWithPlansUseCase,
)
from app.domain.models.plan import Plan
from app.domain.models.user import User


def test_list_users_with_plans_maps_known_and_unknown_plan_names() -> None:
    plans = [
        Plan(plan_id=1, name="Free", initial_monthly_price=0.0),
        Plan(plan_id=2, name="Premium", initial_monthly_price=19.90),
    ]
    users = [
        User(
            user_id=1,
            email="alice@test.com",
            password_hash="h",
            display_name="Alice",
            age=24,
            plan_id=2,
            is_admin=True,
        ),
        User(
            user_id=2,
            email="bob@test.com",
            password_hash="h",
            display_name="Bob",
            age=17,
            plan_id=999,
            is_admin=False,
        ),
    ]
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.list_all.return_value = users
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.list_all.return_value = plans

    use_case = ListUsersWithPlansUseCase(user_repo=user_repo, plan_repo=plan_repo)
    result = use_case.execute()

    assert result == [
        UserPlanSummaryResult(
            user_id=1,
            email="alice@test.com",
            display_name="Alice",
            age=24,
            plan_name="Premium",
            is_admin=True,
        ),
        UserPlanSummaryResult(
            user_id=2,
            email="bob@test.com",
            display_name="Bob",
            age=17,
            plan_name="Unknown",
            is_admin=False,
        ),
    ]
    user_repo.list_all.assert_called_once_with()
    plan_repo.list_all.assert_called_once_with()
