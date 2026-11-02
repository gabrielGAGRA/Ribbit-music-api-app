"""Unit tests for jams router functions."""

from unittest.mock import MagicMock

from app.application.dtos import (
    CreateJamCommand,
    VoteJamTrackCommand,
    VoteSkipJamTrackCommand,
)
from app.application.use_cases.jam import (
    AdvanceJamPlaybackUseCase,
    CreateJamUseCase,
    GetJamStateUseCase,
    JoinJamUseCase,
    VoteJamTrackUseCase,
    VoteSkipJamTrackUseCase,
)
from app.domain.models import Jam, JamQueueItem, Track
from app.presentation.routers.jams import (
    advance_jam_playback,
    create_jam,
    get_jam_state,
    join_jam,
    skip_jam_track,
    vote_jam_track,
)
from app.presentation.schemas import (
    CreateJamRequest,
    JoinJamRequest,
    SkipJamTrackRequest,
    VoteJamTrackRequest,
)


def test_create_jam_forwards_command_and_returns_jam_response() -> None:
    mock_use_case = MagicMock(spec=CreateJamUseCase)
    jam = Jam(
        jam_id=1,
        host_user_id=10,
        room_name="Swamp Party",
        room_code="JAM-ABC123",
        is_active=True,
    )
    mock_use_case.execute.return_value = jam
    req = CreateJamRequest(host_user_id=10, room_name="Swamp Party")

    res = create_jam(req=req, use_case=mock_use_case)

    assert res.jam_id == 1
    assert res.host_user_id == 10
    assert res.room_name == "Swamp Party"
    assert res.room_code == "JAM-ABC123"
    assert res.is_active is True
    mock_use_case.execute.assert_called_once_with(
        CreateJamCommand(
            host_user_id=10,
            room_name="Swamp Party",
        )
    )


def test_join_jam_forwards_room_code_and_returns_jam_response() -> None:
    mock_use_case = MagicMock(spec=JoinJamUseCase)
    jam = Jam(
        jam_id=2,
        host_user_id=10,
        room_name="Swamp Party",
        room_code="JAM-XYZ789",
        is_active=True,
    )
    mock_use_case.execute.return_value = jam
    req = JoinJamRequest(room_code="JAM-XYZ789")

    res = join_jam(req=req, use_case=mock_use_case)

    assert res.jam_id == 2
    assert res.room_code == "JAM-XYZ789"
    mock_use_case.execute.assert_called_once_with(room_code="JAM-XYZ789")


def test_get_jam_state_returns_composite_jam_state_response() -> None:
    mock_use_case = MagicMock(spec=GetJamStateUseCase)
    jam = Jam(
        jam_id=3,
        host_user_id=10,
        room_name="Chill Pond",
        room_code="JAM-111222",
        is_active=True,
        current_track_id=50,
    )
    current_track = Track(
        track_id=50,
        title="Night Croak",
        artist="Bullfrog",
        duration_seconds=200,
        genre="lo-fi",
    )
    queue_item = JamQueueItem(
        jam_queue_id=9,
        jam_id=3,
        track_id=51,
        initial_vote_points=4,
    )
    mock_use_case.execute.return_value = {
        "jam": jam,
        "current_track": current_track,
        "queue": [queue_item],
    }

    res = get_jam_state(jam_id=3, user_id=10, use_case=mock_use_case)

    assert res.jam.jam_id == 3
    assert res.current_track is not None
    assert res.current_track.track_id == 50
    assert len(res.queue) == 1
    assert res.queue[0].track_id == 51
    assert res.queue[0].vote_points == 4
    mock_use_case.execute.assert_called_once_with(jam_id=3, user_id=10)


def test_vote_jam_track_forwards_command_and_returns_queue_item() -> None:
    mock_use_case = MagicMock(spec=VoteJamTrackUseCase)
    queue_item = JamQueueItem(
        jam_queue_id=12,
        jam_id=3,
        track_id=51,
        initial_vote_points=5,
    )
    mock_use_case.execute.return_value = queue_item
    req = VoteJamTrackRequest(user_id=15, track_id=51, points=3)

    res = vote_jam_track(jam_id=3, req=req, use_case=mock_use_case)

    assert res.jam_queue_id == 12
    assert res.jam_id == 3
    assert res.track_id == 51
    assert res.vote_points == 5
    mock_use_case.execute.assert_called_once_with(
        VoteJamTrackCommand(
            jam_id=3,
            track_id=51,
            user_id=15,
            points=3,
        )
    )


