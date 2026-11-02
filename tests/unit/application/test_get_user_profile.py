"""Unit tests for GetUserProfileUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.user_dtos import UserProfileResult
from app.application.ports.repositories.plan_repository import PlanRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.user.get_user_profile import GetUserProfileUseCase
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.plan import Plan
from app.domain.models.user import User


def test_get_user_profile_user_not_found_raises_error() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None
    plan_repo = MagicMock(spec=PlanRepositoryPort)

    use_case = GetUserProfileUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(EntityNotFoundError, match="User with ID 10 not found"):
        use_case.execute(user_id=10)

    plan_repo.find_by_id.assert_not_called()


def test_get_user_profile_plan_not_found_raises_error() -> None:
    user = User(
        user_id=10,
        email="user@test.com",
        password_hash="hash",
        display_name="User",
        age=25,
        plan_id=99,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = None

    use_case = GetUserProfileUseCase(user_repo=user_repo, plan_repo=plan_repo)

    with pytest.raises(EntityNotFoundError, match="Plan with ID 99 not found"):
        use_case.execute(user_id=10)


def test_get_user_profile_returns_user_and_plan_result() -> None:
    user = User(
        user_id=10,
        email="user@test.com",
        password_hash="hash",
        display_name="User",
        age=25,
        plan_id=2,
    )
    plan = Plan(
        plan_id=2,
        name="Premium",
        initial_monthly_price=19.90,
        initial_max_profiles=1,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = plan

    use_case = GetUserProfileUseCase(user_repo=user_repo, plan_repo=plan_repo)
    result = use_case.execute(user_id=10)

    assert result == UserProfileResult(user=user, plan=plan)
    user_repo.find_by_id.assert_called_once_with(10)
    plan_repo.find_by_id.assert_called_once_with(2)


def test_get_user_profile_with_recent_interactions_returns_up_to_5() -> None:
    from app.application.ports.repositories.interaction_repository import (
        InteractionRepositoryPort,
    )
    from app.domain.models.interaction import Interaction, InteractionAction

    user = User(
        user_id=10,
        email="user@test.com",
        password_hash="hash",
        display_name="User",
        age=25,
        plan_id=2,
    )
    plan = Plan(
        plan_id=2,
        name="Premium",
        initial_monthly_price=19.90,
        initial_max_profiles=1,
    )
    interactions = [
        Interaction(
            interaction_id=i,
            user_id=10,
            track_id=100 + i,
            action=InteractionAction.LIKE,
        )
        for i in range(1, 10)
    ]

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = plan
    interaction_repo = MagicMock(spec=InteractionRepositoryPort)
    interaction_repo.list_by_user.return_value = interactions

    use_case = GetUserProfileUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        interaction_repo=interaction_repo,
    )
    result = use_case.execute(user_id=10)

    assert result.user == user
    assert result.plan == plan
    assert len(result.recent_interactions) == 5
    assert result["recent_interactions"] == interactions[:5]
    interaction_repo.list_by_user.assert_called_once_with(10)
