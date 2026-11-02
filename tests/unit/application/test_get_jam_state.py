"""Unit tests for GetJamStateUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.use_cases.jam.get_jam_state import GetJamStateUseCase
from app.domain.exceptions import EntityNotFoundError
from app.domain.models import Jam, JamQueueItem, Track, User


def test_get_jam_state_batch_fetches_tracks() -> None:
    user = User(
        user_id=1,
        email="adult@test.com",
        password_hash="pw",
        display_name="Adult",
        age=20,
        plan_id=1,
    )
    jam = Jam(
        jam_id=10,
        host_user_id=1,
        room_name="Rock Jam",
        is_active=True,
        current_track_id=101,
    )
    q1 = JamQueueItem(jam_id=10, track_id=201, initial_vote_points=5)
    q2 = JamQueueItem(jam_id=10, track_id=202, initial_vote_points=3)

    t_current = Track(
        track_id=101,
        title="Current",
        artist="Artist",
        duration_seconds=200,
        genre="Rock",
    )
    t_q1 = Track(
        track_id=201,
        title="Q1",
        artist="Artist",
        duration_seconds=180,
        genre="Rock",
    )
    t_q2 = Track(
        track_id=202,
        title="Q2",
        artist="Artist",
        duration_seconds=220,
        genre="Rock",
        is_deleted=True,
    )

    user_repo = MagicMock()
    user_repo.find_by_id.return_value = user

    jam_repo = MagicMock()
    jam_repo.find_by_id.return_value = jam
    jam_repo.list_queue.return_value = [q1, q2]

    track_repo = MagicMock()
    track_repo.find_by_ids.return_value = {
        101: t_current,
        201: t_q1,
        202: t_q2,
    }

    use_case = GetJamStateUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=track_repo,
    )
    result = use_case.execute(jam_id=10, user_id=1)

    assert result.jam == jam
    assert result.current_track == t_current
    # q2 is deleted, so it should be omitted
    assert result.queue == [q1]

    # Batch query called once with all track IDs
    track_repo.find_by_ids.assert_called_once()
    called_ids = track_repo.find_by_ids.call_args[0][0]
    assert set(called_ids) == {101, 201, 202}
    track_repo.find_by_id.assert_not_called()


def test_get_jam_state_filters_explicit_tracks_for_minors() -> None:
    minor = User(
        user_id=2,
        email="minor@test.com",
        password_hash="pw",
        display_name="Minor",
        age=14,
        plan_id=1,
    )
    jam = Jam(
        jam_id=10,
        host_user_id=1,
        room_name="Family Jam",
        is_active=True,
        current_track_id=101,
    )
    q1 = JamQueueItem(jam_id=10, track_id=201, initial_vote_points=5)

    t_current = Track(
        track_id=101,
        title="Explicit Current",
        artist="Artist",
        duration_seconds=200,
        genre="Rap",
        explicit=True,
    )
    t_q1 = Track(
        track_id=201,
        title="Explicit Q1",
        artist="Artist",
        duration_seconds=180,
        genre="Rap",
        explicit=True,
    )

    user_repo = MagicMock()
    user_repo.find_by_id.return_value = minor

    jam_repo = MagicMock()
    jam_repo.find_by_id.return_value = jam
    jam_repo.list_queue.return_value = [q1]

    track_repo = MagicMock()
    track_repo.find_by_ids.return_value = {
        101: t_current,
        201: t_q1,
    }

    use_case = GetJamStateUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=track_repo,
    )
    result = use_case.execute(jam_id=10, user_id=2)

    assert result.current_track is None
    assert result.queue == []


def test_get_jam_state_user_not_found() -> None:
    user_repo = MagicMock()
    user_repo.find_by_id.return_value = None

    use_case = GetJamStateUseCase(
        jam_repo=MagicMock(),
        user_repo=user_repo,
        track_repo=MagicMock(),
    )
    with pytest.raises(EntityNotFoundError):
        use_case.execute(jam_id=1, user_id=999)


def test_get_jam_state_jam_not_found() -> None:
    user_repo = MagicMock()
    user_repo.find_by_id.return_value = MagicMock()

    jam_repo = MagicMock()
    jam_repo.find_by_id.return_value = None

    use_case = GetJamStateUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=MagicMock(),
    )
    with pytest.raises(EntityNotFoundError):
        use_case.execute(jam_id=999, user_id=1)
