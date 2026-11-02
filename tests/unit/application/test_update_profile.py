"""Unit tests for UpdateProfileUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.user_dtos import UpdateProfileCommand
from app.application.use_cases.user.update_profile import UpdateProfileUseCase
from app.domain.exceptions import AuthenticationRequiredError, EntityNotFoundError
from app.domain.models import User


def test_update_profile_display_name_only_success() -> None:
    user = User(
        user_id=1,
        email="user@test.com",
        password_hash="hashed_old_pw",
        display_name="Old Name",
        age=25,
        plan_id=1,
    )
    user_repo = MagicMock()
    user_repo.find_by_id.return_value = user
    user_repo.save.side_effect = lambda u: u
    hasher = MagicMock()

    use_case = UpdateProfileUseCase(user_repo=user_repo, password_hasher=hasher)
    command = UpdateProfileCommand(user_id=1, display_name="New Name")
    updated = use_case.execute(command)

    assert updated.display_name == "New Name"
    assert updated.password_hash == "hashed_old_pw"
    hasher.verify_password.assert_not_called()
    hasher.hash_password.assert_not_called()
    user_repo.save.assert_called_once_with(user)


def test_update_profile_password_success() -> None:
    user = User(
        user_id=1,
        email="user@test.com",
        password_hash="hashed_old_pw",
        display_name="User",
        age=25,
        plan_id=1,
    )
    user_repo = MagicMock()
    user_repo.find_by_id.return_value = user
    user_repo.save.side_effect = lambda u: u
    hasher = MagicMock()
    hasher.verify_password.return_value = True
    hasher.hash_password.return_value = "hashed_new_pw"

    use_case = UpdateProfileUseCase(user_repo=user_repo, password_hasher=hasher)
    command = UpdateProfileCommand(
        user_id=1,
        new_password="new_password_123",
        current_password="old_password_123",
    )
    updated = use_case.execute(command)

    assert updated.password_hash == "hashed_new_pw"
    hasher.verify_password.assert_called_once_with("old_password_123", "hashed_old_pw")
    hasher.hash_password.assert_called_once_with("new_password_123")


def test_update_profile_missing_current_password_raises_error() -> None:
    user = User(
        user_id=1,
        email="user@test.com",
        password_hash="hashed_old_pw",
        display_name="User",
        age=25,
        plan_id=1,
    )
    user_repo = MagicMock()
    user_repo.find_by_id.return_value = user
    hasher = MagicMock()

    use_case = UpdateProfileUseCase(user_repo=user_repo, password_hasher=hasher)
    command = UpdateProfileCommand(
        user_id=1,
        new_password="new_password_123",
        current_password=None,
    )

    with pytest.raises(
        AuthenticationRequiredError, match="Current password is required"
    ):
        use_case.execute(command)

    hasher.verify_password.assert_not_called()
    user_repo.save.assert_not_called()


def test_update_profile_wrong_current_password_raises_error() -> None:
    user = User(
        user_id=1,
        email="user@test.com",
        password_hash="hashed_old_pw",
        display_name="User",
        age=25,
        plan_id=1,
    )
    user_repo = MagicMock()
    user_repo.find_by_id.return_value = user
    hasher = MagicMock()
    hasher.verify_password.return_value = False

    use_case = UpdateProfileUseCase(user_repo=user_repo, password_hasher=hasher)
    command = UpdateProfileCommand(
        user_id=1,
        new_password="new_password_123",
        current_password="wrong_password",
    )

    with pytest.raises(
        AuthenticationRequiredError, match="Current password is required"
    ):
        use_case.execute(command)

    hasher.verify_password.assert_called_once_with("wrong_password", "hashed_old_pw")
    user_repo.save.assert_not_called()


def test_update_profile_user_not_found_raises_error() -> None:
    user_repo = MagicMock()
    user_repo.find_by_id.return_value = None
    hasher = MagicMock()

    use_case = UpdateProfileUseCase(user_repo=user_repo, password_hasher=hasher)
    command = UpdateProfileCommand(user_id=999, display_name="Ghost")

    with pytest.raises(EntityNotFoundError):
        use_case.execute(command)
