"""Unit tests for BlockTrackUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.application.ports.services.catalog_source import TrackCatalogFilePort
from app.application.use_cases.admin.block_track import BlockTrackUseCase
from app.domain.exceptions import EntityNotFoundError, ExternalServiceError
from app.domain.models.track import Track


def test_block_track_not_found_raises_error() -> None:
    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = None

    use_case = BlockTrackUseCase(track_repo=track_repo)

    with pytest.raises(EntityNotFoundError, match="Track 100 not found"):
        use_case.execute(track_id=100)

    track_repo.save.assert_not_called()


def _identity_track(t: Track) -> Track:
    return t


def test_block_track_marks_as_deleted_and_saves() -> None:
    track = Track(
        track_id=100,
        title="Offensive Song",
        artist="Artist",
        duration_seconds=200,
        genre="Rock",
        is_deleted=False,
    )
    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track
    track_repo.save.side_effect = _identity_track

    use_case = BlockTrackUseCase(track_repo=track_repo)
    result = use_case.execute(track_id=100, blocked=True)

    assert result is True
    assert track.is_deleted is True
    track_repo.find_by_id.assert_called_once_with(100)
    track_repo.save.assert_called_once_with(track)


def test_unblock_track_restores_and_saves() -> None:
    track = Track(
        track_id=100,
        title="Offensive Song",
        artist="Artist",
        duration_seconds=200,
        genre="Rock",
        is_deleted=True,
    )
    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track
    track_repo.save.side_effect = _identity_track

    use_case = BlockTrackUseCase(track_repo=track_repo)
    result = use_case.execute(track_id=100, blocked=False)

    assert result is False
    assert track.is_deleted is False
    track_repo.find_by_id.assert_called_once_with(100)
    track_repo.save.assert_called_once_with(track)


def test_block_and_unblock_track_writes_delta_and_tolerates_gcs_error() -> None:
    track = Track(
        track_id=101,
        title="Offensive Song",
        artist="Artist",
        duration_seconds=200,
        genre="Rock",
        spotify_id="sp-off-1",
        is_deleted=False,
    )
    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track
    track_repo.save.side_effect = _identity_track
    catalog_port = MagicMock(spec=TrackCatalogFilePort)

    use_case = BlockTrackUseCase(track_repo=track_repo, catalog_file_port=catalog_port)
    assert use_case.execute(track_id=101, blocked=True) is True
    catalog_port.write_track_delta.assert_called_once_with(
        title="Offensive Song",
        artist="Artist",
        spotify_id="sp-off-1",
        is_deleted=True,
    )

    catalog_port.write_track_delta.reset_mock()
    catalog_port.write_track_delta.side_effect = ExternalServiceError(
        "GCS unavailable", service_name="GCP_GCS"
    )
    assert use_case.execute(track_id=101, blocked=False) is False
    catalog_port.write_track_delta.assert_called_once_with(
        title="Offensive Song",
        artist="Artist",
        spotify_id="sp-off-1",
        is_deleted=False,
    )
