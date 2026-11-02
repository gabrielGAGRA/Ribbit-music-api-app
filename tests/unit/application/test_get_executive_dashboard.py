"""Unit tests for GetExecutiveDashboardUseCase."""

from unittest.mock import MagicMock

from app.application.dtos.admin_dtos import ExecutiveDashboardResult
from app.application.ports.repositories.plan_repository import PlanRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.admin.get_executive_dashboard import (
    GetExecutiveDashboardUseCase,
)
from app.domain.models.plan import Plan
from app.domain.models.user import User


def test_get_executive_dashboard_empty_users_returns_zero_revenue() -> None:
    plans = [
        Plan(plan_id=1, name="Free", initial_monthly_price=0.0),
        Plan(plan_id=2, name="Premium", initial_monthly_price=19.90),
    ]
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.list_all.return_value = []
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.list_all.return_value = plans

    use_case = GetExecutiveDashboardUseCase(user_repo=user_repo, plan_repo=plan_repo)
    result = use_case.execute()

    assert result == ExecutiveDashboardResult(
        total_users=0,
        estimated_net_revenue=0.0,
        users_by_plan={"Free": 0, "Premium": 0},
        revenue_by_plan={"Free": 0.0, "Premium": 0.0},
    )


def test_get_executive_dashboard_excludes_family_dependents_from_revenue() -> None:
    plans = [
        Plan(plan_id=1, name="Free", initial_monthly_price=0.0, initial_max_profiles=1),
        Plan(
            plan_id=2,
            name="Premium",
            initial_monthly_price=19.90,
            initial_max_profiles=1,
        ),
        Plan(
            plan_id=3,
            name="Family",
            initial_monthly_price=34.90,
            initial_max_profiles=6,
        ),
    ]
    users = [
        User(
            user_id=1,
            email="free@test.com",
            password_hash="h",
            display_name="FreeUser",
            age=20,
            plan_id=1,
        ),
        User(
            user_id=2,
            email="prem@test.com",
            password_hash="h",
            display_name="PremUser",
            age=25,
            plan_id=2,
        ),
        User(
            user_id=3,
            email="fam_primary@test.com",
            password_hash="h",
            display_name="FamPrimary",
            age=40,
            plan_id=3,
            primary_account_id=None,
        ),
        User(
            user_id=4,
            email="fam_dep1@test.com",
            password_hash="h",
            display_name="FamDep1",
            age=16,
            plan_id=3,
            primary_account_id=3,
        ),
        User(
            user_id=5,
            email="fam_dep2@test.com",
            password_hash="h",
            display_name="FamDep2",
            age=14,
            plan_id=3,
            primary_account_id=3,
        ),
        User(
            user_id=6,
            email="orphan_plan@test.com",
            password_hash="h",
            display_name="Orphan",
            age=30,
            plan_id=999,
        ),
    ]
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.list_all.return_value = users
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.list_all.return_value = plans

    use_case = GetExecutiveDashboardUseCase(user_repo=user_repo, plan_repo=plan_repo)
    result = use_case.execute()

    assert result.total_users == 6
    assert result.estimated_net_revenue == 54.80
    assert result.users_by_plan == {"Free": 1, "Premium": 1, "Family": 3}
    assert result.revenue_by_plan == {"Free": 0.0, "Premium": 19.90, "Family": 34.90}
