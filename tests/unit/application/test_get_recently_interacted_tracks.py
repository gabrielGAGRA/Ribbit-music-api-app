"""Unit tests for GetRecentlyInteractedTracksUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.review.get_recently_interacted_tracks import (
    GetRecentlyInteractedTracksUseCase,
)
from app.domain.exceptions import EntityNotFoundError
from app.domain.models import Interaction, InteractionAction, Track, User


def test_get_recently_interacted_tracks_returns_paired_active_tracks() -> None:
    user = User(
        user_id=1,
        email="listener@ribbit.com",
        password_hash="pw",
        display_name="Listener",
        age=25,
        plan_id=1,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    inter_1 = Interaction(
        interaction_id=10,
        user_id=1,
        track_id=101,
        action=InteractionAction.LIKE,
    )
    inter_2 = Interaction(
        interaction_id=11,
        user_id=1,
        track_id=102,
        action=InteractionAction.DISLIKE,
    )
    inter_deleted = Interaction(
        interaction_id=12,
        user_id=1,
        track_id=103,
        action=InteractionAction.LIKE,
    )

    interaction_repo = MagicMock(spec=InteractionRepositoryPort)
    interaction_repo.list_by_user.return_value = [
        inter_1,
        inter_2,
        inter_deleted,
    ]

    track_1 = Track(
        track_id=101,
        title="Track 1",
        artist="Artist 1",
        duration_seconds=180,
        genre="Pop",
    )
    track_2 = Track(
        track_id=102,
        title="Track 2",
        artist="Artist 2",
        duration_seconds=200,
        genre="Rock",
    )
    track_deleted = Track(
        track_id=103,
        title="Deleted Track",
        artist="Artist 3",
        duration_seconds=200,
        genre="Rock",
        is_deleted=True,
    )

    track_map = {
        101: track_1,
        102: track_2,
        103: track_deleted,
    }
    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.side_effect = track_map.get

    use_case = GetRecentlyInteractedTracksUseCase(
        user_repo=user_repo,
        interaction_repo=interaction_repo,
        track_repo=track_repo,
    )
    results = use_case.execute(user_id=1, limit=20)

    assert len(results) == 2
    assert results[0].interaction == inter_1
    assert results[0].track == track_1
    assert results[1].interaction == inter_2
    assert results[1].track == track_2


def test_get_recently_interacted_tracks_user_not_found_raises_entity_not_found() -> (
    None
):
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None

    use_case = GetRecentlyInteractedTracksUseCase(
        user_repo=user_repo,
        interaction_repo=MagicMock(spec=InteractionRepositoryPort),
        track_repo=MagicMock(spec=TrackRepositoryPort),
    )

    with pytest.raises(EntityNotFoundError, match="User with ID 99 not found"):
        use_case.execute(user_id=99)
