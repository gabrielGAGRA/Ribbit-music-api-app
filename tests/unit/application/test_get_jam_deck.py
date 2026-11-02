"""Unit tests for GetJamDeckUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.jam_dtos import GetJamDeckCommand
from app.application.ports.repositories.jam_repository import JamRepositoryPort
from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.jam.get_jam_deck import GetJamDeckUseCase
from app.domain.exceptions import PermissionDeniedError
from app.domain.models import Jam, JamQueueItem, Playlist, Track, User


def test_get_jam_deck_for_participant_returns_candidates() -> None:
    user = User(
        user_id=1,
        email="participant@ribbit.com",
        password_hash="pw",
        display_name="Participant",
        age=25,
        plan_id=1,
    )
    jam = Jam(
        jam_id=10,
        host_user_id=2,
        room_name="Party",
        is_active=True,
        deck_source="livre",
    )
    t1 = Track(
        track_id=100, title="T1", artist="Artist", duration_seconds=180, genre="Rock"
    )
    t2 = Track(
        track_id=200, title="T2", artist="Artist", duration_seconds=200, genre="Pop"
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam
    jam_repo.is_participant.return_value = True
    jam_repo.list_queue.return_value = []

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.list_active.return_value = [t1, t2]

    use_case = GetJamDeckUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=track_repo,
    )
    result = use_case.execute(GetJamDeckCommand(jam_id=10, user_id=1, limit=10))

    assert [t.track_id for t in result.items] == [100, 200]
    assert result.has_more is False


def test_get_jam_deck_excludes_queue_and_current_track() -> None:
    user = User(
        user_id=1,
        email="participant@ribbit.com",
        password_hash="pw",
        display_name="Participant",
        age=25,
        plan_id=1,
    )
    jam = Jam(
        jam_id=10,
        host_user_id=2,
        room_name="Party",
        is_active=True,
        deck_source="livre",
        current_track_id=100,
    )
    q_item = JamQueueItem(jam_id=10, track_id=200, initial_vote_points=1)
    t1 = Track(
        track_id=100,
        title="Current",
        artist="Artist",
        duration_seconds=180,
        genre="Rock",
    )
    t2 = Track(
        track_id=200, title="Queued", artist="Artist", duration_seconds=200, genre="Pop"
    )
    t3 = Track(
        track_id=300,
        title="Available",
        artist="Artist",
        duration_seconds=220,
        genre="Rock",
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam
    jam_repo.is_participant.return_value = True
    jam_repo.list_queue.return_value = [q_item]

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.list_active.return_value = [t1, t2, t3]

    use_case = GetJamDeckUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=track_repo,
    )
    result = use_case.execute(jam_id=10, user_id=1)

    assert [t.track_id for t in result.items] == [300]


def test_get_jam_deck_non_participant_raises_permission_denied() -> None:
    user = User(
        user_id=5,
        email="outsider@ribbit.com",
        password_hash="pw",
        display_name="Outsider",
        age=25,
        plan_id=1,
    )
    jam = Jam(jam_id=10, host_user_id=2, room_name="Private", is_active=True)

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam
    jam_repo.is_participant.return_value = False

    use_case = GetJamDeckUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=MagicMock(spec=TrackRepositoryPort),
    )
    with pytest.raises(PermissionDeniedError, match="must join"):
        use_case.execute(jam_id=10, user_id=5)


def test_get_jam_deck_playlist_source_pulls_from_configured_playlist() -> None:
    user = User(
        user_id=1,
        email="host@ribbit.com",
        password_hash="pw",
        display_name="Host",
        age=25,
        plan_id=1,
    )
    t1 = Track(
        track_id=1, title="Song 1", artist="Artist", duration_seconds=180, genre="Rock"
    )
    playlist = Playlist(
        playlist_id=99, user_id=1, name="Source Playlist", initial_tracks=[t1]
    )
    jam = Jam(
        jam_id=10,
        host_user_id=1,
        room_name="Party",
        is_active=True,
        deck_source="playlist",
        source_playlist_id=99,
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam
    jam_repo.is_participant.return_value = True
    jam_repo.list_queue.return_value = []

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.find_by_id.return_value = playlist

    use_case = GetJamDeckUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=MagicMock(spec=TrackRepositoryPort),
        playlist_repo=playlist_repo,
    )
    result = use_case.execute(jam_id=10, user_id=1)

    assert [t.track_id for t in result.items] == [1]
