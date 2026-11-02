"""Unit tests for ListBlockedGenresUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.user.list_blocked_genres import ListBlockedGenresUseCase
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.user import User


def test_list_blocked_genres_user_not_found_raises_error() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None

    use_case = ListBlockedGenresUseCase(user_repo=user_repo)

    with pytest.raises(EntityNotFoundError, match="User with ID 1 not found"):
        use_case.execute(user_id=1)


def test_list_blocked_genres_returns_sorted_normalized_genres() -> None:
    user = User(
        user_id=1,
        email="user@test.com",
        password_hash="hash",
        display_name="User",
        age=20,
        plan_id=2,
        blocked_genres=frozenset({"Rock", "Jazz", "Electronic"}),
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    use_case = ListBlockedGenresUseCase(user_repo=user_repo)
    result = use_case.execute(user_id=1)

    assert result == ["electronic", "jazz", "rock"]
    user_repo.find_by_id.assert_called_once_with(1)


def test_list_blocked_genres_free_plan_raises_business_rule_violation() -> None:
    from app.application.ports.repositories.plan_repository import PlanRepositoryPort
    from app.domain.exceptions import BusinessRuleViolationError
    from app.domain.models.plan import Plan

    user = User(
        user_id=1,
        email="free@test.com",
        password_hash="hash",
        display_name="User",
        age=20,
        plan_id=1,
    )
    free_plan = Plan(plan_id=1, name="Free", initial_monthly_price=0.0)

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = free_plan

    use_case = ListBlockedGenresUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(BusinessRuleViolationError):
        use_case.execute(user_id=1)
