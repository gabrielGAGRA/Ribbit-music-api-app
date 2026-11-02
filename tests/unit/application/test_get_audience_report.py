"""Unit tests for GetAudienceReportUseCase."""

from unittest.mock import MagicMock

from app.application.dtos.admin_dtos import AudienceReportResult
from app.application.use_cases.admin.get_audience_report import (
    GetAudienceReportUseCase,
)
from app.domain.models import User


def test_get_audience_report_calls_repository_counts() -> None:
    user = User(
        user_id=1,
        email="listener@ribbit.com",
        password_hash="pw",
        display_name="Listener",
        age=25,
        plan_id=1,
        blocked_genres=frozenset({"rock", "pop"}),
    )
    user_repo = MagicMock()
    user_repo.count_all.return_value = 42
    user_repo.list_all.return_value = [user]

    track_repo = MagicMock()
    track_repo.count_all.return_value = 150
    track_repo.count_active.return_value = 120

    use_case = GetAudienceReportUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
    )
    result = use_case.execute()

    assert result == AudienceReportResult(
        total_users=42,
        total_tracks=150,
        active_tracks=120,
        blocked_genres={"rock": 1, "pop": 1},
    )
    user_repo.count_all.assert_called_once()
    track_repo.count_all.assert_called_once()
    track_repo.count_active.assert_called_once()
    user_repo.list_all.assert_called_once()
