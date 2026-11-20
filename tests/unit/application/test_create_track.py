"""Unit tests for CreateTrackUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.admin_dtos import CreateTrackCommand
from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.application.ports.services.catalog_source import TrackCatalogFilePort
from app.application.use_cases.admin.create_track import CreateTrackUseCase
from app.domain.exceptions import (
    BusinessRuleViolationError,
    DuplicateEntityError,
    ExternalServiceError,
)
from app.domain.models.track import Track


def test_create_track_persists_and_writes_delta() -> None:
    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_spotify_id.return_value = None
    track_repo.find_by_title_and_artist.return_value = None
    track_repo.save.side_effect = lambda t: Track(
        track_id=101,
        title=t.title,
        artist=t.artist,
        duration_seconds=t.duration_seconds,
        genre=t.genre,
        album=t.album,
        country=t.country,
        release_year=t.release_year,
        spotify_id=t.spotify_id,
        explicit=t.explicit,
    )
    catalog_port = MagicMock(spec=TrackCatalogFilePort)

    use_case = CreateTrackUseCase(
        track_repo=track_repo,
        catalog_file_port=catalog_port,
    )
    result = use_case.execute(
        CreateTrackCommand(
            title="  New Wave  ",
            artist="  Synth Band  ",
            genre="  Synthpop  ",
            duration_seconds=215,
            album="  Neon  ",
            spotify_id="  sp-101  ",
            explicit=True,
        )
    )

    assert result.track_id == 101
    assert result.title == "New Wave"
    assert result.artist == "Synth Band"
    assert result.genre == "Synthpop"
    assert result.album == "Neon"
    assert result.spotify_id == "sp-101"
    assert result.explicit is True
    assert result.likes_count == 0
    assert result.dislikes_count == 0
    catalog_port.write_track_delta.assert_called_once()


@pytest.mark.parametrize(
    ("title", "artist", "genre", "duration"),
    [
        ("   ", "Artist", "Rock", 180),
        ("Title", "   ", "Rock", 180),
        ("Title", "Artist", "   ", 180),
        ("Title", "Artist", "Rock", 0),
    ],
)
def test_create_track_rejects_invalid_fields(
    title: str, artist: str, genre: str, duration: int
) -> None:
    track_repo = MagicMock(spec=TrackRepositoryPort)
    use_case = CreateTrackUseCase(track_repo=track_repo)

    with pytest.raises(BusinessRuleViolationError):
        use_case.execute(
            CreateTrackCommand(
                title=title,
                artist=artist,
                genre=genre,
                duration_seconds=duration,
            )
        )
    track_repo.save.assert_not_called()


def test_create_track_rejects_duplicate_spotify_id() -> None:
    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_spotify_id.return_value = Track(
        track_id=5, title="Existing", artist="A", duration_seconds=180, genre="Pop"
    )
    use_case = CreateTrackUseCase(track_repo=track_repo)

    with pytest.raises(DuplicateEntityError, match="spotify_id"):
        use_case.execute(
            CreateTrackCommand(
                title="Other",
                artist="B",
                genre="Pop",
                duration_seconds=180,
                spotify_id="sp-5",
            )
        )
    track_repo.save.assert_not_called()


def test_create_track_rejects_duplicate_title_and_artist() -> None:
    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_spotify_id.return_value = None
    track_repo.find_by_title_and_artist.return_value = Track(
        track_id=5, title="Song", artist="Artist", duration_seconds=180, genre="Pop"
    )
    use_case = CreateTrackUseCase(track_repo=track_repo)

    with pytest.raises(DuplicateEntityError, match="already exists"):
        use_case.execute(
            CreateTrackCommand(
                title="Song",
                artist="Artist",
                genre="Pop",
                duration_seconds=180,
            )
        )
    track_repo.save.assert_not_called()


def test_create_track_swallows_catalog_delta_external_error() -> None:
    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_spotify_id.return_value = None
    track_repo.find_by_title_and_artist.return_value = None
    track_repo.save.side_effect = lambda t: Track(
        track_id=77,
        title=t.title,
        artist=t.artist,
        duration_seconds=t.duration_seconds,
        genre=t.genre,
    )
    catalog_port = MagicMock(spec=TrackCatalogFilePort)
    catalog_port.write_track_delta.side_effect = ExternalServiceError("GCS down")

    use_case = CreateTrackUseCase(
        track_repo=track_repo,
        catalog_file_port=catalog_port,
    )
    result = use_case.execute(
        CreateTrackCommand(
            title="Track",
            artist="Artist",
            genre="Indie",
            duration_seconds=200,
        )
    )

    assert result.track_id == 77
