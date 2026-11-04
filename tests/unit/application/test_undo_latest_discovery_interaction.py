"""Unit tests for undoing the latest discovery swipe."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
from app.application.ports.repositories.plan_repository import PlanRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.discovery.undo_latest_discovery_interaction import (
    UndoLatestDiscoveryInteractionUseCase,
)
from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError
from app.domain.models.interaction import Interaction, InteractionAction
from app.domain.models.plan import Plan
from app.domain.models.user import User


def _create_use_case(
    *,
    plan: Plan | None,
    interaction: Interaction | None,
) -> tuple[UndoLatestDiscoveryInteractionUseCase, InteractionRepositoryPort]:
    user = User(
        user_id=4,
        email="user@example.com",
        password_hash="hash",
        display_name="User",
        age=25,
        plan_id=plan.plan_id if plan and plan.plan_id is not None else 1,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    plan_repo.find_by_id.return_value = plan
    interaction_repo = MagicMock(spec=InteractionRepositoryPort)
    interaction_repo.delete_latest_discovery.return_value = interaction
    return (
        UndoLatestDiscoveryInteractionUseCase(
            user_repo=user_repo,
            plan_repo=plan_repo,
            interaction_repo=interaction_repo,
        ),
        interaction_repo,
    )


def test_undo_latest_discovery_interaction_returns_removed_swipe() -> None:
    interaction = Interaction(
        interaction_id=12,
        user_id=4,
        track_id=30,
        action=InteractionAction.DISLIKE,
        source="discovery",
    )
    paid_plan = Plan(plan_id=2, name="Individual", initial_monthly_price=14.90)
    use_case, repository = _create_use_case(plan=paid_plan, interaction=interaction)

    result = use_case.execute(user_id=4)

    assert result is interaction
    repository.delete_latest_discovery.assert_called_once_with(4)


def test_undo_latest_discovery_interaction_without_history_raises() -> None:
    paid_plan = Plan(plan_id=2, name="Individual", initial_monthly_price=14.90)
    use_case, _ = _create_use_case(plan=paid_plan, interaction=None)

    with pytest.raises(EntityNotFoundError, match="No discovery interaction"):
        use_case.execute(user_id=4)


def test_undo_latest_discovery_interaction_requires_paid_plan() -> None:
    free_plan = Plan(plan_id=1, name="Free", initial_monthly_price=0.0)
    use_case, repository = _create_use_case(plan=free_plan, interaction=None)

    with pytest.raises(PermissionDeniedError, match="exclusive to Premium"):
        use_case.execute(user_id=4)

    repository.delete_latest_discovery.assert_not_called()


def test_undo_latest_discovery_interaction_denies_missing_plan() -> None:
    use_case, repository = _create_use_case(plan=None, interaction=None)

    with pytest.raises(PermissionDeniedError, match="exclusive to Premium"):
        use_case.execute(user_id=4)

    repository.delete_latest_discovery.assert_not_called()
