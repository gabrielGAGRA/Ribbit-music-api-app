"""Unit tests for DeletePlaylistUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.playlist_dtos import DeletePlaylistCommand
from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.playlist.delete_playlist import (
    DeletePlaylistUseCase,
)
from app.domain.exceptions import PermissionDeniedError
from app.domain.models import Playlist, User


def test_delete_playlist_success_owner_only() -> None:
    user = User(
        user_id=1,
        email="owner@ribbit.com",
        password_hash="pw",
        display_name="Owner",
        age=30,
        plan_id=1,
    )
    playlist = Playlist(playlist_id=5, user_id=1, name="My Playlist")

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.find_by_id.return_value = playlist
    playlist_repo.delete.return_value = True

    use_case = DeletePlaylistUseCase(user_repo=user_repo, playlist_repo=playlist_repo)
    result = use_case.execute(DeletePlaylistCommand(playlist_id=5, user_id=1))

    assert result is True
    playlist_repo.delete.assert_called_once_with(5)


def test_delete_playlist_non_owner_raises_permission_denied() -> None:
    user = User(
        user_id=2,
        email="other@ribbit.com",
        password_hash="pw",
        display_name="Other",
        age=30,
        plan_id=1,
    )
    playlist = Playlist(playlist_id=5, user_id=1, name="Victim Playlist")

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.find_by_id.return_value = playlist

    use_case = DeletePlaylistUseCase(user_repo=user_repo, playlist_repo=playlist_repo)
    with pytest.raises(PermissionDeniedError, match="playlist does not belong"):
        use_case.execute(DeletePlaylistCommand(playlist_id=5, user_id=2))

    playlist_repo.delete.assert_not_called()
