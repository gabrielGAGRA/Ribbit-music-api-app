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
    EntityNotFoundError,
    ExternalServiceError,
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
        access_token=None,
        refresh_token=None,
    )
    playlist_repo.save.assert_called_once_with(playlist)


def test_export_playlist_to_spotify_unlinked_account_raises_connection_required_error() -> (
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

    with pytest.raises(PermissionDeniedError) as exc_info:
        use_case.execute(user_id=1, playlist_id=5)

    assert exc_info.value.details.get("rule_name") == "spotify_connection_required"
    export_port.export_playlist.assert_not_called()


def test_export_playlist_to_spotify_succeeds_without_spotify_premium() -> None:
    user_free_spotify = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="Frog",
        age=25,
        plan_id=1,
        spotify_id="spotify_free_user",
        spotify_premium=False,
    )
    playlist = Playlist(
        playlist_id=5,
        user_id=1,
        name="Free Spotify Playlist",
        initial_tracks=[],
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user_free_spotify

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.find_by_id.return_value = playlist
    playlist_repo.save.side_effect = lambda p: p

    export_port = MagicMock(spec=PlaylistExportPort)
    export_port.export_playlist.return_value = "spotify_pl_free"

    use_case = ExportPlaylistToSpotifyUseCase(
        user_repo=user_repo,
        playlist_repo=playlist_repo,
        export_port=export_port,
    )

    result = use_case.execute(user_id=1, playlist_id=5)

    assert result.is_exported is True
    assert result.spotify_playlist_id == "spotify_pl_free"
    export_port.export_playlist.assert_called_once_with(
        account_id="spotify_free_user",
        name="Free Spotify Playlist",
        track_ids=[],
        access_token=None,
        refresh_token=None,
    )


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


def test_export_playlist_resolves_missing_spotify_ids_from_catalog() -> None:
    from app.application.ports.repositories.track_repository import TrackRepositoryPort
    from app.application.ports.services.music_service import (
        CatalogTrack,
        TrackCatalogPort,
    )

    user = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="Frog",
        age=25,
        plan_id=2,
        spotify_id="spotify_user_123",
    )
    track = Track(
        track_id=10,
        title="Numb",
        artist="Linkin Park",
        duration_seconds=185,
        genre="Rock",
        spotify_id=None,
    )
    playlist = Playlist(
        playlist_id=5,
        user_id=1,
        name="Rock Mix",
        initial_tracks=[track],
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.find_by_id.return_value = playlist
    playlist_repo.get_cover_image.return_value = None
    playlist_repo.save.side_effect = lambda p: p

    track_catalog = MagicMock(spec=TrackCatalogPort)
    track_catalog.search_tracks.return_value = [
        CatalogTrack(
            external_id="2nLtzopw4rPReszdYBJU6h",
            title="Numb",
            artist="Linkin Park",
            album="Meteora",
            preview_url=None,
        )
    ]

    track_repo = MagicMock(spec=TrackRepositoryPort)
    export_port = MagicMock(spec=PlaylistExportPort)
    export_port.export_playlist.return_value = "spotify_pl_111"

    use_case = ExportPlaylistToSpotifyUseCase(
        user_repo=user_repo,
        playlist_repo=playlist_repo,
        export_port=export_port,
        track_catalog=track_catalog,
        track_repo=track_repo,
    )

    result = use_case.execute(user_id=1, playlist_id=5)

    assert result.spotify_playlist_id == "spotify_pl_111"
    assert track.spotify_id == "2nLtzopw4rPReszdYBJU6h"
    track_catalog.search_tracks.assert_called_once_with("Numb Linkin Park", limit=1)
    track_repo.save.assert_called_once_with(track)
    export_port.export_playlist.assert_called_once_with(
        account_id="spotify_user_123",
        name="Rock Mix",
        track_ids=["2nLtzopw4rPReszdYBJU6h"],
        access_token=None,
        refresh_token=None,
    )


@pytest.mark.parametrize(
    ("content_type", "image_bytes"),
    [
        ("image/jpeg", b"\xff\xd8\xff\xe0" + b"a" * 100),
        ("image/png", b"\x89PNG\r\n\x1a\n" + b"a" * 100),
        ("image/webp", b"RIFF\x00\x00\x00\x00WEBP" + b"a" * 100),
    ],
    ids=["jpeg", "png", "webp"],
)
def test_export_playlist_forwards_cover_image_to_export_port(
    content_type: str, image_bytes: bytes
) -> None:
    user = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="Frog",
        age=25,
        plan_id=2,
        spotify_id="spotify_user_123",
    )
    playlist = Playlist(playlist_id=5, user_id=1, name="Cover Mix", initial_tracks=[])

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.find_by_id.return_value = playlist
    playlist_repo.get_cover_image.return_value = (content_type, image_bytes)
    playlist_repo.save.side_effect = lambda p: p

    export_port = MagicMock(spec=PlaylistExportPort)
    export_port.export_playlist.return_value = "spotify_pl_222"

    use_case = ExportPlaylistToSpotifyUseCase(
        user_repo=user_repo,
        playlist_repo=playlist_repo,
        export_port=export_port,
    )

    result = use_case.execute(user_id=1, playlist_id=5)

    assert result.spotify_playlist_id == "spotify_pl_222"
    export_port.export_playlist.assert_called_once_with(
        account_id="spotify_user_123",
        name="Cover Mix",
        track_ids=[],
        access_token=None,
        refresh_token=None,
        cover_image=(content_type, image_bytes),
    )


