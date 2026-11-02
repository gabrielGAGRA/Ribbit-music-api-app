"""Unit tests for VoteSkipJamTrackUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.jam_dtos import VoteSkipJamTrackCommand
from app.application.ports.repositories.jam_repository import JamRepositoryPort
from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.jam.vote_skip_jam_track import VoteSkipJamTrackUseCase
from app.domain.exceptions import BusinessRuleViolationError, EntityNotFoundError
from app.domain.models.jam import Jam, JamQueueItem
from app.domain.models.track import Track
from app.domain.models.user import User


def test_vote_skip_jam_track_decrements_points_and_saves() -> None:
    user = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="Frog",
        age=22,
        plan_id=1,
    )
    jam = Jam(jam_id=10, host_user_id=1, room_name="Jam", is_active=True)
    track = Track(
        track_id=100,
        title="Song",
        artist="Artist",
        duration_seconds=180,
        genre="Rock",
    )
    queue_item = JamQueueItem(jam_id=10, track_id=100, initial_vote_points=3)

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam
    jam_repo.find_queue_item.return_value = queue_item
    jam_repo.save_queue_item.side_effect = lambda item: item

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track

    use_case = VoteSkipJamTrackUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=track_repo,
    )
    command = VoteSkipJamTrackCommand(jam_id=10, track_id=100, user_id=1)

    result = use_case.execute(command)

    assert result is queue_item
    assert result.vote_points == 2
    jam_repo.save_queue_item.assert_called_once_with(queue_item)


def test_vote_skip_jam_track_not_in_queue_raises_entity_not_found() -> None:
    user = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="Frog",
        age=22,
        plan_id=1,
    )
    jam = Jam(jam_id=10, host_user_id=1, room_name="Jam", is_active=True)
    track = Track(
        track_id=100,
        title="Song",
        artist="Artist",
        duration_seconds=180,
        genre="Rock",
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam
    jam_repo.find_queue_item.return_value = None

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track

    use_case = VoteSkipJamTrackUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=track_repo,
    )
    command = VoteSkipJamTrackCommand(jam_id=10, track_id=100, user_id=1)

    with pytest.raises(EntityNotFoundError, match="not currently in the jam queue"):
        use_case.execute(command)


def test_vote_skip_jam_track_minor_on_explicit_track_raises_business_rule_error() -> (
    None
):
    minor = User(
        user_id=2,
        email="minor@ribbit.com",
        password_hash="pw",
        display_name="Tadpole",
        age=16,
        plan_id=1,
    )
    jam = Jam(jam_id=10, host_user_id=1, room_name="Jam", is_active=True)
    explicit_track = Track(
        track_id=100,
        title="Explicit",
        artist="Artist",
        duration_seconds=180,
        genre="Rap",
        explicit=True,
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = minor

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = explicit_track

    use_case = VoteSkipJamTrackUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=track_repo,
    )
    command = VoteSkipJamTrackCommand(jam_id=10, track_id=100, user_id=2)

    with pytest.raises(BusinessRuleViolationError, match="underage"):
        use_case.execute(command)


def test_vote_skip_jam_track_user_not_found_raises_entity_not_found() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None

    use_case = VoteSkipJamTrackUseCase(
        jam_repo=MagicMock(spec=JamRepositoryPort),
        user_repo=user_repo,
        track_repo=MagicMock(spec=TrackRepositoryPort),
    )
    command = VoteSkipJamTrackCommand(jam_id=10, track_id=100, user_id=999)

    with pytest.raises(EntityNotFoundError, match="User with ID 999 not found"):
        use_case.execute(command)


def test_vote_skip_jam_track_inactive_jam_raises_entity_not_found() -> None:
    user = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="Frog",
        age=22,
        plan_id=1,
    )
    inactive_jam = Jam(jam_id=10, host_user_id=1, room_name="Jam", is_active=False)

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = inactive_jam

    use_case = VoteSkipJamTrackUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=MagicMock(spec=TrackRepositoryPort),
    )
    command = VoteSkipJamTrackCommand(jam_id=10, track_id=100, user_id=1)

    with pytest.raises(EntityNotFoundError, match="Jam room not found or inactive"):
        use_case.execute(command)


def test_vote_skip_jam_track_deleted_track_raises_entity_not_found() -> None:
    user = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="Frog",
        age=22,
        plan_id=1,
    )
    jam = Jam(jam_id=10, host_user_id=1, room_name="Jam", is_active=True)
    deleted_track = Track(
        track_id=100,
        title="Deleted",
        artist="Artist",
        duration_seconds=180,
        genre="Rock",
        is_deleted=True,
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = deleted_track

    use_case = VoteSkipJamTrackUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=track_repo,
    )
    command = VoteSkipJamTrackCommand(jam_id=10, track_id=100, user_id=1)

    with pytest.raises(EntityNotFoundError, match="Track not found or inactive"):
        use_case.execute(command)
