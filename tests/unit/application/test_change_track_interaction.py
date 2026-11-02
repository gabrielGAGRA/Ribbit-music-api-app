"""Unit tests for ChangeTrackInteractionUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
from app.application.ports.repositories.plan_repository import PlanRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.user.change_track_interaction import (
    ChangeTrackInteractionUseCase,
)
from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError
from app.domain.models.interaction import Interaction, InteractionAction
from app.domain.models.plan import Plan
from app.domain.models.user import User


def test_change_track_interaction_user_not_found_raises_error() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    interaction_repo = MagicMock(spec=InteractionRepositoryPort)

    use_case = ChangeTrackInteractionUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        interaction_repo=interaction_repo,
    )

    with pytest.raises(EntityNotFoundError, match="User with ID 1 not found"):
        use_case.execute(user_id=1, track_id=10, new_action=InteractionAction.LIKE)

    interaction_repo.save.assert_not_called()


def test_change_track_interaction_free_plan_raises_permission_denied() -> None:
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
    interaction_repo = MagicMock(spec=InteractionRepositoryPort)

    use_case = ChangeTrackInteractionUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        interaction_repo=interaction_repo,
    )

    with pytest.raises(
        PermissionDeniedError, match="Feature exclusive to Premium subscribers"
    ):
        use_case.execute(user_id=1, track_id=10, new_action=InteractionAction.LIKE)

    interaction_repo.save.assert_not_called()


def test_change_track_interaction_missing_plan_raises_permission_denied() -> None:
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
    interaction_repo = MagicMock(spec=InteractionRepositoryPort)

    use_case = ChangeTrackInteractionUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        interaction_repo=interaction_repo,
    )

    with pytest.raises(
        PermissionDeniedError, match="Feature exclusive to Premium subscribers"
    ):
        use_case.execute(user_id=1, track_id=10, new_action=InteractionAction.LIKE)

    interaction_repo.save.assert_not_called()


def test_change_track_interaction_not_found_raises_error() -> None:
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
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = paid_plan
    interaction_repo = MagicMock(spec=InteractionRepositoryPort)
    interaction_repo.find_by_user_and_track.return_value = None

    use_case = ChangeTrackInteractionUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        interaction_repo=interaction_repo,
    )

    with pytest.raises(
        EntityNotFoundError, match="Interaction for this track was not found"
    ):
        use_case.execute(user_id=1, track_id=10, new_action=InteractionAction.LIKE)

    interaction_repo.save.assert_not_called()


def test_change_track_interaction_updates_and_saves_interaction() -> None:
    user = User(
        user_id=1,
        email="prem@test.com",
        password_hash="hash",
        display_name="PremUser",
        age=20,
        plan_id=2,
    )
    paid_plan = Plan(plan_id=2, name="Premium", initial_monthly_price=19.90)
    existing_interaction = Interaction(
        interaction_id=5,
        user_id=1,
        track_id=10,
        action=InteractionAction.DISLIKE,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = paid_plan
    interaction_repo = MagicMock(spec=InteractionRepositoryPort)
    interaction_repo.find_by_user_and_track.return_value = existing_interaction
    interaction_repo.save.side_effect = lambda i: i

    use_case = ChangeTrackInteractionUseCase(
        user_repo=user_repo,
        plan_repo=plan_repo,
        interaction_repo=interaction_repo,
    )
    result = use_case.execute(
        user_id=1, track_id=10, new_action=InteractionAction.SUPERLIKE
    )

    assert result.action == InteractionAction.SUPERLIKE
    interaction_repo.find_by_user_and_track.assert_called_once_with(1, 10)
    interaction_repo.save.assert_called_once_with(existing_interaction)
