"""Unit tests for UpdateTrackGenreUseCase."""

import logging
from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.application.ports.services.catalog_source import TrackCatalogFilePort
from app.application.use_cases.admin.update_track_genre import (
    UpdateTrackGenreUseCase,
)
from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    ExternalServiceError,
)
from app.domain.models.track import Track


def test_update_track_genre_saves_repo_and_writes_delta() -> None:
    track = Track(
        track_id=1,
        title="Amphibian Beat",
        artist="Froggy",
        duration_seconds=200,
        genre="Pop",
        itunes_preview_url="https://preview.itunes.apple.com/beat.mp3",
        spotify_id="spot-1",
    )

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track
    track_repo.save.side_effect = lambda t: t

    catalog_port = MagicMock(spec=TrackCatalogFilePort)

    use_case = UpdateTrackGenreUseCase(
        track_repo=track_repo,
        catalog_file_port=catalog_port,
    )

    result = use_case.execute(track_id=1, genre="Synthwave")

    assert result == "Synthwave"
    assert track.genre == "Synthwave"
    track_repo.save.assert_called_once_with(track)
    catalog_port.write_track_delta.assert_called_once_with(
        title="Amphibian Beat",
        artist="Froggy",
        preview_url="https://preview.itunes.apple.com/beat.mp3",
        genre="Synthwave",
        spotify_id="spot-1",
    )


def test_update_track_genre_raises_entity_not_found_when_missing() -> None:
    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = None

    use_case = UpdateTrackGenreUseCase(track_repo=track_repo)

    with pytest.raises(EntityNotFoundError, match="Track 999 not found"):
        use_case.execute(track_id=999, genre="Rock")


@pytest.mark.parametrize("empty_genre", ["", "   ", "\t\n"])
def test_update_track_genre_raises_business_rule_violation_for_empty_genre(
    empty_genre: str,
) -> None:
    track = Track(
        track_id=1,
        title="Amphibian Beat",
        artist="Froggy",
        duration_seconds=200,
        genre="Pop",
    )
    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track

    use_case = UpdateTrackGenreUseCase(track_repo=track_repo)

    with pytest.raises(
        BusinessRuleViolationError, match="Track genre must not be empty"
    ):
        use_case.execute(track_id=1, genre=empty_genre)


def test_update_track_genre_catches_and_logs_external_service_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    track = Track(
        track_id=42,
        title="Amphibian Beat",
        artist="Froggy",
        duration_seconds=200,
        genre="Pop",
        itunes_preview_url="https://preview.itunes.apple.com/beat.mp3",
        spotify_id="spot-42",
    )
    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track
    track_repo.save.side_effect = lambda t: t

    catalog_port = MagicMock(spec=TrackCatalogFilePort)
    catalog_port.write_track_delta.side_effect = ExternalServiceError(
        "GCS storage unreachable"
    )

    use_case = UpdateTrackGenreUseCase(
        track_repo=track_repo,
        catalog_file_port=catalog_port,
    )

    with caplog.at_level(logging.WARNING):
        result = use_case.execute(track_id=42, genre="Electronic")

    assert result == "Electronic"
    assert track.genre == "Electronic"
    track_repo.save.assert_called_once_with(track)
    catalog_port.write_track_delta.assert_called_once_with(
        title="Amphibian Beat",
        artist="Froggy",
        preview_url="https://preview.itunes.apple.com/beat.mp3",
        genre="Electronic",
        spotify_id="spot-42",
    )
    assert (
        "Failed to write track delta for track 42: GCS storage unreachable"
        in caplog.text
    )
