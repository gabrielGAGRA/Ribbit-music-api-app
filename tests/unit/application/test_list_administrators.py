"""Unit tests for ListAdministratorsUseCase."""

from unittest.mock import MagicMock

from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.admin.list_administrators import (
    ListAdministratorsUseCase,
)
from app.domain.models import User


def test_list_administrators_filters_only_admin_users() -> None:
    admin = User(
        user_id=1,
        email="admin@ribbit.com",
        password_hash="pw",
        display_name="Admin",
        age=30,
        plan_id=1,
        is_admin=True,
    )
    regular = User(
        user_id=2,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="User",
        age=25,
        plan_id=1,
        is_admin=False,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.list_all.return_value = [admin, regular]

    use_case = ListAdministratorsUseCase(user_repo=user_repo)
    results = use_case.execute()

    assert len(results) == 1
    assert results[0].user_id == 1
    assert results[0].is_admin is True
