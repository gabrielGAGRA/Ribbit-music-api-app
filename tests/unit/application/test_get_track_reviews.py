"""Unit tests for GetTrackReviewsUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.review_repository import ReviewRepositoryPort
from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.application.use_cases.review.get_track_reviews import GetTrackReviewsUseCase
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.review import ReviewComment
from app.domain.models.track import Track


def test_get_track_reviews_returns_active_reviews_for_valid_track() -> None:
    track = Track(
        track_id=100,
        title="Swamp Symphony",
        artist="Maestro Frog",
        duration_seconds=240,
        genre="Classical",
    )
    reviews = [
        ReviewComment(
            review_id=1,
            user_id=5,
            track_id=100,
            initial_rating=4,
            text="Lovely strings",
        )
    ]

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track

    review_repo = MagicMock(spec=ReviewRepositoryPort)
    review_repo.list_by_track.return_value = reviews

    use_case = GetTrackReviewsUseCase(
        track_repo=track_repo,
        review_repo=review_repo,
    )

    result = use_case.execute(track_id=100, limit=20)

    assert result == reviews
    track_repo.find_by_id.assert_called_once_with(100)
    review_repo.list_by_track.assert_called_once_with(100, limit=20)


def test_get_track_reviews_track_not_found_raises_entity_not_found() -> None:
    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = None

    review_repo = MagicMock(spec=ReviewRepositoryPort)

    use_case = GetTrackReviewsUseCase(
        track_repo=track_repo,
        review_repo=review_repo,
    )

    with pytest.raises(EntityNotFoundError, match="Track not found or inactive"):
        use_case.execute(track_id=404)

    review_repo.list_by_track.assert_not_called()


def test_get_track_reviews_soft_deleted_track_raises_entity_not_found() -> None:
    deleted_track = Track(
        track_id=100,
        title="Deleted Track",
        artist="Artist",
        duration_seconds=180,
        genre="Pop",
        is_deleted=True,
    )
    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = deleted_track

    review_repo = MagicMock(spec=ReviewRepositoryPort)

    use_case = GetTrackReviewsUseCase(
        track_repo=track_repo,
        review_repo=review_repo,
    )

    with pytest.raises(EntityNotFoundError, match="Track not found or inactive"):
        use_case.execute(track_id=100)

    review_repo.list_by_track.assert_not_called()
