"""Unit tests for GetAnnualListeningStatsUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.user_dtos import AnnualStatsResult, GenreStat
from app.application.use_cases.user.get_annual_stats import (
    GetAnnualListeningStatsUseCase,
)
from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError
from app.domain.models import Plan, User


def test_get_annual_stats_user_not_found() -> None:
    user_repo = MagicMock()
    user_repo.find_by_id.return_value = None
    plan_repo = MagicMock()
    user_stats_repo = MagicMock()

    use_case = GetAnnualListeningStatsUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        user_stats_repo=user_stats_repo,
    )

    with pytest.raises(EntityNotFoundError):
        use_case.execute(user_id=1)

    user_stats_repo.get_user_stats.assert_not_called()


def test_get_annual_stats_non_premium_raises_permission_denied() -> None:
    user = User(
        user_id=1,
        email="free@test.com",
        password_hash="pw",
        display_name="Free",
        age=20,
        plan_id=1,
    )
    free_plan = Plan(plan_id=1, name="Free", initial_monthly_price=0.0)

    user_repo = MagicMock()
    user_repo.find_by_id.return_value = user
    plan_repo = MagicMock()
    plan_repo.find_by_id.return_value = free_plan
    user_stats_repo = MagicMock()

    use_case = GetAnnualListeningStatsUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        user_stats_repo=user_stats_repo,
    )

    with pytest.raises(PermissionDeniedError, match="exclusive to Premium"):
        use_case.execute(user_id=1)

    user_stats_repo.get_user_stats.assert_not_called()


def test_get_annual_stats_delegates_to_user_stats_repo_with_year() -> None:
    user = User(
        user_id=1,
        email="prem@test.com",
        password_hash="pw",
        display_name="Prem",
        age=20,
        plan_id=2,
    )
    paid_plan = Plan(plan_id=2, name="Premium", initial_monthly_price=10.0)
    expected = AnnualStatsResult(
        user_id=1,
        year=2026,
        available_years=[2026],
        total_interactions=5,
        total_likes=3,
        total_superlikes=1,
        total_dislikes=1,
        positive_rate=0.8,
        top_genres=[
            GenreStat(
                genre="rock",
                likes=2,
                superlikes=1,
                dislikes=0,
                total_positive=3,
            )
        ],
    )

    user_repo = MagicMock()
    user_repo.find_by_id.return_value = user
    plan_repo = MagicMock()
    plan_repo.find_by_id.return_value = paid_plan
    user_stats_repo = MagicMock()
    user_stats_repo.get_user_stats.return_value = expected

    use_case = GetAnnualListeningStatsUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        user_stats_repo=user_stats_repo,
    )

    stats = use_case.execute(user_id=1, year=2026)

    assert stats is expected
    user_stats_repo.get_user_stats.assert_called_once_with(user_id=1, year=2026)
