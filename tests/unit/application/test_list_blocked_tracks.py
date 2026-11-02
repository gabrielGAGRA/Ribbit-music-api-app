"""Unit tests for ListBlockedTracksUseCase."""

from unittest.mock import MagicMock

from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.application.use_cases.admin.list_blocked_tracks import (
    ListBlockedTracksUseCase,
)
from app.domain.models import Track


def test_list_blocked_tracks_returns_repository_blocked_list() -> None:
    blocked_track = Track(
        track_id=1,
        title="Blocked Track",
        artist="Offensive Artist",
        duration_seconds=180,
        genre="Noise",
        is_deleted=True,
    )
    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.list_blocked.return_value = [blocked_track]

    use_case = ListBlockedTracksUseCase(track_repo=track_repo)
    results = use_case.execute()

    assert len(results) == 1
    assert results[0].track_id == 1
    assert results[0].is_deleted is True
    track_repo.list_blocked.assert_called_once()
