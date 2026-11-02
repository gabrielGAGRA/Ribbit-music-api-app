"""Unit tests for GetPlaylistDeckUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.playlist_dtos import GetPlaylistDeckCommand
from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.playlist.get_playlist_deck import (
    GetPlaylistDeckUseCase,
)
from app.domain.exceptions import PermissionDeniedError
from app.domain.models import Interaction, InteractionAction, Playlist, Track, User


def test_get_playlist_deck_excludes_playlist_tracks_and_rejected_tracks() -> None:
    user = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="hash",
        display_name="User",
        age=25,
        plan_id=1,
    )
    t1 = Track(
        track_id=1, title="Track 1", artist="Artist", duration_seconds=180, genre="Rock"
    )
    t2 = Track(
        track_id=2, title="Track 2", artist="Artist", duration_seconds=180, genre="Rock"
    )
    t3 = Track(
        track_id=3, title="Track 3", artist="Artist", duration_seconds=180, genre="Rock"
    )
    t4 = Track(
        track_id=4, title="Track 4", artist="Artist", duration_seconds=180, genre="Rock"
    )

    playlist = Playlist(
        playlist_id=10,
        user_id=1,
        name="Deck",
        max_duration_seconds=1800,
        initial_tracks=[t1],
    )

    dislike = Interaction(user_id=1, track_id=2, action=InteractionAction.DISLIKE)

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.find_by_id.return_value = playlist

    interaction_repo = MagicMock(spec=InteractionRepositoryPort)
    interaction_repo.list_by_user.return_value = [dislike]

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.list_active.return_value = [t1, t2, t3, t4]

    use_case = GetPlaylistDeckUseCase(
        user_repo=user_repo,
        playlist_repo=playlist_repo,
        track_repo=track_repo,
        interaction_repo=interaction_repo,
    )
    cmd = GetPlaylistDeckCommand(playlist_id=10, user_id=1, limit=10)

    result = use_case.execute(cmd)

    # t1 is already in playlist, t2 is disliked, so only t3 and t4 should be returned
    assert [t.track_id for t in result.items] == [3, 4]
    assert result.has_more is False
    assert result.next_cursor is None


def test_get_playlist_deck_returns_empty_when_max_duration_is_exhausted() -> None:
    user = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="hash",
        display_name="User",
        age=25,
        plan_id=1,
    )
    t1 = Track(
        track_id=1, title="Track 1", artist="Artist", duration_seconds=600, genre="Rock"
    )
    playlist = Playlist(
        playlist_id=10,
        user_id=1,
        name="Full Deck",
        max_duration_seconds=600,
        initial_tracks=[t1],
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.find_by_id.return_value = playlist

    track_repo = MagicMock(spec=TrackRepositoryPort)

    use_case = GetPlaylistDeckUseCase(
        user_repo=user_repo,
        playlist_repo=playlist_repo,
        track_repo=track_repo,
    )
    result = use_case.execute(playlist_id=10, user_id=1)

    assert result.items == []
    assert result.has_more is False
    assert result.next_cursor is None
    track_repo.list_active.assert_not_called()


def test_get_playlist_deck_non_owner_raises_permission_denied() -> None:
    user = User(
        user_id=2,
        email="other@ribbit.com",
        password_hash="hash",
        display_name="Other",
        age=25,
        plan_id=1,
    )
    playlist = Playlist(playlist_id=10, user_id=1, name="Deck")

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.find_by_id.return_value = playlist

    use_case = GetPlaylistDeckUseCase(
        user_repo=user_repo,
        playlist_repo=playlist_repo,
        track_repo=MagicMock(spec=TrackRepositoryPort),
    )
    with pytest.raises(PermissionDeniedError, match="playlist does not belong"):
        use_case.execute(playlist_id=10, user_id=2)


def test_get_playlist_deck_filters_explicit_tracks_for_minors() -> None:
    minor = User(
        user_id=3,
        email="minor@ribbit.com",
        password_hash="hash",
        display_name="Minor",
        age=15,
        plan_id=1,
    )
    playlist = Playlist(playlist_id=10, user_id=3, name="Teen Deck")

    clean_track = Track(
        track_id=1,
        title="Clean",
        artist="Artist",
        duration_seconds=180,
        genre="Pop",
        explicit=False,
    )
    explicit_track = Track(
        track_id=2,
        title="Explicit",
        artist="Artist",
        duration_seconds=180,
        genre="Rap",
        explicit=True,
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = minor

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.find_by_id.return_value = playlist

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.list_active.return_value = [clean_track, explicit_track]

    use_case = GetPlaylistDeckUseCase(
        user_repo=user_repo,
        playlist_repo=playlist_repo,
        track_repo=track_repo,
    )
    result = use_case.execute(playlist_id=10, user_id=3)

    assert [t.track_id for t in result.items] == [1]
