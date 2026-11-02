"""Unit tests for DeleteReviewUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.ports.repositories.review_repository import (
    ReviewRepositoryPort,
)
from app.application.use_cases.review.delete_review import (
    DeleteReviewUseCase,
)
from app.domain.exceptions import EntityNotFoundError, ForbiddenError
from app.domain.models import ReviewComment


def test_delete_review_by_author_succeeds() -> None:
    review = ReviewComment(
        review_id=1,
        user_id=10,
        track_id=100,
        initial_rating=4,
        text="Solid tune",
    )
    repo = MagicMock(spec=ReviewRepositoryPort)
    repo.find_by_id.return_value = review
    repo.delete.return_value = True

    use_case = DeleteReviewUseCase(review_repo=repo)
    result = use_case.execute(review_id=1, user_id=10)

    assert result is True
    repo.find_by_id.assert_called_once_with(1)
    repo.delete.assert_called_once_with(1)


def test_delete_review_by_non_author_raises_forbidden() -> None:
    review = ReviewComment(
        review_id=1,
        user_id=10,
        track_id=100,
        initial_rating=4,
        text="Solid tune",
    )
    repo = MagicMock(spec=ReviewRepositoryPort)
    repo.find_by_id.return_value = review

    use_case = DeleteReviewUseCase(review_repo=repo)

    with pytest.raises(ForbiddenError, match="Only the author"):
        use_case.execute(review_id=1, user_id=99)

    repo.delete.assert_not_called()


def test_delete_review_not_found_raises_entity_not_found() -> None:
    repo = MagicMock(spec=ReviewRepositoryPort)
    repo.find_by_id.return_value = None

    use_case = DeleteReviewUseCase(review_repo=repo)

    with pytest.raises(EntityNotFoundError, match="Review with ID 999 not found"):
        use_case.execute(review_id=999, user_id=10)

    repo.delete.assert_not_called()
