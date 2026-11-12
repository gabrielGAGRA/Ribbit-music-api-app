"""Unit tests for GetPreferredThemeUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.user.get_preferred_theme import GetPreferredThemeUseCase
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.user import User


def test_get_preferred_theme_user_not_found_raises_error() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None

    use_case = GetPreferredThemeUseCase(user_repo=user_repo)

    with pytest.raises(EntityNotFoundError, match="User with ID 1 not found"):
        use_case.execute(user_id=1)


def test_get_preferred_theme_returns_theme() -> None:
    user = User(
        user_id=1,
        email="user@test.com",
        password_hash="hash",
        display_name="User",
        age=20,
        plan_id=1,
        preferred_theme="dark",
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    use_case = GetPreferredThemeUseCase(user_repo=user_repo)
    result = use_case.execute(user_id=1)

    assert result == "dark"
    user_repo.find_by_id.assert_called_once_with(1)
