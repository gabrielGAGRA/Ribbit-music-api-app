"""Unit tests for GetNextDiscoveryTrackUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.discovery.get_next_discovery_track import (
    GetNextDiscoveryTrackUseCase,
)
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.track import Track
from app.domain.models.user import User


def test_get_next_discovery_track_for_adult_passes_preferences_and_returns_track() -> (
    None
):
    adult_user = User(
        user_id=1,
        email="adult@ribbit.com",
        password_hash="pw",
        display_name="Adult Frog",
        age=25,
        plan_id=1,
        blocked_genres=frozenset({"country"}),
    )
    candidate_track = Track(
        track_id=10,
        title="Midnight Hop",
        artist="DJ Toad",
        duration_seconds=210,
        genre="Electronic",
        explicit=True,
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = adult_user

    interaction_repo = MagicMock(spec=InteractionRepositoryPort)
    interaction_repo.list_interacted_track_ids.return_value = [1, 2, 3]

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.list_active.return_value = [candidate_track]

    use_case = GetNextDiscoveryTrackUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
        interaction_repo=interaction_repo,
    )

    result = use_case.execute(user_id=1)

    assert result is candidate_track
    interaction_repo.list_interacted_track_ids.assert_called_once_with(1)
    track_repo.list_active.assert_called_once_with(
        excluded_genres=("country",),
        block_explicit=False,
        excluded_ids=[1, 2, 3],
        limit=1,
    )


def test_get_next_discovery_track_for_minor_blocks_explicit_tracks() -> None:
    minor_user = User(
        user_id=2,
        email="minor@ribbit.com",
        password_hash="pw",
        display_name="Tadpole",
        age=15,
        plan_id=1,
        blocked_genres=frozenset(),
    )
    clean_track = Track(
        track_id=20,
        title="Sunny Pond",
        artist="Lily",
        duration_seconds=180,
        genre="Pop",
        explicit=False,
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = minor_user

    interaction_repo = MagicMock(spec=InteractionRepositoryPort)
    interaction_repo.list_interacted_track_ids.return_value = []

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.list_active.return_value = [clean_track]

    use_case = GetNextDiscoveryTrackUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
        interaction_repo=interaction_repo,
    )

    result = use_case.execute(user_id=2)

    assert result is clean_track
    track_repo.list_active.assert_called_once_with(
        excluded_genres=(),
        block_explicit=True,
        excluded_ids=[],
        limit=1,
    )


def test_get_next_discovery_track_returns_none_when_no_candidates_remain() -> None:
    user = User(
        user_id=1,
        email="adult@ribbit.com",
        password_hash="pw",
        display_name="Adult Frog",
        age=25,
        plan_id=1,
    )
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    interaction_repo = MagicMock(spec=InteractionRepositoryPort)
    interaction_repo.list_interacted_track_ids.return_value = [10, 11]

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.list_active.return_value = []

    use_case = GetNextDiscoveryTrackUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
        interaction_repo=interaction_repo,
    )

    result = use_case.execute(user_id=1)

    assert result is None


def test_get_next_discovery_track_user_not_found_raises_entity_not_found() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None

    use_case = GetNextDiscoveryTrackUseCase(
        user_repo=user_repo,
        track_repo=MagicMock(spec=TrackRepositoryPort),
        interaction_repo=MagicMock(spec=InteractionRepositoryPort),
    )

    with pytest.raises(EntityNotFoundError, match="User with ID 999 not found"):
        use_case.execute(user_id=999)


def test_get_next_discovery_track_fetches_itunes_preview_fallback_when_missing() -> (
    None
):
    from app.application.ports.services.music_service import (
        TrackPreview,
        TrackPreviewPort,
    )

    user = User(
        user_id=1,
        email="adult@ribbit.com",
        password_hash="pw",
        display_name="Adult Frog",
        age=25,
        plan_id=1,
    )
    track_without_preview = Track(
        track_id=10,
        title="Midnight Hop",
        artist="DJ Toad",
        duration_seconds=210,
        genre="Electronic",
        itunes_preview_url=None,
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    interaction_repo = MagicMock(spec=InteractionRepositoryPort)
    interaction_repo.list_interacted_track_ids.return_value = []

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.list_active.return_value = [track_without_preview]
    track_repo.save.side_effect = lambda t: t

    preview_service = MagicMock(spec=TrackPreviewPort)
    preview_service.find_preview.return_value = TrackPreview(
        external_id="ext-123",
        title="Midnight Hop",
        artist="DJ Toad",
        preview_url="https://audio-ssl.itunes.apple.com/preview.m4a",
        cover_url=None,
    )

    use_case = GetNextDiscoveryTrackUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
        interaction_repo=interaction_repo,
        track_preview_port=preview_service,
    )

    result = use_case.execute(user_id=1)

    assert result is not None
    assert result.itunes_preview_url == "https://audio-ssl.itunes.apple.com/preview.m4a"
    preview_service.find_preview.assert_called_once_with("DJ Toad Midnight Hop")
    track_repo.save.assert_called_once_with(track_without_preview)
