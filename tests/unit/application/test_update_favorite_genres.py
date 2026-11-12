"""Unit tests for UpdateFavoriteGenresUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.user.update_favorite_genres import (
    UpdateFavoriteGenresUseCase,
)
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.user import User


def test_update_favorite_genres_user_not_found_raises_error() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None

    use_case = UpdateFavoriteGenresUseCase(user_repo=user_repo)

    with pytest.raises(EntityNotFoundError, match="User with ID 1 not found"):
        use_case.execute(user_id=1, favorite_genres=["rock", "pop"])


def test_update_favorite_genres_updates_and_saves() -> None:
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

    use_case = UpdateFavoriteGenresUseCase(user_repo=user_repo)
    result = use_case.execute(user_id=1, favorite_genres=["Rock", "Pop"])

    assert result.favorite_genres == frozenset({"rock", "pop"})
    user_repo.find_by_id.assert_called_once_with(1)
    user_repo.save.assert_called_once_with(user)
