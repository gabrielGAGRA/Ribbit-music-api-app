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
from app.domain.models import (
    Interaction,
    InteractionAction,
    Jam,
    JamQueueItem,
    Playlist,
    Track,
    User,
)


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

    track_repo.find_by_ids.return_value = {200: t2, 300: t3}

    use_case = GetJamDeckUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=track_repo,
    )
    result = use_case.execute(jam_id=10, user_id=1)

    assert [t.track_id for t in result.items] == [200, 300]


def test_get_jam_deck_excludes_tracks_already_interacted_by_user() -> None:
    user = User(
        user_id=1,
        email="participant@ribbit.com",
        password_hash="pw",
        display_name="Participant",
        age=25,
        plan_id=1,
    )
    jam = Jam(jam_id=10, host_user_id=2, room_name="Party", is_active=True)
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

    interaction_repo = MagicMock()
    interaction_repo.list_by_user.return_value = [
        Interaction(
            user_id=1,
            track_id=200,
            action=InteractionAction.LIKE,
            source="jam",
        )
    ]

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.list_active.return_value = [t1, t2]

    use_case = GetJamDeckUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=track_repo,
        interaction_repo=interaction_repo,
    )
    result = use_case.execute(jam_id=10, user_id=1)

    assert [t.track_id for t in result.items] == [100]


def test_get_jam_deck_keeps_favorites_based_candidates_when_not_jam_interactions() -> (
    None
):
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
        deck_source="curtidas",
    )
    t1 = Track(
        track_id=100, title="Liked", artist="Artist", duration_seconds=180, genre="Rock"
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam
    jam_repo.is_participant.return_value = True
    jam_repo.list_queue.return_value = []

    interaction_repo = MagicMock()
    interaction_repo.list_by_user.return_value = [
        Interaction(
            user_id=1, track_id=100, action=InteractionAction.LIKE, source="discovery"
        ),
        Interaction(
            user_id=1, track_id=200, action=InteractionAction.LIKE, source="jam"
        ),
    ]

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_ids.return_value = {100: t1}
    track_repo.list_active.return_value = []

    use_case = GetJamDeckUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=track_repo,
        interaction_repo=interaction_repo,
    )

    result = use_case.execute(jam_id=10, user_id=1)

    assert [t.track_id for t in result.items] == [100]


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


def test_get_jam_deck_keeps_unvoted_queue_tracks_plus_base_candidates() -> None:
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
        deck_source="curtidas",
        current_track_id=1000,
    )
    profile_track = Track(
        track_id=10,
        title="Shape of You",
        artist="Ed Sheeran",
        duration_seconds=233,
        genre="Pop",
    )
    queue_voted = Track(
        track_id=200,
        title="Jambo",
        artist="Artist",
        duration_seconds=180,
        genre="Rock",
    )
    queue_unvoted = Track(
        track_id=300,
        title="Flowers",
        artist="Miley Cyrus",
        duration_seconds=200,
        genre="Pop",
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam
    jam_repo.is_participant.return_value = True
    jam_repo.list_queue.return_value = [
        JamQueueItem(jam_id=10, track_id=200, initial_vote_points=1),
        JamQueueItem(jam_id=10, track_id=300, initial_vote_points=1),
    ]

    interaction_repo = MagicMock()
    interaction_repo.list_by_user.return_value = [
        Interaction(
            user_id=1,
            track_id=10,
            action=InteractionAction.LIKE,
            source="discovery",
        ),
        Interaction(
            user_id=1,
            track_id=200,
            action=InteractionAction.LIKE,
            source="jam",
            jam_id=10,
        ),
    ]

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_ids.return_value = {
        10: profile_track,
        200: queue_voted,
        300: queue_unvoted,
    }

    use_case = GetJamDeckUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=track_repo,
        interaction_repo=interaction_repo,
    )

    result = use_case.execute(jam_id=10, user_id=1)

    assert [t.track_id for t in result.items] == [10, 300]


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


