"""Unit tests for GetCommunityFeedUseCase."""

from unittest.mock import MagicMock

from app.application.ports.repositories.review_repository import ReviewRepositoryPort
from app.application.use_cases.review.get_community_feed import GetCommunityFeedUseCase
from app.domain.models.review import ReviewComment


def test_get_community_feed_uses_default_days_and_limit() -> None:
    top_reviews = [
        ReviewComment(
            review_id=1,
            user_id=10,
            track_id=100,
            initial_rating=5,
            text="Masterpiece!",
            initial_likes_count=42,
        )
    ]
    review_repo = MagicMock(spec=ReviewRepositoryPort)
    review_repo.list_top_recent.return_value = top_reviews

    use_case = GetCommunityFeedUseCase(review_repo=review_repo)
    result = use_case.execute()

    assert result == top_reviews
    review_repo.list_top_recent.assert_called_once_with(days=5, limit=3)


def test_get_community_feed_forwards_custom_days_and_limit() -> None:
    review_repo = MagicMock(spec=ReviewRepositoryPort)
    review_repo.list_top_recent.return_value = []

    use_case = GetCommunityFeedUseCase(review_repo=review_repo)
    result = use_case.execute(days=14, limit=10)

    assert result == []
    review_repo.list_top_recent.assert_called_once_with(days=14, limit=10)
