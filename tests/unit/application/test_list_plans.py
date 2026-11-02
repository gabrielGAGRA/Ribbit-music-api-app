"""Unit tests for ListPlansUseCase."""

from unittest.mock import MagicMock

from app.application.ports.repositories.plan_repository import PlanRepositoryPort
from app.application.use_cases.user.list_plans import ListPlansUseCase
from app.domain.models.plan import Plan


def test_list_plans_returns_all_plans_from_repository() -> None:
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
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.list_all.return_value = plans

    use_case = ListPlansUseCase(plan_repo=plan_repo)
    result = use_case.execute()

    assert result == plans
    plan_repo.list_all.assert_called_once_with()