def test_skip_jam_track_forwards_command_and_returns_success() -> None:
    mock_use_case = MagicMock(spec=VoteSkipJamTrackUseCase)
    req = SkipJamTrackRequest(user_id=15, track_id=50)

    res = skip_jam_track(jam_id=3, req=req, use_case=mock_use_case)

    assert res.success is True
    mock_use_case.execute.assert_called_once_with(
        VoteSkipJamTrackCommand(
            jam_id=3,
            track_id=50,
            user_id=15,
        )
    )


def test_advance_jam_playback_forwards_ids_and_returns_jam_response() -> None:
    mock_use_case = MagicMock(spec=AdvanceJamPlaybackUseCase)
    jam = Jam(
        jam_id=3,
        host_user_id=10,
        room_name="Chill Pond",
        room_code="JAM-111222",
        is_active=True,
        current_track_id=51,
    )
    mock_use_case.execute.return_value = jam

    res = advance_jam_playback(
        jam_id=3,
        requester_user_id=10,
        use_case=mock_use_case,
    )

    assert res.jam_id == 3
    assert res.current_track_id == 51
    mock_use_case.execute.assert_called_once_with(
        jam_id=3,
        requester_user_id=10,
    )


def test_get_jam_deck_endpoint() -> None:
    from app.application.dtos.jam_dtos import GetJamDeckCommand
    from app.application.dtos.playlist_dtos import PlaylistDeckResult
    from app.application.use_cases.jam import GetJamDeckUseCase
    from app.presentation.routers.jams import get_jam_deck

    mock_use_case = MagicMock(spec=GetJamDeckUseCase)
    t = Track(
        track_id=10,
        title="Jam Track",
        artist="Artist",
        duration_seconds=180,
        genre="Rock",
    )
    mock_use_case.execute.return_value = PlaylistDeckResult(
        items=[t], next_cursor=None, has_more=False
    )

    res = get_jam_deck(jam_id=3, current_user_id=10, limit=10, use_case=mock_use_case)

    assert len(res.items) == 1
    assert res.items[0].track_id == 10
    mock_use_case.execute.assert_called_once_with(
        GetJamDeckCommand(jam_id=3, user_id=10, limit=10, cursor_id=None)
    )


def test_save_queue_track_endpoint() -> None:
    from app.application.dtos.jam_dtos import SaveQueueTrackCommand
    from app.application.use_cases.jam import SaveQueueTrackUseCase
    from app.presentation.routers.jams import save_queue_track
    from app.presentation.schemas.jams import SaveQueueTrackRequest

    mock_use_case = MagicMock(spec=SaveQueueTrackUseCase)
    mock_use_case.execute.return_value = True

    req = SaveQueueTrackRequest(track_id=50, playlist_id=20)
    res = save_queue_track(
        jam_id=3, req=req, current_user_id=10, use_case=mock_use_case
    )

    assert res.success is True
    mock_use_case.execute.assert_called_once_with(
        SaveQueueTrackCommand(jam_id=3, user_id=10, track_id=50, playlist_id=20)
    )


def test_close_jam_endpoint() -> None:
    from app.application.dtos.jam_dtos import CloseJamCommand
    from app.application.use_cases.jam import CloseJamUseCase
    from app.presentation.routers.jams import close_jam

    mock_use_case = MagicMock(spec=CloseJamUseCase)
    closed_jam = Jam(
        jam_id=3,
        host_user_id=10,
        room_name="Closed",
        room_code="123456",
        is_active=False,
    )
    mock_use_case.execute.return_value = closed_jam

    res = close_jam(jam_id=3, current_user_id=10, use_case=mock_use_case)

    assert res.jam_id == 3
    assert res.is_active is False
    mock_use_case.execute.assert_called_once_with(
        CloseJamCommand(jam_id=3, host_user_id=10)
    )
