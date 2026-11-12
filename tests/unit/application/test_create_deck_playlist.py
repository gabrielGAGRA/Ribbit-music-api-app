"""Unit tests for CreateDeckPlaylistUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.playlist_dtos import CreateDeckPlaylistCommand
from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.playlist.create_deck_playlist import (
    CreateDeckPlaylistUseCase,
)
from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError
from app.domain.models.track import Track
from app.domain.models.user import User


def test_create_deck_playlist_respects_duration_tolerance_of_plus_60_seconds() -> None:
    user = User(
        user_id=1,
        email="adult@ribbit.com",
        password_hash="pw",
        display_name="Adult",
        age=25,
        plan_id=1,
    )
    # Target: 5 minutes = 300 seconds, max allowed = 360 seconds (target + 60s tolerance)
    t1 = Track(
        track_id=1,
        title="Track 1",
        artist="Queen",
        duration_seconds=180,
        genre="Rock",
        release_year=1975,
    )
    t2 = Track(
        track_id=2,
        title="Track 2",
        artist="Queen",
        duration_seconds=170,
        genre="Rock",
        release_year=1975,
    )  # 180 + 170 = 350 <= 360 (included)
    t3 = Track(
        track_id=3,
        title="Track 3",
        artist="Queen",
        duration_seconds=60,
        genre="Rock",
        release_year=1975,
    )  # 350 + 60 = 410 > 360 (excluded)

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_filters.return_value = [t1, t2, t3]

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.save.side_effect = lambda p: p

    use_case = CreateDeckPlaylistUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
        playlist_repo=playlist_repo,
    )
    command = CreateDeckPlaylistCommand(
        user_id=1,
        name="  70s Rock Deck  ",
        description="  Classic vibes  ",
        duration_minutes=5,
        genre="Rock",
        year=1975,
        artist="Queen",
    )

    result = use_case.execute(command)

    assert result.name == "70s Rock Deck"
    assert result.description == "Classic vibes"
    assert result.tracks == (t1, t2)
    track_repo.find_by_filters.assert_called_once_with(
        artist="Queen",
        genre="Rock",
        year=1975,
    )
    track_repo.list_active.assert_not_called()
    playlist_repo.save.assert_called_once_with(result)


def test_create_deck_playlist_filters_explicit_tracks_for_minor_and_falls_back_if_empty() -> (
    None
):
    minor = User(
        user_id=2,
        email="minor@ribbit.com",
        password_hash="pw",
        display_name="Minor",
        age=15,
        plan_id=1,
    )
    explicit_candidate = Track(
        track_id=1,
        title="Explicit Hit",
        artist="Artist",
        duration_seconds=200,
        genre="Rap",
        explicit=True,
    )
    fallback_clean_track = Track(
        track_id=2,
        title="Clean Fallback",
        artist="Artist",
        duration_seconds=180,
        genre="Pop",
        explicit=False,
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = minor

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_filters.return_value = [explicit_candidate]
    track_repo.list_active.return_value = [fallback_clean_track]

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.save.side_effect = lambda p: p

    use_case = CreateDeckPlaylistUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
        playlist_repo=playlist_repo,
    )
    command = CreateDeckPlaylistCommand(
        user_id=2,
        name="Teen Mix",
        genre="Rap",
    )

    result = use_case.execute(command)

    assert result.tracks == (fallback_clean_track,)
    track_repo.list_active.assert_called_once_with(
        block_explicit=True,
        limit=10,
    )


def test_create_deck_playlist_preserves_reference_playlist_id() -> None:
    user = User(
        user_id=1,
        email="adult@ribbit.com",
        password_hash="pw",
        display_name="Adult",
        age=25,
        plan_id=1,
    )
    source = Track(
        track_id=7,
        title="Reference Track",
        artist="Artist",
        duration_seconds=180,
        genre="Rock",
    )
    reference_playlist = MagicMock()
    reference_playlist.tracks = [source]

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.list_active.return_value = []

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.save.side_effect = lambda p: p
    playlist_repo.find_by_id.return_value = reference_playlist

    use_case = CreateDeckPlaylistUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
        playlist_repo=playlist_repo,
    )
    command = CreateDeckPlaylistCommand(
        user_id=1,
        name="From Reference",
        source_playlist_id=42,
        duration_minutes=3,
    )

    result = use_case.execute(command)

    assert result.source_playlist_id == 42
    assert result.tracks == (source,)
    playlist_repo.find_by_id.assert_called_once_with(42)


def test_create_deck_playlist_user_not_found_raises_entity_not_found() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None

    use_case = CreateDeckPlaylistUseCase(
        user_repo=user_repo,
        track_repo=MagicMock(spec=TrackRepositoryPort),
        playlist_repo=MagicMock(spec=PlaylistRepositoryPort),
    )
    command = CreateDeckPlaylistCommand(user_id=999, name="Deck")

    with pytest.raises(EntityNotFoundError, match="User with ID 999 not found"):
        use_case.execute(command)


def test_create_deck_playlist_reference_not_owned_raises_permission_denied() -> None:
    user = User(
        user_id=1,
        email="user1@ribbit.com",
        password_hash="pw",
        display_name="User 1",
        age=25,
        plan_id=1,
    )
    reference_playlist = MagicMock()
    reference_playlist.is_owned_by.return_value = False

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.find_by_id.return_value = reference_playlist

    use_case = CreateDeckPlaylistUseCase(
        user_repo=user_repo,
        track_repo=MagicMock(spec=TrackRepositoryPort),
        playlist_repo=playlist_repo,
    )
    command = CreateDeckPlaylistCommand(
        user_id=1,
        name="Foreign Deck",
        source_playlist_id=99,
    )

    with pytest.raises(
        PermissionDeniedError, match="playlist does not belong to this user"
    ):
        use_case.execute(command)


def test_create_deck_playlist_reference_not_found_raises_entity_not_found() -> None:
    user = User(
        user_id=1,
        email="user1@ribbit.com",
        password_hash="pw",
        display_name="User 1",
        age=25,
        plan_id=1,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.find_by_id.return_value = None

    use_case = CreateDeckPlaylistUseCase(
        user_repo=user_repo,
        track_repo=MagicMock(spec=TrackRepositoryPort),
        playlist_repo=playlist_repo,
    )
    command = CreateDeckPlaylistCommand(
        user_id=1,
        name="Missing Reference Deck",
        source_playlist_id=404,
    )

    with pytest.raises(EntityNotFoundError, match="Playlist with ID 404 not found"):
        use_case.execute(command)


def test_create_deck_playlist_filters_blocked_genres_for_user_from_reference() -> None:
    user = User(
        user_id=1,
        email="adult@ribbit.com",
        password_hash="pw",
        display_name="Adult",
        age=25,
        plan_id=1,
        blocked_genres={"Metal"},
    )
    allowed_track = Track(
        track_id=1,
        title="Rock Anthem",
        artist="RockBand",
        duration_seconds=200,
        genre="Rock",
    )
    blocked_track = Track(
        track_id=2,
        title="Heavy Riff",
        artist="MetalBand",
        duration_seconds=210,
        genre="Metal",
    )
    reference_playlist = MagicMock()
    reference_playlist.tracks = [allowed_track, blocked_track]
    reference_playlist.is_owned_by.return_value = True

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.save.side_effect = lambda p: p
    playlist_repo.find_by_id.return_value = reference_playlist

    use_case = CreateDeckPlaylistUseCase(
        user_repo=user_repo,
        track_repo=MagicMock(spec=TrackRepositoryPort),
        playlist_repo=playlist_repo,
    )
    command = CreateDeckPlaylistCommand(
        user_id=1,
        name="Cleaned Deck",
        source_playlist_id=10,
    )

    result = use_case.execute(command)

    assert result.tracks == (allowed_track,)
