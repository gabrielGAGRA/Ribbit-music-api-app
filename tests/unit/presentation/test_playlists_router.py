"""Unit tests for playlists router functions."""

from unittest.mock import MagicMock

from app.application.dtos import (
    AddTrackToPlaylistCommand,
    CreateDeckPlaylistCommand,
)
from app.application.use_cases.playlist import (
    AddTrackToPlaylistUseCase,
    CreateDeckPlaylistUseCase,
    DeletePlaylistUseCase,
    ExportPlaylistToSpotifyUseCase,
    GetPlaylistDeckUseCase,
    ListUserPlaylistsUseCase,
    RemoveTrackFromPlaylistUseCase,
)
from app.domain.models import Playlist, Track
from app.presentation.routers.playlists import (
    create_deck_playlist,
    export_playlist_to_spotify,
    list_playlists,
    swipe_add_track,
)
from app.presentation.schemas import (
    DeckPlaylistRequest,
    SwipeAddTrackRequest,
)


def test_create_deck_playlist_forwards_command_and_returns_playlist() -> None:
    mock_use_case = MagicMock(spec=CreateDeckPlaylistUseCase)
    track = Track(
        track_id=1,
        title="Track 1",
        artist="Artist 1",
        duration_seconds=180,
        genre="rock",
    )
    playlist = Playlist(
        playlist_id=10,
        user_id=3,
        name="Roadtrip Deck",
        description="Energetic rock",
        initial_tracks=[track],
    )
    mock_use_case.execute.return_value = playlist
    req = DeckPlaylistRequest(
        user_id=3,
        name="Roadtrip Deck",
        duration_minutes=30,
        genre="rock",
        year=2020,
        artist="Artist 1",
        country="US",
        description="Energetic rock",
    )

    res = create_deck_playlist(req=req, use_case=mock_use_case)

    assert res.playlist_id == 10
    assert res.user_id == 3
    assert res.name == "Roadtrip Deck"
    assert len(res.tracks) == 1
    assert res.tracks[0].track_id == 1
    mock_use_case.execute.assert_called_once_with(
        CreateDeckPlaylistCommand(
            user_id=3,
            name="Roadtrip Deck",
            duration_minutes=30,
            genre="rock",
            year=2020,
            artist="Artist 1",
            country="US",
            description="Energetic rock",
        )
    )


def test_swipe_add_track_executes_command_and_returns_success() -> None:
    mock_use_case = MagicMock(spec=AddTrackToPlaylistUseCase)
    req = SwipeAddTrackRequest(track_id=99)

    res = swipe_add_track(
        playlist_id=10,
        req=req,
        user_id=3,
        use_case=mock_use_case,
    )

    assert res.success is True
    mock_use_case.execute.assert_called_once_with(
        AddTrackToPlaylistCommand(
            playlist_id=10,
            track_id=99,
            user_id=3,
        )
    )


def test_list_playlists_returns_mapped_user_playlists() -> None:
    mock_use_case = MagicMock(spec=ListUserPlaylistsUseCase)
    playlist = Playlist(
        playlist_id=11,
        user_id=3,
        name="My Favorites",
    )
    mock_use_case.execute.return_value = [playlist]

    res = list_playlists(user_id=3, use_case=mock_use_case)

    assert len(res) == 1
    assert res[0].playlist_id == 11
    assert res[0].name == "My Favorites"
    mock_use_case.execute.assert_called_once_with(user_id=3)


def test_export_playlist_to_spotify_returns_updated_playlist() -> None:
    mock_use_case = MagicMock(spec=ExportPlaylistToSpotifyUseCase)
    playlist = Playlist(
        playlist_id=11,
        user_id=3,
        name="My Favorites",
        spotify_playlist_id="sp_playlist_123",
        is_exported=True,
    )
    mock_use_case.execute.return_value = playlist

    res = export_playlist_to_spotify(
        playlist_id=11,
        user_id=3,
        use_case=mock_use_case,
    )

    assert res.playlist_id == 11
    assert res.is_exported is True
    assert res.spotify_playlist_id == "sp_playlist_123"
    mock_use_case.execute.assert_called_once_with(
        user_id=3,
        playlist_id=11,
    )


def test_get_playlist_deck_endpoint() -> None:
    from app.application.dtos.playlist_dtos import (
        GetPlaylistDeckCommand,
        PlaylistDeckResult,
    )
    from app.presentation.routers.playlists import get_playlist_deck

    mock_use_case = MagicMock(spec=GetPlaylistDeckUseCase)
    t = Track(
        track_id=1, title="Song", artist="Artist", duration_seconds=180, genre="Pop"
    )
    mock_use_case.execute.return_value = PlaylistDeckResult(
        items=[t], next_cursor=None, has_more=False
    )

    res = get_playlist_deck(
        playlist_id=10, current_user_id=3, limit=10, use_case=mock_use_case
    )

    assert len(res.items) == 1
    assert res.items[0].track_id == 1
    mock_use_case.execute.assert_called_once_with(
        GetPlaylistDeckCommand(playlist_id=10, user_id=3, limit=10, cursor_id=None)
    )


def test_remove_track_endpoint() -> None:
    from app.application.dtos.playlist_dtos import RemoveTrackFromPlaylistCommand
    from app.presentation.routers.playlists import remove_track

    mock_use_case = MagicMock(spec=RemoveTrackFromPlaylistUseCase)
    mock_use_case.execute.return_value = True

    res = remove_track(
        playlist_id=10, track_id=5, current_user_id=3, use_case=mock_use_case
    )

    assert res.success is True
    mock_use_case.execute.assert_called_once_with(
        RemoveTrackFromPlaylistCommand(playlist_id=10, track_id=5, user_id=3)
    )


def test_delete_playlist_endpoint() -> None:
    from app.application.dtos.playlist_dtos import DeletePlaylistCommand
    from app.presentation.routers.playlists import delete_playlist

    mock_use_case = MagicMock(spec=DeletePlaylistUseCase)
    mock_use_case.execute.return_value = True

    res = delete_playlist(playlist_id=10, current_user_id=3, use_case=mock_use_case)

    assert res.success is True
    mock_use_case.execute.assert_called_once_with(
        DeletePlaylistCommand(playlist_id=10, user_id=3)
    )
