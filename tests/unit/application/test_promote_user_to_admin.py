"""Unit tests for PromoteUserToAdminUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.admin.promote_user_to_admin import (
    PromoteUserToAdminUseCase,
)
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.user import User


def test_promote_user_to_admin_user_not_found_raises_error() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None

    use_case = PromoteUserToAdminUseCase(user_repo=user_repo)

    with pytest.raises(EntityNotFoundError, match="User 42 not found"):
        use_case.execute(user_id=42)

    user_repo.save.assert_not_called()


def test_promote_user_to_admin_sets_flag_and_saves_user() -> None:
    user = User(
        user_id=42,
        email="mod@test.com",
        password_hash="hash",
        display_name="Moderator",
        age=28,
        plan_id=1,
        is_admin=False,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user
    user_repo.save.side_effect = lambda u: u

    use_case = PromoteUserToAdminUseCase(user_repo=user_repo)
    promoted = use_case.execute(user_id=42)

    assert promoted.is_admin is True
    user_repo.find_by_id.assert_called_once_with(42)
    user_repo.save.assert_called_once_with(user)
