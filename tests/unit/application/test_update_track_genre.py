"""Unit tests for UpdateTrackGenreUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.application.ports.services.catalog_source import TrackCatalogFilePort
from app.application.use_cases.admin.update_track_genre import (
    UpdateTrackGenreUseCase,
)
from app.domain.exceptions import EntityNotFoundError
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
