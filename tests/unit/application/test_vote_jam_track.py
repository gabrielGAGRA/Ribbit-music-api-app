"""Unit tests for VoteJamTrackUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.jam_dtos import VoteJamTrackCommand
from app.application.ports.repositories.jam_repository import JamRepositoryPort
from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.jam.vote_jam_track import VoteJamTrackUseCase
from app.domain.exceptions import BusinessRuleViolationError, EntityNotFoundError
from app.domain.models.jam import Jam, JamQueueItem
from app.domain.models.track import Track
from app.domain.models.user import User


def test_vote_jam_track_adds_new_queue_item_when_not_in_queue() -> None:
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
        title="Hop",
        artist="Frog",
        duration_seconds=180,
        genre="Rock",
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam
    jam_repo.find_queue_item.return_value = None
    jam_repo.save_queue_item.side_effect = lambda item: item

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track

    use_case = VoteJamTrackUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=track_repo,
    )
    command = VoteJamTrackCommand(jam_id=10, track_id=100, user_id=1, points=2)

    result = use_case.execute(command)

    assert result.jam_id == 10
    assert result.track_id == 100
    assert result.vote_points == 2
    jam_repo.save_queue_item.assert_called_once_with(result)


def test_vote_jam_track_increments_existing_queue_item_points() -> None:
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
        title="Hop",
        artist="Frog",
        duration_seconds=180,
        genre="Rock",
    )
    existing_item = JamQueueItem(jam_id=10, track_id=100, initial_vote_points=3)

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam
    jam_repo.find_queue_item.return_value = existing_item
    jam_repo.save_queue_item.side_effect = lambda item: item

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track

    use_case = VoteJamTrackUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=track_repo,
    )
    command = VoteJamTrackCommand(jam_id=10, track_id=100, user_id=1, points=1)

    result = use_case.execute(command)

    assert result is existing_item
    assert result.vote_points == 4
    jam_repo.save_queue_item.assert_called_once_with(existing_item)


def test_vote_jam_track_minor_blocked_from_explicit_track_raises_business_rule_error() -> (
    None
):
    minor = User(
        user_id=2,
        email="minor@ribbit.com",
        password_hash="pw",
        display_name="Tadpole",
        age=15,
        plan_id=1,
    )
    jam = Jam(jam_id=10, host_user_id=1, room_name="Jam", is_active=True)
    explicit_track = Track(
        track_id=100,
        title="Explicit Song",
        artist="Artist",
        duration_seconds=200,
        genre="Rap",
        explicit=True,
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = minor

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = explicit_track

    use_case = VoteJamTrackUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=track_repo,
    )
    command = VoteJamTrackCommand(jam_id=10, track_id=100, user_id=2, points=1)

    with pytest.raises(BusinessRuleViolationError, match="underage"):
        use_case.execute(command)

    jam_repo.save_queue_item.assert_not_called()


def test_vote_jam_track_blocked_genre_raises_business_rule_error() -> None:
    user = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="Frog",
        age=25,
        plan_id=1,
        blocked_genres=frozenset({"metal"}),
    )
    jam = Jam(jam_id=10, host_user_id=1, room_name="Jam", is_active=True)
    metal_track = Track(
        track_id=100,
        title="Heavy Riff",
        artist="Band",
        duration_seconds=200,
        genre="Metal",
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = metal_track

    use_case = VoteJamTrackUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=track_repo,
    )
    command = VoteJamTrackCommand(jam_id=10, track_id=100, user_id=1, points=1)

    with pytest.raises(BusinessRuleViolationError, match="genre preferences"):
        use_case.execute(command)


def test_vote_jam_track_user_not_found_raises_entity_not_found() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None

    use_case = VoteJamTrackUseCase(
        jam_repo=MagicMock(spec=JamRepositoryPort),
        user_repo=user_repo,
        track_repo=MagicMock(spec=TrackRepositoryPort),
    )
    command = VoteJamTrackCommand(jam_id=10, track_id=100, user_id=999)

    with pytest.raises(EntityNotFoundError, match="User with ID 999 not found"):
        use_case.execute(command)


def test_vote_jam_track_inactive_or_missing_jam_raises_entity_not_found() -> None:
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

    use_case = VoteJamTrackUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=MagicMock(spec=TrackRepositoryPort),
    )
    command = VoteJamTrackCommand(jam_id=10, track_id=100, user_id=1)

    with pytest.raises(EntityNotFoundError, match="Jam room not found or inactive"):
        use_case.execute(command)


def test_vote_jam_track_deleted_track_raises_entity_not_found() -> None:
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
        genre="Pop",
        is_deleted=True,
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = deleted_track

    use_case = VoteJamTrackUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=track_repo,
    )
    command = VoteJamTrackCommand(jam_id=10, track_id=100, user_id=1)

    with pytest.raises(EntityNotFoundError, match="Track not found or inactive"):
        use_case.execute(command)


def test_vote_jam_track_superlike_limit_reached_raises_error() -> None:
    user = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="Frog",
        age=22,
        plan_id=1,
    )
    # Jam has max 2 superlikes, and 2 already used
    jam = Jam(
        jam_id=10,
        host_user_id=1,
        room_name="Jam",
        is_active=True,
        max_superlikes=2,
        superlikes_used=2,
    )
    track = Track(
        track_id=100, title="Song", artist="Artist", duration_seconds=180, genre="Pop"
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam
    jam_repo.is_participant.return_value = True

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track

    use_case = VoteJamTrackUseCase(
        jam_repo=jam_repo, user_repo=user_repo, track_repo=track_repo
    )
    command = VoteJamTrackCommand(
        jam_id=10, track_id=100, user_id=1, action="superlike"
    )

    with pytest.raises(BusinessRuleViolationError, match="Superlike limit reached"):
        use_case.execute(command)


def test_vote_jam_track_duration_cap_exceeded_raises_error() -> None:
    user = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="Frog",
        age=22,
        plan_id=1,
    )
    # Jam: 1 minute = 60s max. Track is 180s.
    jam = Jam(
        jam_id=10, host_user_id=1, room_name="Jam", is_active=True, duration_minutes=1
    )
    track = Track(
        track_id=100,
        title="Long Song",
        artist="Artist",
        duration_seconds=180,
        genre="Pop",
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam
    jam_repo.is_participant.return_value = True
    jam_repo.list_queue.return_value = []

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track

    use_case = VoteJamTrackUseCase(
        jam_repo=jam_repo, user_repo=user_repo, track_repo=track_repo
    )
    command = VoteJamTrackCommand(jam_id=10, track_id=100, user_id=1, points=1)

    with pytest.raises(BusinessRuleViolationError, match="duration"):
        use_case.execute(command)


def test_vote_jam_track_auto_advances_when_no_current_track() -> None:
    user = User(
        user_id=1,
        email="user@ribbit.com",
        password_hash="pw",
        display_name="Frog",
        age=22,
        plan_id=1,
    )
    jam = Jam(
        jam_id=10,
        host_user_id=1,
        room_name="Jam",
        is_active=True,
        current_track_id=None,
    )
    track = Track(
        track_id=100,
        title="First Song",
        artist="Artist",
        duration_seconds=180,
        genre="Pop",
    )
    queue_item = JamQueueItem(jam_id=10, track_id=100, initial_vote_points=1)

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam
    jam_repo.is_participant.return_value = True
    jam_repo.find_queue_item.return_value = None
    jam_repo.save_queue_item.return_value = queue_item
    jam_repo.list_queue.return_value = [queue_item]

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track

    use_case = VoteJamTrackUseCase(
        jam_repo=jam_repo, user_repo=user_repo, track_repo=track_repo
    )
    command = VoteJamTrackCommand(jam_id=10, track_id=100, user_id=1, points=1)

    result = use_case.execute(command)

    assert result.track_id == 100
    assert jam.current_track_id == 100
    jam_repo.remove_track_from_queue.assert_called_once_with(10, 100)