def test_get_jam_deck_livre_weights_favorite_genres_and_paginates_deterministically() -> (
    None
):
    user = User(
        user_id=1,
        email="participant@ribbit.com",
        password_hash="pw",
        display_name="Participant",
        age=25,
        plan_id=1,
        favorite_genres=frozenset({"rock"}),
    )
    jam = Jam(
        jam_id=10,
        host_user_id=2,
        room_name="Party",
        is_active=True,
        deck_source="livre",
    )
    candidates = [
        Track(
            track_id=i,
            title=f"Song {i}",
            artist="Artist",
            duration_seconds=180,
            genre="Rock" if i <= 15 else "Pop",
        )
        for i in range(1, 31)
    ]

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam
    jam_repo.is_participant.return_value = True
    jam_repo.list_queue.return_value = []

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.list_active.return_value = candidates

    use_case = GetJamDeckUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=track_repo,
    )

    page1 = use_case.execute(GetJamDeckCommand(jam_id=10, user_id=1, limit=10))
    assert len(page1.items) == 10
    assert page1.has_more is True
    assert page1.next_cursor is not None

    page2 = use_case.execute(
        GetJamDeckCommand(jam_id=10, user_id=1, limit=25, cursor_id=page1.next_cursor)
    )
    assert len(page2.items) == 20
    assert page2.has_more is False

    combined_ids = [t.track_id for t in page1.items] + [t.track_id for t in page2.items]
    # All 30 tracks returned across pages with zero duplicates
    assert len(combined_ids) == 30
    assert set(combined_ids) == set(range(1, 31))
    # Favorite genre ("Rock") should be heavily represented in the first page
    assert sum(1 for t in page1.items if t.genre == "Rock") >= 6


def test_get_jam_deck_livre_cursor_pagination_when_cursor_track_was_queued_or_excluded() -> (
    None
):
    user = User(
        user_id=1,
        email="participant@ribbit.com",
        password_hash="pw",
        display_name="Participant",
        age=25,
        plan_id=1,
        favorite_genres=frozenset({"rock"}),
    )
    jam = Jam(
        jam_id=10,
        host_user_id=2,
        room_name="Party",
        is_active=True,
        deck_source="livre",
    )
    candidates = [
        Track(
            track_id=i,
            title=f"Song {i}",
            artist="Artist",
            duration_seconds=180,
            genre="Rock" if i > 15 else "Pop",
        )
        for i in range(1, 31)
    ]
    tracks_by_id = {t.track_id: t for t in candidates if t.track_id is not None}

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    jam_repo = MagicMock(spec=JamRepositoryPort)
    jam_repo.find_by_id.return_value = jam
    jam_repo.is_participant.return_value = True
    jam_repo.list_queue.return_value = []

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.list_active.side_effect = lambda **kwargs: [
        t for t in candidates if t.track_id not in set(kwargs.get("excluded_ids") or [])
    ]
    track_repo.find_by_id.side_effect = tracks_by_id.get
    track_repo.find_by_ids.return_value = {}

    use_case = GetJamDeckUseCase(
        jam_repo=jam_repo,
        user_repo=user_repo,
        track_repo=track_repo,
    )

    page1 = use_case.execute(GetJamDeckCommand(jam_id=10, user_id=1, limit=10))
    assert len(page1.items) == 10
    assert page1.next_cursor is not None

    # Simulate the cursor track (and all Page 1 tracks) being excluded before Page 2
    jam.current_track_id = page1.next_cursor
    page2 = use_case.execute(
        GetJamDeckCommand(jam_id=10, user_id=1, limit=25, cursor_id=page1.next_cursor)
    )

    page1_ids = [t.track_id for t in page1.items]
    page2_ids = [t.track_id for t in page2.items]
    assert len(page2_ids) == 20
    assert set(page1_ids).isdisjoint(page2_ids)
    assert set(page1_ids + page2_ids) == set(range(1, 31))
