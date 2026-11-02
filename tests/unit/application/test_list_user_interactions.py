"""Unit tests for ListUserInteractionsUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.user.list_user_interactions import (
    ListUserInteractionsUseCase,
)
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.interaction import Interaction, InteractionAction
from app.domain.models.user import User


def test_list_user_interactions_user_not_found_raises_error() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None
    interaction_repo = MagicMock(spec=InteractionRepositoryPort)

    use_case = ListUserInteractionsUseCase(
        user_repo=user_repo, interaction_repo=interaction_repo
    )

    with pytest.raises(EntityNotFoundError, match="User with ID 1 not found"):
        use_case.execute(user_id=1)

    interaction_repo.list_by_user.assert_not_called()


def test_list_user_interactions_without_filter_returns_all_interactions() -> None:
    user = User(
        user_id=1,
        email="user@test.com",
        password_hash="hash",
        display_name="User",
        age=21,
        plan_id=1,
    )
    interactions = [
        Interaction(
            interaction_id=1, user_id=1, track_id=10, action=InteractionAction.LIKE
        ),
        Interaction(
            interaction_id=2, user_id=1, track_id=11, action=InteractionAction.DISLIKE
        ),
    ]
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user
    interaction_repo = MagicMock(spec=InteractionRepositoryPort)
    interaction_repo.list_by_user.return_value = interactions

    use_case = ListUserInteractionsUseCase(
        user_repo=user_repo, interaction_repo=interaction_repo
    )
    result = use_case.execute(user_id=1)

    assert result == interactions
    interaction_repo.list_by_user.assert_called_once_with(1, action=None)


def test_list_user_interactions_with_action_filter_passes_action_to_repo() -> None:
    user = User(
        user_id=1,
        email="user@test.com",
        password_hash="hash",
        display_name="User",
        age=21,
        plan_id=1,
    )
    interactions = [
        Interaction(
            interaction_id=1, user_id=1, track_id=10, action=InteractionAction.SUPERLIKE
        ),
    ]
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user
    interaction_repo = MagicMock(spec=InteractionRepositoryPort)
    interaction_repo.list_by_user.return_value = interactions

    use_case = ListUserInteractionsUseCase(
        user_repo=user_repo, interaction_repo=interaction_repo
    )
    result = use_case.execute(user_id=1, action=InteractionAction.SUPERLIKE)

    assert result == interactions
    interaction_repo.list_by_user.assert_called_once_with(
        1, action=InteractionAction.SUPERLIKE
    )