def test_export_playlist_skips_missing_cover_image() -> None:
    user = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="Frog",
        age=25,
        plan_id=2,
        spotify_id="spotify_user_123",
    )
    playlist = Playlist(playlist_id=5, user_id=1, name="No Cover", initial_tracks=[])

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.find_by_id.return_value = playlist
    playlist_repo.get_cover_image.return_value = None
    playlist_repo.save.side_effect = lambda p: p

    export_port = MagicMock(spec=PlaylistExportPort)
    export_port.export_playlist.return_value = "spotify_pl_333"

    use_case = ExportPlaylistToSpotifyUseCase(
        user_repo=user_repo,
        playlist_repo=playlist_repo,
        export_port=export_port,
    )

    result = use_case.execute(user_id=1, playlist_id=5)

    assert result.spotify_playlist_id == "spotify_pl_333"
    export_port.export_playlist.assert_called_once_with(
        account_id="spotify_user_123",
        name="No Cover",
        track_ids=[],
        access_token=None,
        refresh_token=None,
    )


@pytest.mark.parametrize("error_kind", ["auth", "forbidden"])
def test_export_playlist_to_spotify_auth_or_forbidden_error_maps_to_permission_denied(
    error_kind: str,
) -> None:
    user = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="Frog",
        age=25,
        plan_id=2,
        spotify_id="spotify_user_123",
    )
    playlist = Playlist(playlist_id=5, user_id=1, name="Pond Favorites")

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.find_by_id.return_value = playlist
    playlist_repo.get_cover_image.return_value = None

    export_port = MagicMock(spec=PlaylistExportPort)
    export_port.export_playlist.side_effect = ExternalServiceError(
        "Spotify rejected token.",
        service_name="spotify",
        details={"error_kind": error_kind},
    )

    use_case = ExportPlaylistToSpotifyUseCase(
        user_repo=user_repo,
        playlist_repo=playlist_repo,
        export_port=export_port,
    )

    with pytest.raises(PermissionDeniedError) as exc_info:
        use_case.execute(user_id=1, playlist_id=5)

    assert exc_info.value.details.get("rule_name") == "spotify_connection_required"
    playlist_repo.save.assert_not_called()


def test_export_playlist_to_spotify_other_external_service_error_propagates() -> None:
    user = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="Frog",
        age=25,
        plan_id=2,
        spotify_id="spotify_user_123",
    )
    playlist = Playlist(playlist_id=5, user_id=1, name="Pond Favorites")

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.find_by_id.return_value = playlist
    playlist_repo.get_cover_image.return_value = None

    original_error = ExternalServiceError(
        "Spotify rate limit exceeded.",
        service_name="spotify",
        details={"error_kind": "rate_limit"},
    )
    export_port = MagicMock(spec=PlaylistExportPort)
    export_port.export_playlist.side_effect = original_error

    use_case = ExportPlaylistToSpotifyUseCase(
        user_repo=user_repo,
        playlist_repo=playlist_repo,
        export_port=export_port,
    )

    with pytest.raises(ExternalServiceError) as exc_info:
        use_case.execute(user_id=1, playlist_id=5)

    assert exc_info.value is original_error
    playlist_repo.save.assert_not_called()
