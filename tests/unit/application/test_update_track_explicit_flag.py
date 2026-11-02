"""Unit tests for UpdateTrackExplicitFlagUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.application.use_cases.admin.update_track_explicit_flag import (
    UpdateTrackExplicitFlagUseCase,
)
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.track import Track


def test_update_track_explicit_flag_track_not_found_raises_error() -> None:
    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = None

    use_case = UpdateTrackExplicitFlagUseCase(track_repo=track_repo)

    with pytest.raises(EntityNotFoundError, match="Track 77 not found"):
        use_case.execute(track_id=77, explicit=True)

    track_repo.save.assert_not_called()


def test_update_track_explicit_flag_toggles_true_and_false() -> None:
    track = Track(
        track_id=77,
        title="Track",
        artist="Artist",
        duration_seconds=180,
        genre="Hip-Hop",
        explicit=False,
    )
    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track
    track_repo.save.side_effect = lambda t: t

    use_case = UpdateTrackExplicitFlagUseCase(track_repo=track_repo)

    result_true = use_case.execute(track_id=77, explicit=True)
    assert result_true is True
    assert track.explicit is True

    result_false = use_case.execute(track_id=77, explicit=False)
    assert result_false is False
    assert track.explicit is False
    assert track_repo.save.call_count == 2
