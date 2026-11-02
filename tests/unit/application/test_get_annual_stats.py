"""Unit tests for GetAnnualListeningStatsUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.use_cases.user.get_annual_stats import (
    GetAnnualListeningStatsUseCase,
)
from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError
from app.domain.models import Interaction, InteractionAction, Plan, Track, User


def test_get_annual_stats_user_not_found() -> None:
    user_repo = MagicMock()
    user_repo.find_by_id.return_value = None
    plan_repo = MagicMock()
    interaction_repo = MagicMock()
    track_repo = MagicMock()

    use_case = GetAnnualListeningStatsUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        interaction_repo=interaction_repo,
        track_repo=track_repo,
    )

    with pytest.raises(EntityNotFoundError):
        use_case.execute(user_id=1)


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
    interaction_repo = MagicMock()
    track_repo = MagicMock()

    use_case = GetAnnualListeningStatsUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        interaction_repo=interaction_repo,
        track_repo=track_repo,
    )

    with pytest.raises(PermissionDeniedError, match="exclusive to Premium"):
        use_case.execute(user_id=1)


def test_get_annual_stats_empty_interactions() -> None:
    user = User(
        user_id=1,
        email="prem@test.com",
        password_hash="pw",
        display_name="Prem",
        age=20,
        plan_id=2,
    )
    paid_plan = Plan(plan_id=2, name="Premium", initial_monthly_price=10.0)

    user_repo = MagicMock()
    user_repo.find_by_id.return_value = user
    plan_repo = MagicMock()
    plan_repo.find_by_id.return_value = paid_plan
    interaction_repo = MagicMock()
    interaction_repo.list_by_user.return_value = []
    track_repo = MagicMock()

    use_case = GetAnnualListeningStatsUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        interaction_repo=interaction_repo,
        track_repo=track_repo,
    )

    stats = use_case.execute(user_id=1)
    assert stats.user_id == 1
    assert stats.total_likes == 0
    assert stats.estimated_listening_hours == 0.0
    assert stats.top_genres == []
    assert stats.top_artists == []
    track_repo.find_by_ids.assert_not_called()


def test_get_annual_stats_calculates_top_genres_and_artists() -> None:
    user = User(
        user_id=1,
        email="prem@test.com",
        password_hash="pw",
        display_name="Prem",
        age=20,
        plan_id=2,
    )
    paid_plan = Plan(plan_id=2, name="Premium", initial_monthly_price=10.0)

    interactions = [
        Interaction(user_id=1, track_id=101, action=InteractionAction.LIKE),
        Interaction(user_id=1, track_id=102, action=InteractionAction.LIKE),
        Interaction(user_id=1, track_id=103, action=InteractionAction.LIKE),
        Interaction(user_id=1, track_id=104, action=InteractionAction.LIKE),
        Interaction(
            user_id=1, track_id=105, action=InteractionAction.DISLIKE
        ),  # not positive
    ]

    tracks = {
        101: Track(
            track_id=101,
            title="T1",
            artist="Artist A",
            genre="Rock",
            duration_seconds=180,
        ),
        102: Track(
            track_id=102,
            title="T2",
            artist="Artist A",
            genre="Rock",
            duration_seconds=180,
        ),
        103: Track(
            track_id=103,
            title="T3",
            artist="Artist B",
            genre="Pop",
            duration_seconds=180,
        ),
        104: Track(
            track_id=104,
            title="T4",
            artist="Artist C",
            genre="Jazz",
            duration_seconds=180,
        ),
    }

    user_repo = MagicMock()
    user_repo.find_by_id.return_value = user
    plan_repo = MagicMock()
    plan_repo.find_by_id.return_value = paid_plan
    interaction_repo = MagicMock()
    interaction_repo.list_by_user.return_value = interactions
    track_repo = MagicMock()
    track_repo.find_by_ids.return_value = tracks

    use_case = GetAnnualListeningStatsUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        interaction_repo=interaction_repo,
        track_repo=track_repo,
    )

    stats = use_case.execute(user_id=1)
    assert stats.user_id == 1
    assert stats.total_likes == 4
    assert stats.estimated_listening_hours == round(4 * 3.5 / 60, 1)
    assert stats.top_genres[0] == "Rock"
    assert len(stats.top_genres) == 3
    assert stats.top_artists[0] == "Artist A"
    assert len(stats.top_artists) == 3
    track_repo.find_by_ids.assert_called_once_with([101, 102, 103, 104])
