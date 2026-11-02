"""Unit tests for LinkSpotifyAccountUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.user.link_spotify_account import (
    LinkSpotifyAccountUseCase,
)
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.user import User


def test_link_spotify_account_user_not_found_raises_error() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None

    use_case = LinkSpotifyAccountUseCase(user_repo=user_repo)

    with pytest.raises(EntityNotFoundError, match="User with ID 1 not found"):
        use_case.execute(user_id=1, spotify_id="spotify:user:123")

    user_repo.save.assert_not_called()


def test_link_spotify_account_blank_spotify_id_raises_value_error() -> None:
    user = User(
        user_id=1,
        email="user@test.com",
        password_hash="hash",
        display_name="User",
        age=20,
        plan_id=1,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    use_case = LinkSpotifyAccountUseCase(user_repo=user_repo)

    with pytest.raises(ValueError, match="Spotify ID cannot be blank"):
        use_case.execute(user_id=1, spotify_id="   ")

    user_repo.save.assert_not_called()


def test_link_spotify_account_updates_and_saves_user() -> None:
    user = User(
        user_id=1,
        email="user@test.com",
        password_hash="hash",
        display_name="User",
        age=20,
        plan_id=1,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user
    user_repo.save.side_effect = lambda u: u

    use_case = LinkSpotifyAccountUseCase(user_repo=user_repo)
    updated_user = use_case.execute(user_id=1, spotify_id="  sp_user_abc  ")

    assert updated_user.spotify_id == "sp_user_abc"
    user_repo.save.assert_called_once_with(user)
