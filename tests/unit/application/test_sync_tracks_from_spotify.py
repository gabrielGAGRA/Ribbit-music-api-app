"""Unit tests for SyncTracksFromSpotifyUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.spotify_dtos import SyncTracksFromSpotifyCommand
from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.application.ports.services.music_service import CatalogTrack, TrackCatalogPort
from app.application.use_cases.spotify.sync_tracks_from_spotify import (
    SyncTracksFromSpotifyUseCase,
)
from app.domain.exceptions import BusinessRuleViolationError, SpotifyAuthError
from app.domain.models.track import Track


def _catalog_track(track_id: str, duration_ms: int | None = 200_400) -> CatalogTrack:
    return CatalogTrack(
        external_id=track_id,
        title=f"T{track_id}",
        artist="Art",
        album="Alb",
        preview_url=None,
        uri=f"spotify:track:{track_id}",
        duration_ms=duration_ms,
        cover_url="http://c",
        release_year=2020,
    )


def _use_case(
    found: list[CatalogTrack], existing: dict[str, Track] | None = None
) -> tuple[SyncTracksFromSpotifyUseCase, MagicMock, MagicMock]:
    catalog = MagicMock(spec=TrackCatalogPort)
    catalog.search_tracks.return_value = found
    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_spotify_id.side_effect = (existing or {}).get
    track_repo.save.side_effect = lambda track: track
    return SyncTracksFromSpotifyUseCase(catalog, track_repo), catalog, track_repo


@pytest.mark.unit
class TestSyncTracks:
    def test_saves_new_tracks_with_command_genre_and_seconds(self) -> None:
        use_case, catalog, track_repo = _use_case(
            [_catalog_track("1", 200_400), _catalog_track("2", 100)]
        )

        saved = use_case.execute(
            SyncTracksFromSpotifyCommand(
                query="daft punk", limit=2, offset=4, genre="Pop"
            )
        )

        catalog.search_tracks.assert_called_once_with("daft punk", limit=2, offset=4)
        assert [t.spotify_id for t in saved] == ["1", "2"]
        first, second = saved
        assert (first.title, first.artist, first.album) == ("T1", "Art", "Alb")
        assert (first.duration_seconds, first.genre) == (200, "Pop")
        assert (first.cover_url, first.release_year) == ("http://c", 2020)
        assert second.duration_seconds == 1
        assert track_repo.save.call_count == 2

    def test_default_genre_is_unknown(self) -> None:
        use_case, _, _ = _use_case([_catalog_track("1")])

        (track,) = use_case.execute(SyncTracksFromSpotifyCommand(query="x"))

        assert track.genre == "Desconhecido"

    def test_existing_track_keeps_curated_fields(self) -> None:
        existing = Track(
            track_id=7,
            spotify_id="1",
            title="Old",
            artist="Old",
            duration_seconds=10,
            genre="Rock",
            explicit=True,
        )
        use_case, _, track_repo = _use_case([_catalog_track("1")], {"1": existing})

        (track,) = use_case.execute(
            SyncTracksFromSpotifyCommand(query="x", genre="Pop")
        )

        assert track is existing
        assert (track.title, track.duration_seconds) == ("T1", 200)
        assert (track.genre, track.explicit, track.track_id) == ("Rock", True, 7)
        track_repo.save.assert_called_once_with(existing)

    def test_skips_tracks_missing_required_data(self) -> None:
        incomplete = CatalogTrack(
            external_id="9", title="T9", artist="Art", album=None, preview_url=None
        )
        use_case, _, track_repo = _use_case([incomplete, _catalog_track("1")])

        saved = use_case.execute(SyncTracksFromSpotifyCommand(query="x"))

        assert [t.spotify_id for t in saved] == ["1"]
        track_repo.save.assert_called_once()

    @pytest.mark.parametrize("invalid_limit", [0, -1, 11, 50])
    def test_rejects_invalid_limit(self, invalid_limit: int) -> None:
        with pytest.raises(BusinessRuleViolationError, match="limit"):
            SyncTracksFromSpotifyCommand(query="x", limit=invalid_limit)

    def test_rejects_negative_offset(self) -> None:
        with pytest.raises(BusinessRuleViolationError, match="offset"):
            SyncTracksFromSpotifyCommand(query="x", offset=-1)

    def test_unconfigured_catalog_raises_spotify_auth_error(self) -> None:
        catalog = MagicMock(spec=TrackCatalogPort)
        catalog.search_tracks.side_effect = SpotifyAuthError("not configured")
        track_repo = MagicMock(spec=TrackRepositoryPort)
        use_case = SyncTracksFromSpotifyUseCase(catalog, track_repo)

        with pytest.raises(SpotifyAuthError, match="not configured"):
            use_case.execute(SyncTracksFromSpotifyCommand(query="x"))
