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
