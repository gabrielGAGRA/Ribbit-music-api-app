"""Unit tests for ListUserInteractionsUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.user.list_user_interactions import (
    ListUserInteractionsUseCase,
)
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.interaction import Interaction, InteractionAction
from app.domain.models.track import Track
from app.domain.models.user import User


def test_list_user_interactions_user_not_found_raises_error() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None
    interaction_repo = MagicMock(spec=InteractionRepositoryPort)
    track_repo = MagicMock(spec=TrackRepositoryPort)

    use_case = ListUserInteractionsUseCase(
        user_repo=user_repo,
        interaction_repo=interaction_repo,
        track_repo=track_repo,
    )

    with pytest.raises(EntityNotFoundError, match="User with ID 1 not found"):
        use_case.execute(user_id=1)

    interaction_repo.list_by_user.assert_not_called()
    track_repo.find_by_ids.assert_not_called()


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
    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_ids.return_value = {
        10: Track(
            track_id=10,
            title="Track 10",
            artist="Artist 10",
            duration_seconds=180,
            genre="Pop",
        ),
        11: Track(
            track_id=11,
            title="Track 11",
            artist="Artist 11",
            duration_seconds=200,
            genre="Rock",
        ),
    }

    use_case = ListUserInteractionsUseCase(
        user_repo=user_repo,
        interaction_repo=interaction_repo,
        track_repo=track_repo,
    )
    result = use_case.execute(user_id=1)

    assert result == interactions
    interaction_repo.list_by_user.assert_called_once_with(1, action=None)
    track_repo.find_by_ids.assert_called_once_with([10, 11])


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
    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_ids.return_value = {
        10: Track(
            track_id=10,
            title="Track 10",
            artist="Artist 10",
            duration_seconds=180,
            genre="Pop",
        ),
    }

    use_case = ListUserInteractionsUseCase(
        user_repo=user_repo,
        interaction_repo=interaction_repo,
        track_repo=track_repo,
    )
    result = use_case.execute(user_id=1, action=InteractionAction.SUPERLIKE)

    assert result == interactions
    interaction_repo.list_by_user.assert_called_once_with(
        1, action=InteractionAction.SUPERLIKE
    )
    track_repo.find_by_ids.assert_called_once_with([10])


def test_list_user_interactions_filters_restricted_tracks_for_minor() -> None:
    minor_user = User(
        user_id=2,
        email="minor@test.com",
        password_hash="hash",
        display_name="Minor",
        age=15,
        plan_id=1,
    )
    interaction_allowed = Interaction(
        interaction_id=1, user_id=2, track_id=101, action=InteractionAction.LIKE
    )
    interaction_explicit = Interaction(
        interaction_id=2, user_id=2, track_id=102, action=InteractionAction.LIKE
    )
    interaction_deleted = Interaction(
        interaction_id=3, user_id=2, track_id=103, action=InteractionAction.DISLIKE
    )
    interactions = [interaction_allowed, interaction_explicit, interaction_deleted]

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = minor_user
    interaction_repo = MagicMock(spec=InteractionRepositoryPort)
    interaction_repo.list_by_user.return_value = interactions

    track_allowed = Track(
        track_id=101,
        title="Clean Track",
        artist="Clean Artist",
        duration_seconds=180,
        genre="Pop",
        explicit=False,
    )
    track_explicit = Track(
        track_id=102,
        title="Explicit Track",
        artist="Explicit Artist",
        duration_seconds=200,
        genre="Rock",
        explicit=True,
    )
    track_deleted = Track(
        track_id=103,
        title="Deleted Clean Track",
        artist="Artist",
        duration_seconds=200,
        genre="Pop",
        explicit=False,
        is_deleted=True,
    )

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_ids.return_value = {
        101: track_allowed,
        102: track_explicit,
        103: track_deleted,
    }

    use_case = ListUserInteractionsUseCase(
        user_repo=user_repo,
        interaction_repo=interaction_repo,
        track_repo=track_repo,
    )
    result = use_case.execute(user_id=2)

    assert result == [interaction_allowed]
    interaction_repo.list_by_user.assert_called_once_with(2, action=None)
    track_repo.find_by_ids.assert_called_once_with([101, 102, 103])
