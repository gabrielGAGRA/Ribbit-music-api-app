"""Unit tests for UpdateBlockedGenresUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.plan_repository import PlanRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.user.update_blocked_genres import (
    UpdateBlockedGenresUseCase,
)
from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError
from app.domain.models.plan import Plan
from app.domain.models.user import User


def test_update_blocked_genres_user_not_found_raises_error() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None
    plan_repo = MagicMock(spec=PlanRepositoryPort)

    use_case = UpdateBlockedGenresUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(EntityNotFoundError, match="User with ID 1 not found"):
        use_case.execute(user_id=1, blocked_genres=["rock"])

    user_repo.save.assert_not_called()


def test_update_blocked_genres_free_user_raises_permission_denied() -> None:
    user = User(
        user_id=1,
        email="free@test.com",
        password_hash="hash",
        display_name="FreeUser",
        age=20,
        plan_id=1,
    )
    free_plan = Plan(plan_id=1, name="Free", initial_monthly_price=0.0)
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = free_plan

    use_case = UpdateBlockedGenresUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(
        PermissionDeniedError, match="Feature exclusive to Premium subscribers"
    ):
        use_case.execute(user_id=1, blocked_genres=["rock"])

    user_repo.save.assert_not_called()


def test_update_blocked_genres_missing_plan_raises_permission_denied() -> None:
    user = User(
        user_id=1,
        email="user@test.com",
        password_hash="hash",
        display_name="User",
        age=20,
        plan_id=99,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = None

    use_case = UpdateBlockedGenresUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(
        PermissionDeniedError, match="Feature exclusive to Premium subscribers"
    ):
        use_case.execute(user_id=1, blocked_genres=["rock"])

    user_repo.save.assert_not_called()


def test_update_blocked_genres_premium_user_normalizes_and_saves() -> None:
    user = User(
        user_id=1,
        email="prem@test.com",
        password_hash="hash",
        display_name="PremUser",
        age=20,
        plan_id=2,
    )
    paid_plan = Plan(plan_id=2, name="Premium", initial_monthly_price=19.90)
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user
    user_repo.save.side_effect = lambda u: u
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = paid_plan

    use_case = UpdateBlockedGenresUseCase(user_repo=user_repo, plan_repo=plan_repo)
    updated_user = use_case.execute(
        user_id=1, blocked_genres=["  Heavy Metal ", "COUNTRY", ""]
    )

    assert updated_user.blocked_genres == frozenset({"heavy metal", "country"})
    user_repo.save.assert_called_once_with(user)


def test_update_blocked_genres_for_dependent_saves_only_linked_dependent() -> None:
    primary = User(
        user_id=1,
        email="primary@test.com",
        password_hash="hash",
        display_name="Primary",
        age=35,
        plan_id=2,
    )
    dependent = User(
        user_id=2,
        email="dependent@test.com",
        password_hash="hash",
        display_name="Dependent",
        age=14,
        plan_id=2,
        primary_account_id=1,
    )
    family_plan = Plan(
        plan_id=2,
        name="Family",
        initial_monthly_price=19.90,
        initial_max_profiles=4,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.side_effect = {1: primary, 2: dependent}.get
    user_repo.save.side_effect = lambda user: user
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = family_plan

    use_case = UpdateBlockedGenresUseCase(user_repo=user_repo, plan_repo=plan_repo)
    updated = use_case.execute_for_dependent(
        primary_user_id=1,
        dependent_user_id=2,
        blocked_genres=["  metal ", "rock"],
    )

    assert updated is dependent
    assert dependent.blocked_genres == frozenset({"metal", "rock"})
    user_repo.save.assert_called_once_with(dependent)


def test_update_blocked_genres_for_dependent_rejects_unlinked_profile() -> None:
    primary = User(
        user_id=1,
        email="primary@test.com",
        password_hash="hash",
        display_name="Primary",
        age=35,
        plan_id=2,
    )
    other_user = User(
        user_id=2,
        email="other@test.com",
        password_hash="hash",
        display_name="Other",
        age=14,
        plan_id=2,
    )
    family_plan = Plan(
        plan_id=2,
        name="Family",
        initial_monthly_price=19.90,
        initial_max_profiles=4,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.side_effect = {1: primary, 2: other_user}.get
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = family_plan

    use_case = UpdateBlockedGenresUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(PermissionDeniedError, match="does not belong"):
        use_case.execute_for_dependent(
            primary_user_id=1,
            dependent_user_id=2,
            blocked_genres=["rock"],
        )

    user_repo.save.assert_not_called()


def test_update_blocked_genres_for_dependent_requires_family_plan() -> None:
    primary = User(
        user_id=1,
        email="primary@test.com",
        password_hash="hash",
        display_name="Primary",
        age=35,
        plan_id=2,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = primary
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = Plan(
        plan_id=2,
        name="Premium",
        initial_monthly_price=19.90,
        initial_max_profiles=1,
    )

    use_case = UpdateBlockedGenresUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(PermissionDeniedError, match="does not support family"):
        use_case.execute_for_dependent(
            primary_user_id=1,
            dependent_user_id=2,
            blocked_genres=["rock"],
        )

    user_repo.save.assert_not_called()


def test_update_blocked_genres_for_dependent_rejects_dependent_as_primary() -> None:
    dependent = User(
        user_id=1,
        email="dependent@test.com",
        password_hash="hash",
        display_name="Dependent",
        age=14,
        plan_id=2,
        primary_account_id=9,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = dependent
    plan_repo = MagicMock(spec=PlanRepositoryPort)

    use_case = UpdateBlockedGenresUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(PermissionDeniedError, match="cannot manage family"):
        use_case.execute_for_dependent(
            primary_user_id=1,
            dependent_user_id=2,
            blocked_genres=["rock"],
        )

    plan_repo.find_by_id.assert_not_called()
    user_repo.save.assert_not_called()


def test_update_blocked_genres_allows_admin_on_free_plan_for_self_and_dependent() -> (
    None
):
    admin = User(
        user_id=1,
        email="admin@test.com",
        password_hash="hash",
        display_name="Admin",
        age=30,
        plan_id=1,
        is_admin=True,
    )
    dependent = User(
        user_id=2,
        email="dependent@test.com",
        password_hash="hash",
        display_name="Dependent",
        age=14,
        plan_id=3,
        primary_account_id=1,
    )
    free_plan = Plan(plan_id=1, name="Free", initial_monthly_price=0.0)
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.side_effect = {1: admin, 2: dependent}.get
    user_repo.save.side_effect = lambda user: user
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = free_plan

    use_case = UpdateBlockedGenresUseCase(user_repo=user_repo, plan_repo=plan_repo)
    updated_admin = use_case.execute(user_id=1, blocked_genres=["  Pop "])
    updated_dep = use_case.execute_for_dependent(
        primary_user_id=1,
        dependent_user_id=2,
        blocked_genres=["Funk"],
    )

    assert updated_admin.blocked_genres == frozenset({"pop"})
    assert updated_dep.blocked_genres == frozenset({"funk"})
