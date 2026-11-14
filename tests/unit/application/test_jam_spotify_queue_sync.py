"""Unit tests for Pond (Jam) integration with SpotifyHostQueuePort."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.jam_dtos import (
    VoteJamTrackCommand,
    VoteSkipJamTrackCommand,
)
from app.application.ports.repositories.jam_repository import JamRepositoryPort
from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.ports.services.spotify import SpotifyHostQueuePort
from app.application.use_cases.jam.advance_jam_playback import (
    AdvanceJamPlaybackUseCase,
)
from app.application.use_cases.jam.vote_jam_track import VoteJamTrackUseCase
from app.application.use_cases.jam.vote_skip_jam_track import (
    VoteSkipJamTrackUseCase,
)
from app.domain.exceptions import SpotifyError, SpotifyPremiumRequiredError
from app.domain.models.jam import Jam, JamQueueItem
from app.domain.models.track import Track
from app.domain.models.user import User


def _user(user_id: int, *, with_tokens: bool = False) -> User:
    return User(
        user_id=user_id,
        email=f"u{user_id}@test.com",
        password_hash="pw",
        display_name=f"User {user_id}",
        age=25,
        plan_id=1,
        spotify_id=f"sp_{user_id}",
        spotify_premium=True,
        spotify_refresh_token=f"ref_{user_id}" if with_tokens else None,
    )


def _track(track_id: int, spotify_id: str | None = "sp_track_1") -> Track:
    return Track(
        track_id=track_id,
        title="Track One",
        artist="Artist",
        album="Album",
        duration_seconds=180,
        genre="Pop",
        spotify_id=spotify_id,
    )


def test_vote_jam_track_enqueues_new_track_for_pond_owner_only_once() -> None:
    host = _user(1, with_tokens=True)
    guest = _user(2, with_tokens=False)
    jam = Jam(jam_id=10, host_user_id=1, room_code="123456", room_name="Pond")
    track = _track(50, "4uLU6hMCjMI75M1A2tKUQC")

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam
    jam_repo.is_participant.return_value = True
    jam_repo.list_queue.return_value = []
    jam_repo.find_queue_item.side_effect = [
        None,
        JamQueueItem(jam_id=10, track_id=50, initial_vote_points=1),
    ]
    jam_repo.save_queue_item.side_effect = lambda item: item

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.side_effect = lambda uid: host if uid == 1 else guest

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track

    spotify_queue = MagicMock(spec=SpotifyHostQueuePort)
    use_case = VoteJamTrackUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=track_repo,
        spotify_queue=spotify_queue,
    )

    use_case.execute(
        VoteJamTrackCommand(jam_id=10, user_id=2, track_id=50, action="like")
    )
    use_case.execute(
        VoteJamTrackCommand(jam_id=10, user_id=2, track_id=50, action="like")
    )

    spotify_queue.enqueue_track.assert_called_once_with(
        host, "spotify:track:4uLU6hMCjMI75M1A2tKUQC"
    )


def test_vote_jam_track_falls_back_gracefully_on_non_premium_spotify_error() -> None:
    host = _user(1, with_tokens=True)
    jam = Jam(jam_id=10, host_user_id=1, room_code="123456", room_name="Pond")
    track = _track(50, "abc")

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam
    jam_repo.is_participant.return_value = True
    jam_repo.list_queue.return_value = []
    jam_repo.find_queue_item.return_value = None
    jam_repo.save_queue_item.side_effect = lambda item: item

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = host

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track

    spotify_queue = MagicMock(spec=SpotifyHostQueuePort)
    spotify_queue.enqueue_track.side_effect = SpotifyError("No active device")

    use_case = VoteJamTrackUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=track_repo,
        spotify_queue=spotify_queue,
    )

    item = use_case.execute(
        VoteJamTrackCommand(jam_id=10, user_id=1, track_id=50, action="like")
    )
    assert item.track_id == 50
    assert host.spotify_premium is True


def test_vote_jam_track_downgrades_host_on_spotify_premium_required() -> None:
    host = _user(1, with_tokens=True)
    jam = Jam(jam_id=10, host_user_id=1, room_code="123456", room_name="Pond")
    track = _track(50, "abc")

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam
    jam_repo.is_participant.return_value = True
    jam_repo.list_queue.return_value = []
    jam_repo.find_queue_item.return_value = None
    jam_repo.save_queue_item.side_effect = lambda item: item

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = host
    user_repo.save.side_effect = lambda u: u

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track

    spotify_queue = MagicMock(spec=SpotifyHostQueuePort)
    spotify_queue.enqueue_track.side_effect = SpotifyPremiumRequiredError()

    use_case = VoteJamTrackUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=track_repo,
        spotify_queue=spotify_queue,
    )

    with pytest.raises(SpotifyPremiumRequiredError):
        use_case.execute(
            VoteJamTrackCommand(jam_id=10, user_id=1, track_id=50, action="like")
        )

    assert host.spotify_premium is False
    user_repo.save.assert_called_once_with(host)


def test_advance_and_skip_threshold_sync_to_spotify_owner() -> None:
    host = _user(1, with_tokens=True)
    jam = Jam(
        jam_id=10,
        host_user_id=1,
        room_code="123456",
        room_name="Pond",
        current_track_id=50,
        skip_votes_threshold=1,
    )
    next_track = _track(51, "next_sp_id")
    queue_item = JamQueueItem(jam_id=10, track_id=51, initial_vote_points=3)

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam
    jam_repo.is_participant.return_value = True
    jam_repo.list_queue.return_value = [queue_item]
    jam_repo.count_skip_votes.return_value = 1
    jam_repo.save.side_effect = lambda j: j
    del jam_repo.advance_playback

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = host

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = next_track

    spotify_queue = MagicMock(spec=SpotifyHostQueuePort)

    advance_uc = AdvanceJamPlaybackUseCase(
        jam_repo=jam_repo,
        track_repo=track_repo,
        user_repo=user_repo,
        spotify_queue=spotify_queue,
    )
    advance_uc.execute(jam_id=10, requester_user_id=1)

    skip_uc = VoteSkipJamTrackUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=track_repo,
        spotify_queue=spotify_queue,
    )
    skip_uc.execute(VoteSkipJamTrackCommand(jam_id=10, user_id=1, track_id=51))

    assert spotify_queue.start_track.call_count == 2
    spotify_queue.start_track.assert_called_with(host, "spotify:track:next_sp_id")
