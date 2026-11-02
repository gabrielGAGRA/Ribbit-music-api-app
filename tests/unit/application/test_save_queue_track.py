"""Unit tests for SaveQueueTrackUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.jam_dtos import SaveQueueTrackCommand
from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
from app.application.ports.repositories.jam_repository import JamRepositoryPort
from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.jam.save_queue_track import SaveQueueTrackUseCase
from app.domain.exceptions import EntityNotFoundError
from app.domain.models import (
    InteractionAction,
    Jam,
    JamQueueItem,
    Playlist,
    Track,
    User,
)


def test_save_queue_track_saves_to_liked_and_adds_to_playlist() -> None:
    user = User(
        user_id=1,
        email="participant@ribbit.com",
        password_hash="pw",
        display_name="Participant",
        age=25,
        plan_id=1,
    )
    jam = Jam(jam_id=10, host_user_id=2, room_name="Jam", is_active=True)
    q_item = JamQueueItem(jam_id=10, track_id=50, initial_vote_points=1)
    track = Track(
        track_id=50,
        title="Cool Track",
        artist="Artist",
        duration_seconds=180,
        genre="Pop",
    )
    playlist = Playlist(playlist_id=20, user_id=1, name="My Jam Saves")

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam
    jam_repo.is_participant.return_value = True
    jam_repo.list_queue.return_value = [q_item]

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track

    interaction_repo = MagicMock(spec=InteractionRepositoryPort)
    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.find_by_id.return_value = playlist

    use_case = SaveQueueTrackUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=track_repo,
        interaction_repo=interaction_repo,
        playlist_repo=playlist_repo,
    )
    cmd = SaveQueueTrackCommand(jam_id=10, user_id=1, track_id=50, playlist_id=20)
    result = use_case.execute(cmd)

    assert result is True
    interaction_repo.save.assert_called_once()
    saved_interaction = interaction_repo.save.call_args[0][0]
    assert saved_interaction.user_id == 1
    assert saved_interaction.track_id == 50
    assert saved_interaction.action == InteractionAction.SUPERLIKE
    playlist_repo.save.assert_called_once()


def test_save_queue_track_not_in_queue_raises_entity_not_found() -> None:
    user = User(
        user_id=1,
        email="participant@ribbit.com",
        password_hash="pw",
        display_name="Participant",
        age=25,
        plan_id=1,
    )
    jam = Jam(jam_id=10, host_user_id=2, room_name="Jam", is_active=True)

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam
    jam_repo.is_participant.return_value = True
    jam_repo.list_queue.return_value = []

    use_case = SaveQueueTrackUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=MagicMock(spec=TrackRepositoryPort),
        interaction_repo=MagicMock(spec=InteractionRepositoryPort),
    )
    with pytest.raises(
        EntityNotFoundError, match="Track does not belong to this Jam room queue"
    ):
        use_case.execute(SaveQueueTrackCommand(jam_id=10, user_id=1, track_id=999))
