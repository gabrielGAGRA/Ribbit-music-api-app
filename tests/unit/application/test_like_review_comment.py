"""Unit tests for LikeReviewCommentUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.use_cases.review.like_review_comment import (
    LikeReviewCommentUseCase,
)
from app.domain.exceptions import EntityNotFoundError
from app.domain.models import ReviewComment


def _identity_review(r: ReviewComment) -> ReviewComment:
    return r


def test_like_review_comment_success() -> None:
    review = ReviewComment(
        review_id=1,
        user_id=10,
        track_id=100,
        initial_rating=5,
        text="Great song!",
        initial_likes_count=3,
    )
    review_repo = MagicMock()
    review_repo.find_by_id.return_value = review
    review_repo.has_user_liked.return_value = False
    review_repo.save.side_effect = _identity_review

    use_case = LikeReviewCommentUseCase(review_repo=review_repo)
    result = use_case.execute(review_id=1, user_id=20)

    assert result.likes_count == 4
    review_repo.has_user_liked.assert_called_once_with(1, 20)
    review_repo.save.assert_called_once_with(review)
    review_repo.record_like.assert_called_once_with(1, 20)


def test_like_review_comment_already_liked_is_idempotent() -> None:
    review = ReviewComment(
        review_id=1,
        user_id=10,
        track_id=100,
        initial_rating=5,
        text="Great song!",
        initial_likes_count=3,
    )
    review_repo = MagicMock()
    review_repo.find_by_id.return_value = review
    review_repo.has_user_liked.return_value = True

    use_case = LikeReviewCommentUseCase(review_repo=review_repo)
    result = use_case.execute(review_id=1, user_id=20)

    assert result.likes_count == 3
    review_repo.has_user_liked.assert_called_once_with(1, 20)
    review_repo.record_like.assert_not_called()
    review_repo.save.assert_not_called()


def test_like_review_comment_not_found_raises_error() -> None:
    review_repo = MagicMock()
    review_repo.find_by_id.return_value = None

    use_case = LikeReviewCommentUseCase(review_repo=review_repo)

    with pytest.raises(EntityNotFoundError):
        use_case.execute(review_id=999, user_id=20)


def test_like_review_comment_deleted_raises_error() -> None:
    review = ReviewComment(
        review_id=1,
        user_id=10,
        track_id=100,
        initial_rating=5,
        text="Great song!",
        initial_likes_count=3,
        is_deleted=True,
    )
    review_repo = MagicMock()
    review_repo.find_by_id.return_value = review

    use_case = LikeReviewCommentUseCase(review_repo=review_repo)

    with pytest.raises(EntityNotFoundError):
        use_case.execute(review_id=1, user_id=20)
