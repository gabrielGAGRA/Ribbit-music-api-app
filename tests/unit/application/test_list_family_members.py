"""Unit tests for ListFamilyMembersUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.user.list_family_members import ListFamilyMembersUseCase
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.user import User


def test_list_family_members_primary_user_not_found_raises_error() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None

    use_case = ListFamilyMembersUseCase(user_repo=user_repo)

    with pytest.raises(EntityNotFoundError, match="Primary user 1 not found"):
        use_case.execute(primary_user_id=1)

    user_repo.list_dependents.assert_not_called()


def test_list_family_members_returns_dependents_from_repository() -> None:
    primary_user = User(
        user_id=1,
        email="primary@test.com",
        password_hash="hash",
        display_name="Primary",
        age=35,
        plan_id=3,
    )
    dependent = User(
        user_id=2,
        email="dep@test.com",
        password_hash="hash",
        display_name="Dependent",
        age=14,
        plan_id=3,
        primary_account_id=1,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = primary_user
    user_repo.list_dependents.return_value = [dependent]

    use_case = ListFamilyMembersUseCase(user_repo=user_repo)
    result = use_case.execute(primary_user_id=1)

    assert result == [dependent]
    user_repo.find_by_id.assert_called_once_with(1)
    user_repo.list_dependents.assert_called_once_with(1)
