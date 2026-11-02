"""Unit tests for ListUserPlaylistsUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.playlist.list_user_playlists import (
    ListUserPlaylistsUseCase,
)
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.playlist import Playlist
from app.domain.models.user import User


def test_list_user_playlists_returns_playlists_for_existing_user() -> None:
    user = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="Frog",
        age=20,
        plan_id=1,
    )
    playlists = [
        Playlist(playlist_id=1, user_id=1, name="Mix 1"),
        Playlist(playlist_id=2, user_id=1, name="Mix 2"),
    ]

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.list_by_user.return_value = playlists

    use_case = ListUserPlaylistsUseCase(
        user_repo=user_repo,
        playlist_repo=playlist_repo,
    )

    result = use_case.execute(user_id=1)

    assert result == playlists
    user_repo.find_by_id.assert_called_once_with(1)
    playlist_repo.list_by_user.assert_called_once_with(1)


def test_list_user_playlists_user_not_found_raises_entity_not_found() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)

    use_case = ListUserPlaylistsUseCase(
        user_repo=user_repo,
        playlist_repo=playlist_repo,
    )

    with pytest.raises(EntityNotFoundError, match="User with ID 999 not found"):
        use_case.execute(user_id=999)

    playlist_repo.list_by_user.assert_not_called()
