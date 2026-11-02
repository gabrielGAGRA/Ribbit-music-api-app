"""Unit tests for AdvanceJamPlaybackUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.jam_repository import JamRepositoryPort
from app.application.use_cases.jam.advance_jam_playback import (
    AdvanceJamPlaybackUseCase,
)
from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    PermissionDeniedError,
)
from app.domain.models import Jam, JamQueueItem


def test_advance_playback_success() -> None:
    jam = Jam(jam_id=1, host_user_id=10, room_name="Rock Room", is_active=True)
    expected_jam = Jam(
        jam_id=1,
        host_user_id=10,
        room_name="Rock Room",
        is_active=True,
        current_track_id=100,
    )
    queue_item = JamQueueItem(jam_id=1, track_id=100, initial_vote_points=5)

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam
    jam_repo.list_queue.return_value = [queue_item]
    jam_repo.advance_playback.return_value = expected_jam

    use_case = AdvanceJamPlaybackUseCase(jam_repo=jam_repo)
    result = use_case.execute(jam_id=1, requester_user_id=10)

    assert result == expected_jam
    jam_repo.advance_playback.assert_called_once_with(
        jam_id=1,
        new_track_id=100,
        removed_track_id=100,
    )


def test_advance_playback_inactive_or_not_found() -> None:
    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = None

    use_case = AdvanceJamPlaybackUseCase(jam_repo=jam_repo)
    with pytest.raises(EntityNotFoundError):
        use_case.execute(jam_id=1, requester_user_id=10)


def test_advance_playback_closed_jam_raises_entity_not_found() -> None:
    closed_jam = Jam(
        jam_id=1,
        host_user_id=10,
        room_name="Rock Room",
        is_active=False,
    )
    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = closed_jam

    use_case = AdvanceJamPlaybackUseCase(jam_repo=jam_repo)
    with pytest.raises(EntityNotFoundError, match="Jam room not found or inactive"):
        use_case.execute(jam_id=1, requester_user_id=10)


def test_advance_playback_non_host_forbidden() -> None:
    jam = Jam(jam_id=1, host_user_id=10, room_name="Rock Room", is_active=True)
    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam

    use_case = AdvanceJamPlaybackUseCase(jam_repo=jam_repo)
    with pytest.raises(PermissionDeniedError):
        use_case.execute(jam_id=1, requester_user_id=999)


def test_advance_playback_empty_queue() -> None:
    jam = Jam(jam_id=1, host_user_id=10, room_name="Rock Room", is_active=True)
    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam
    jam_repo.list_queue.return_value = []

    use_case = AdvanceJamPlaybackUseCase(jam_repo=jam_repo)
    with pytest.raises(BusinessRuleViolationError):
        use_case.execute(jam_id=1, requester_user_id=10)
