"""Unit tests for SyncPlaylistFromSpotifyUseCase."""

from itertools import count
from unittest.mock import MagicMock

import pytest

from app.application.dtos.spotify_dtos import SyncPlaylistFromSpotifyCommand
from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.ports.services.music_service import (
    CatalogTrack,
    PlaylistItemsPage,
    PlaylistSourcePort,
    ProviderPlaylist,
)
from app.application.use_cases.spotify.sync_playlist_from_spotify import (
    SyncPlaylistFromSpotifyUseCase,
)
from app.domain.exceptions import BusinessRuleViolationError, EntityNotFoundError
from app.domain.models.playlist import Playlist
from app.domain.models.track import Track
from app.domain.models.user import User


def _catalog_track(track_id: str) -> CatalogTrack:
    return CatalogTrack(
        external_id=track_id,
        title=f"T{track_id}",
        artist="Art",
        album="Alb",
        preview_url=None,
        uri=f"spotify:track:{track_id}",
        duration_ms=200_000,
        cover_url=None,
        release_year=2020,
    )


class _Harness:
    def __init__(
        self,
        pages: list[list[CatalogTrack]],
        playlists: list[Playlist] | None = None,
    ) -> None:
        user = User(
            user_id=1,
            email="u@ribbit.com",
            password_hash="pw",
            display_name="U",
            age=25,
            plan_id=1,
        )
        self.user_repo = MagicMock(spec=UserRepositoryPort)
        self.user_repo.find_by_id.return_value = user
        self.source = MagicMock(spec=PlaylistSourcePort)
        self.source.get_playlist.return_value = ProviderPlaylist(
            external_id="p1", name="Mix", description="d"
        )
        total_items = sum(len(p) for p in pages)

        def get_items(_id: str, limit: int, offset: int) -> PlaylistItemsPage:
            idx = offset // 50
            page_tracks = pages[idx] if idx < len(pages) else []
            return PlaylistItemsPage(
                items=page_tracks,
                total=total_items,
                raw_item_count=len(page_tracks),
            )

        self.source.get_playlist_items.side_effect = get_items
        ids = count(1)
        stored: dict[str, Track] = {}

        def save_track(track: Track) -> Track:
            if track.spotify_id is not None and track.spotify_id not in stored:
                track.track_id = next(ids)
                stored[track.spotify_id] = track
            return track

        self.track_repo = MagicMock(spec=TrackRepositoryPort)
        self.track_repo.find_by_spotify_id.side_effect = stored.get
        self.track_repo.save.side_effect = save_track
        self.playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
        self.playlist_repo.list_by_user.return_value = playlists or []
        self.playlist_repo.save.side_effect = lambda playlist: playlist
        self.use_case = SyncPlaylistFromSpotifyUseCase(
            self.user_repo, self.track_repo, self.playlist_repo, self.source
        )


def _command(**overrides: int | str) -> SyncPlaylistFromSpotifyCommand:
    return SyncPlaylistFromSpotifyCommand(
        user_id=1, spotify_playlist_id="p1", **overrides
    )


