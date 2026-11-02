"""Unit tests for ExportPlaylistToSpotifyUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.ports.services.music_service import PlaylistExportPort
from app.application.use_cases.playlist.export_playlist_to_spotify import (
    ExportPlaylistToSpotifyUseCase,
)
from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    PermissionDeniedError,
)
from app.domain.models.playlist import Playlist
from app.domain.models.track import Track
from app.domain.models.user import User


def test_export_playlist_to_spotify_success_marks_exported_and_saves() -> None:
    user = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="Frog",
        age=25,
        plan_id=2,
        spotify_id="spotify_user_123",
    )
    t1 = Track(
        track_id=10,
        title="Track With Spotify ID",
        artist="Artist",
        duration_seconds=200,
        genre="Pop",
        spotify_id="sp_track_abc",
    )
    t2 = Track(
        track_id=20,
        title="Track Fallback ID",
        artist="Artist",
        duration_seconds=180,
        genre="Pop",
        spotify_id=None,
    )
    playlist = Playlist(
        playlist_id=5,
        user_id=1,
        name="Pond Favorites",
        initial_tracks=[t1, t2],
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.find_by_id.return_value = playlist
    playlist_repo.save.side_effect = lambda p: p

    export_port = MagicMock(spec=PlaylistExportPort)
    export_port.export_playlist.return_value = "spotify_pl_999"

    use_case = ExportPlaylistToSpotifyUseCase(
        user_repo=user_repo,
        playlist_repo=playlist_repo,
        export_port=export_port,
    )

    result = use_case.execute(user_id=1, playlist_id=5)

    assert result is playlist
    assert result.is_exported is True
    assert result.spotify_playlist_id == "spotify_pl_999"
    export_port.export_playlist.assert_called_once_with(
        account_id="spotify_user_123",
        name="Pond Favorites",
        track_ids=["sp_track_abc", "20"],
    )
    playlist_repo.save.assert_called_once_with(playlist)


def test_export_playlist_to_spotify_unlinked_account_raises_business_rule_error() -> (
    None
):
    user_without_spotify = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="Frog",
        age=25,
        plan_id=1,
        spotify_id=None,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user_without_spotify

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    export_port = MagicMock(spec=PlaylistExportPort)

    use_case = ExportPlaylistToSpotifyUseCase(
        user_repo=user_repo,
        playlist_repo=playlist_repo,
        export_port=export_port,
    )

    with pytest.raises(BusinessRuleViolationError, match="linked Spotify account"):
        use_case.execute(user_id=1, playlist_id=5)

    export_port.export_playlist.assert_not_called()


def test_export_playlist_to_spotify_idor_non_owner_raises_permission_denied() -> None:
    user = User(
        user_id=99,
        email="other@ribbit.com",
        password_hash="pw",
        display_name="Other",
        age=25,
        plan_id=1,
        spotify_id="sp_99",
    )
    playlist = Playlist(playlist_id=5, user_id=1, name="Private Playlist")

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.find_by_id.return_value = playlist

    export_port = MagicMock(spec=PlaylistExportPort)

    use_case = ExportPlaylistToSpotifyUseCase(
        user_repo=user_repo,
        playlist_repo=playlist_repo,
        export_port=export_port,
    )

    with pytest.raises(PermissionDeniedError, match="does not belong to you"):
        use_case.execute(user_id=99, playlist_id=5)

    export_port.export_playlist.assert_not_called()


def test_export_playlist_to_spotify_user_not_found_raises_entity_not_found() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None

    use_case = ExportPlaylistToSpotifyUseCase(
        user_repo=user_repo,
        playlist_repo=MagicMock(spec=PlaylistRepositoryPort),
        export_port=MagicMock(spec=PlaylistExportPort),
    )

    with pytest.raises(EntityNotFoundError, match="User with ID 999 not found"):
        use_case.execute(user_id=999, playlist_id=5)


def test_export_playlist_to_spotify_playlist_not_found_raises_entity_not_found() -> (
    None
):
    user = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="Frog",
        age=25,
        plan_id=1,
        spotify_id="sp_1",
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.find_by_id.return_value = None

    use_case = ExportPlaylistToSpotifyUseCase(
        user_repo=user_repo,
        playlist_repo=playlist_repo,
        export_port=MagicMock(spec=PlaylistExportPort),
    )

    with pytest.raises(EntityNotFoundError, match="Playlist with ID 404 not found"):
        use_case.execute(user_id=1, playlist_id=404)
