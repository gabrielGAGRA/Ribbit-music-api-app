"""Unit tests for UpdateAdminRoleUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.admin.update_admin_role import (
    UpdateAdminRoleUseCase,
)
from app.domain.exceptions import BusinessRuleViolationError, EntityNotFoundError
from app.domain.models import User


def test_update_admin_role_prevents_self_demotion() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    use_case = UpdateAdminRoleUseCase(user_repo=user_repo)

    with pytest.raises(
        BusinessRuleViolationError, match="Administrator cannot revoke own access"
    ):
        use_case.execute(admin_id=1, target_user_id=1, is_admin=False)

    user_repo.find_by_id.assert_not_called()
    user_repo.save.assert_not_called()


def test_update_admin_role_promotes_another_user() -> None:
    target = User(
        user_id=2,
        email="moderator@ribbit.com",
        password_hash="pw",
        display_name="Mod",
        age=28,
        plan_id=1,
        is_admin=False,
    )

    def _save_user(u: User) -> User:
        return u

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = target
    user_repo.save.side_effect = _save_user
    audit_log_repo = MagicMock()

    use_case = UpdateAdminRoleUseCase(
        user_repo=user_repo,
        eligible_emails=("moderator@ribbit.com",),
        audit_log_repo=audit_log_repo,
    )
    result = use_case.execute(admin_id=1, target_user_id=2, is_admin=True)

    assert result.is_admin is True
    user_repo.save.assert_called_once_with(target)
    audit_log_repo.log_event.assert_called_once_with(
        "ADMIN_ROLE_UPDATED:moderator@ribbit.com:True", "OK"
    )


def test_update_admin_role_user_not_found_raises_entity_not_found() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None

    use_case = UpdateAdminRoleUseCase(user_repo=user_repo)

    with pytest.raises(EntityNotFoundError, match="User with ID 99 not found"):
        use_case.execute(admin_id=1, target_user_id=99, is_admin=False)


def test_update_admin_role_rejects_ineligible_user_promotion() -> None:
    target = User(
        user_id=2,
        email="ineligible@example.com",
        password_hash="pw",
        display_name="Ineligible",
        age=28,
        plan_id=1,
        is_admin=False,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = target

    use_case = UpdateAdminRoleUseCase(
        user_repo=user_repo,
        eligible_emails=("gabriel.agra@usp.br",),
    )

    with pytest.raises(
        BusinessRuleViolationError,
        match="User ineligible@example.com is not eligible",
    ):
        use_case.execute(admin_id=1, target_user_id=2, is_admin=True)

    user_repo.save.assert_not_called()


def test_update_admin_role_rejects_promotion_when_eligible_emails_empty() -> None:
    target = User(
        user_id=2,
        email="someone@example.com",
        password_hash="pw",
        display_name="Someone",
        age=28,
        plan_id=1,
        is_admin=False,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = target

    use_case = UpdateAdminRoleUseCase(
        user_repo=user_repo,
        eligible_emails=(),
    )

    with pytest.raises(
        BusinessRuleViolationError,
        match="User someone@example.com is not eligible",
    ):
        use_case.execute(admin_id=1, target_user_id=2, is_admin=True)

    user_repo.save.assert_not_called()
