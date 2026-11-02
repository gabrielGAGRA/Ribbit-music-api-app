"""Unit tests for SaveSearchTrackLikeUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.review.save_search_track_like import (
    SaveSearchTrackLikeUseCase,
)
from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    ForbiddenError,
)
from app.domain.models import Interaction, Playlist, Track, User


def test_save_search_track_like_saves_interaction_and_adds_to_playlist() -> None:
    user = User(
        user_id=1,
        email="adult@ribbit.com",
        password_hash="pw",
        display_name="Adult",
        age=25,
        plan_id=1,
    )
    track = Track(
        track_id=10,
        title="Bohemian Rhapsody",
        artist="Queen",
        duration_seconds=354,
        genre="Rock",
    )
    playlist = Playlist(
        playlist_id=5,
        user_id=1,
        name="Favorites",
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track

    def _save_interaction(i: Interaction) -> Interaction:
        return i

    interaction_repo = MagicMock(spec=InteractionRepositoryPort)
    interaction_repo.save.side_effect = _save_interaction

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.find_by_id.return_value = playlist

    use_case = SaveSearchTrackLikeUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
        interaction_repo=interaction_repo,
        playlist_repo=playlist_repo,
    )
    success = use_case.execute(user_id_or_cmd=1, track_id=10, playlist_id=5)

    assert success is True
    interaction_repo.save.assert_called_once()
    saved_interaction = interaction_repo.save.call_args[0][0]
    assert saved_interaction.user_id == 1
    assert saved_interaction.track_id == 10
    playlist_repo.save.assert_called_once_with(playlist)
    assert len(playlist.tracks) == 1


def test_save_search_track_like_blocks_explicit_for_minor() -> None:
    minor = User(
        user_id=2,
        email="minor@ribbit.com",
        password_hash="pw",
        display_name="Minor",
        age=14,
        plan_id=1,
    )
    explicit_track = Track(
        track_id=20,
        title="Rap God",
        artist="Eminem",
        duration_seconds=364,
        genre="Hip Hop",
        explicit=True,
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = minor

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = explicit_track

    use_case = SaveSearchTrackLikeUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
        interaction_repo=MagicMock(spec=InteractionRepositoryPort),
    )

    with pytest.raises(BusinessRuleViolationError, match="menores de idade"):
        use_case.execute(user_id_or_cmd=2, track_id=20)


def test_save_search_track_like_rejects_non_owned_playlist() -> None:
    user = User(
        user_id=1,
        email="adult@ribbit.com",
        password_hash="pw",
        display_name="Adult",
        age=25,
        plan_id=1,
    )
    track = Track(
        track_id=10,
        title="Song",
        artist="Artist",
        duration_seconds=200,
        genre="Pop",
    )
    other_playlist = Playlist(
        playlist_id=99,
        user_id=2,
        name="Other's Playlist",
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track

    playlist_repo = MagicMock(spec=PlaylistRepositoryPort)
    playlist_repo.find_by_id.return_value = other_playlist

    use_case = SaveSearchTrackLikeUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
        interaction_repo=MagicMock(spec=InteractionRepositoryPort),
        playlist_repo=playlist_repo,
    )

    with pytest.raises(ForbiddenError, match="não pertence a este usuário"):
        use_case.execute(user_id_or_cmd=1, track_id=10, playlist_id=99)


def test_save_search_track_like_track_not_found_raises_entity_not_found() -> None:
    user = User(
        user_id=1,
        email="adult@ribbit.com",
        password_hash="pw",
        display_name="Adult",
        age=25,
        plan_id=1,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = None

    use_case = SaveSearchTrackLikeUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
        interaction_repo=MagicMock(spec=InteractionRepositoryPort),
    )

    with pytest.raises(EntityNotFoundError, match="não encontrada"):
        use_case.execute(user_id_or_cmd=1, track_id=999)
