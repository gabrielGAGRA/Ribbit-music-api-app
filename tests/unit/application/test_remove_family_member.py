"""Unit tests for RemoveFamilyMemberUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.plan_repository import PlanRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.user.remove_family_member import (
    RemoveFamilyMemberUseCase,
)
from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError
from app.domain.models.plan import Plan
from app.domain.models.user import User


def test_remove_family_member_primary_user_not_found_raises_error() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None
    plan_repo = MagicMock(spec=PlanRepositoryPort)

    use_case = RemoveFamilyMemberUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(EntityNotFoundError, match="Primary user 1 not found"):
        use_case.execute(primary_user_id=1, member_user_id=2)

    user_repo.save.assert_not_called()


def test_remove_family_member_target_member_not_found_raises_error() -> None:
    primary_user = User(
        user_id=1,
        email="primary@test.com",
        password_hash="hash",
        display_name="Primary",
        age=35,
        plan_id=3,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.side_effect = [primary_user, None]
    plan_repo = MagicMock(spec=PlanRepositoryPort)

    use_case = RemoveFamilyMemberUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(EntityNotFoundError, match="Member user 2 not found"):
        use_case.execute(primary_user_id=1, member_user_id=2)

    user_repo.save.assert_not_called()


def test_remove_family_member_not_belonging_to_primary_raises_permission_denied() -> (
    None
):
    primary_user = User(
        user_id=1,
        email="primary@test.com",
        password_hash="hash",
        display_name="Primary",
        age=35,
        plan_id=3,
    )
    unrelated_member = User(
        user_id=2,
        email="other@test.com",
        password_hash="hash",
        display_name="Other",
        age=20,
        plan_id=3,
        primary_account_id=99,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.side_effect = [primary_user, unrelated_member]
    plan_repo = MagicMock(spec=PlanRepositoryPort)

    use_case = RemoveFamilyMemberUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(
        PermissionDeniedError,
        match="This profile does not belong to your family account",
    ):
        use_case.execute(primary_user_id=1, member_user_id=2)

    user_repo.save.assert_not_called()


def test_remove_family_member_free_plan_missing_raises_error() -> None:
    primary_user = User(
        user_id=1,
        email="primary@test.com",
        password_hash="hash",
        display_name="Primary",
        age=35,
        plan_id=3,
    )
    member_user = User(
        user_id=2,
        email="dep@test.com",
        password_hash="hash",
        display_name="Dep",
        age=16,
        plan_id=3,
        primary_account_id=1,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.side_effect = [primary_user, member_user]
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_name.return_value = None

    use_case = RemoveFamilyMemberUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(EntityNotFoundError, match="Default Free plan not found"):
        use_case.execute(primary_user_id=1, member_user_id=2)

    user_repo.save.assert_not_called()


def test_remove_family_member_unlinks_and_reverts_to_free_plan() -> None:
    primary_user = User(
        user_id=1,
        email="primary@test.com",
        password_hash="hash",
        display_name="Primary",
        age=35,
        plan_id=3,
    )
    member_user = User(
        user_id=2,
        email="dep@test.com",
        password_hash="hash",
        display_name="Dep",
        age=16,
        plan_id=3,
        primary_account_id=1,
    )
    free_plan = Plan(
        plan_id=1,
        name=Plan.DEFAULT_FREE_PLAN_NAME,
        initial_monthly_price=0.0,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.side_effect = [primary_user, member_user]
    user_repo.save.side_effect = lambda u: u
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_name.return_value = free_plan

    use_case = RemoveFamilyMemberUseCase(user_repo=user_repo, plan_repo=plan_repo)
    updated_member = use_case.execute(primary_user_id=1, member_user_id=2)

    assert updated_member.primary_account_id is None
    assert updated_member.plan_id == 1
    user_repo.save.assert_called_once_with(member_user)
