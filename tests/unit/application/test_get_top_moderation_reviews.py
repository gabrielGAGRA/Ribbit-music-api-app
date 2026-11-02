"""Unit tests for GetTopModerationReviewsUseCase."""

from unittest.mock import MagicMock

from app.application.ports.repositories.review_repository import ReviewRepositoryPort
from app.application.use_cases.admin.get_top_moderation_reviews import (
    GetTopModerationReviewsUseCase,
)
from app.domain.models.review import ReviewComment


def test_get_top_moderation_reviews_returns_recent_top_reviews() -> None:
    reviews = [
        ReviewComment(
            review_id=1,
            user_id=10,
            track_id=100,
            initial_rating=5,
            text="Great track!",
            initial_likes_count=25,
        ),
        ReviewComment(
            review_id=2,
            user_id=11,
            track_id=101,
            initial_rating=1,
            text="Terrible mix.",
            initial_likes_count=12,
        ),
    ]
    review_repo = MagicMock(spec=ReviewRepositoryPort)
    review_repo.list_top_recent.return_value = reviews

    use_case = GetTopModerationReviewsUseCase(review_repo=review_repo)
    result = use_case.execute()

    assert result == reviews
    review_repo.list_top_recent.assert_called_once_with(days=30, limit=10)