@pytest.mark.unit
class TestSyncPlaylist:
    def test_imports_tracks_across_pages_into_new_playlist(self) -> None:
        pages = [[_catalog_track(str(i)) for i in range(50)], [_catalog_track("x")]]
        harness = _Harness(pages)

        playlist = harness.use_case.execute(_command())

        offsets = [
            c.kwargs["offset"] for c in harness.source.get_playlist_items.call_args_list
        ]
        assert offsets == [0, 50]
        assert len(playlist.tracks) == 51
        assert playlist.tracks[-1].spotify_id == "x"
        assert (playlist.user_id, playlist.name, playlist.description) == (
            1,
            "Mix",
            "d",
        )
        assert playlist.spotify_playlist_id == "p1"
        assert playlist.is_exported is False
        harness.playlist_repo.save.assert_called_once_with(playlist)

    def test_stops_at_max_items(self) -> None:
        pages = [[_catalog_track(str(i)) for i in range(50)]] * 3
        harness = _Harness(pages)

        playlist = harness.use_case.execute(_command(max_items=50))

        assert len(playlist.tracks) == 50
        assert harness.source.get_playlist_items.call_count == 1

    def test_last_page_is_trimmed_to_remaining_items(self) -> None:
        harness = _Harness([[_catalog_track("a"), _catalog_track("b")]])

        harness.use_case.execute(_command(max_items=2))

        harness.source.get_playlist_items.assert_called_once_with(
            "p1", limit=2, offset=0
        )

    def test_duplicate_tracks_are_imported_once(self) -> None:
        harness = _Harness([[_catalog_track("a"), _catalog_track("a")]])

        playlist = harness.use_case.execute(_command())

        assert [t.spotify_id for t in playlist.tracks] == ["a"]

    def test_resync_replaces_tracks_of_existing_playlist(self) -> None:
        old = Track(
            track_id=99, title="Old", artist="A", duration_seconds=10, genre="Rock"
        )
        existing = Playlist(
            playlist_id=5,
            user_id=1,
            name="Mix",
            spotify_playlist_id="p1",
            initial_tracks=[old],
        )
        harness = _Harness([[_catalog_track("a")]], playlists=[existing])

        playlist = harness.use_case.execute(_command())

        assert playlist is existing
        assert [t.spotify_id for t in playlist.tracks] == ["a"]
        harness.playlist_repo.save.assert_called_once_with(existing)

    def test_unrelated_playlists_are_ignored(self) -> None:
        other = Playlist(
            playlist_id=5, user_id=1, name="Other", spotify_playlist_id="zz"
        )
        harness = _Harness([[_catalog_track("a")]], playlists=[other])

        playlist = harness.use_case.execute(_command())

        assert playlist.playlist_id is None

    def test_unknown_user_is_rejected_before_any_api_call(self) -> None:
        harness = _Harness([])
        harness.user_repo.find_by_id.return_value = None

        with pytest.raises(EntityNotFoundError):
            harness.use_case.execute(_command())

        harness.source.get_playlist.assert_not_called()

    def test_pages_with_skipped_entries_like_episodes_continue_paging(self) -> None:
        user = User(
            user_id=1,
            email="u@ribbit.com",
            password_hash="pw",
            display_name="U",
            age=25,
            plan_id=1,
        )
        user_repo = MagicMock(spec=UserRepositoryPort)
        user_repo.find_by_id.return_value = user
        source = MagicMock(spec=PlaylistSourcePort)
        source.get_playlist.return_value = ProviderPlaylist(
            external_id="p1", name="Mix", description="d"
        )
        # Page 1: 50 raw items in Spotify, but only 49 tracks mapped (1 episode skipped)
        page1_tracks = [_catalog_track(str(i)) for i in range(49)]
        # Page 2: 1 raw item and 1 track mapped
        page2_tracks = [_catalog_track("50")]

        def get_items(_id: str, limit: int, offset: int) -> PlaylistItemsPage:
            if offset == 0:
                return PlaylistItemsPage(
                    items=page1_tracks,
                    total=51,
                    raw_item_count=50,
                )
            if offset == 50:
                return PlaylistItemsPage(
                    items=page2_tracks,
                    total=51,
                    raw_item_count=1,
                )
            return PlaylistItemsPage(items=[], total=51, raw_item_count=0)

        source.get_playlist_items.side_effect = get_items

        track_repo = MagicMock(spec=TrackRepositoryPort)
        ids = count(1)
        track_repo.find_by_spotify_id.return_value = None
        track_repo.save.side_effect = lambda t: Track(
            track_id=next(ids),
            spotify_id=t.spotify_id,
            title=t.title,
            artist=t.artist,
            duration_seconds=t.duration_seconds,
            genre=t.genre,
        )
        playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
        playlist_repo.list_by_user.return_value = []
        playlist_repo.save.side_effect = lambda playlist: playlist

        use_case = SyncPlaylistFromSpotifyUseCase(
            user_repo, track_repo, playlist_repo, source
        )
        playlist = use_case.execute(_command())

        assert len(playlist.tracks) == 50
        assert source.get_playlist_items.call_count == 2
        offsets = [c.kwargs["offset"] for c in source.get_playlist_items.call_args_list]
        assert offsets == [0, 50]

    def test_sync_playlist_rejects_non_positive_max_items(self) -> None:
        with pytest.raises(BusinessRuleViolationError, match="positive"):
            _command(max_items=0)

        with pytest.raises(BusinessRuleViolationError, match="positive"):
            _command(max_items=-10)
