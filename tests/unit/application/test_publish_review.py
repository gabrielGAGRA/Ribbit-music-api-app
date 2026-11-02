"""Unit tests for PublishReviewUseCase."""

from unittest.mock import MagicMock

import pytest

from app.application.dtos.review_dtos import PublishReviewCommand
from app.application.ports.repositories.review_repository import ReviewRepositoryPort
from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.use_cases.review.publish_review import PublishReviewUseCase
from app.domain.exceptions import (
    BusinessRuleViolationError,
    DuplicateEntityError,
    EntityNotFoundError,
)
from app.domain.models.review import ReviewComment
from app.domain.models.track import Track
from app.domain.models.user import User


def test_publish_review_success_strips_text_and_saves_review() -> None:
    user = User(
        user_id=1,
        email="critic@ribbit.com",
        password_hash="pw",
        display_name="Critic Frog",
        age=28,
        plan_id=1,
    )
    track = Track(
        track_id=10,
        title="Lily Pad Waltz",
        artist="Frog Orchestra",
        duration_seconds=200,
        genre="Jazz",
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track

    def _save_review(r: ReviewComment) -> ReviewComment:
        return r

    review_repo = MagicMock(spec=ReviewRepositoryPort)
    review_repo.find_active_by_user_and_track.return_value = None
    review_repo.save.side_effect = _save_review

    use_case = PublishReviewUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
        review_repo=review_repo,
    )
    command = PublishReviewCommand(
        user_id=1,
        track_id=10,
        rating=5,
        text="  Incredible brass section!  ",
    )

    result = use_case.execute(command)

    assert result.user_id == 1
    assert result.track_id == 10
    assert result.rating == 5
    assert result.text == "Incredible brass section!"
    assert result.likes_count == 0
    assert result.is_deleted is False
    review_repo.save.assert_called_once_with(result)


def test_publish_review_duplicate_active_review_raises_duplicate_entity_error() -> None:
    user = User(
        user_id=1,
        email="critic@ribbit.com",
        password_hash="pw",
        display_name="Critic Frog",
        age=28,
        plan_id=1,
    )
    track = Track(
        track_id=10,
        title="Lily Pad Waltz",
        artist="Frog Orchestra",
        duration_seconds=200,
        genre="Jazz",
    )
    existing_review = ReviewComment(
        review_id=100,
        user_id=1,
        track_id=10,
        initial_rating=4,
        text="Earlier review",
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = track

    review_repo = MagicMock(spec=ReviewRepositoryPort)
    review_repo.find_active_by_user_and_track.return_value = existing_review

    use_case = PublishReviewUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
        review_repo=review_repo,
    )
    command = PublishReviewCommand(
        user_id=1,
        track_id=10,
        rating=5,
        text="Another review",
    )

    with pytest.raises(DuplicateEntityError, match="already reviewed"):
        use_case.execute(command)

    review_repo.save.assert_not_called()


@pytest.mark.parametrize("invalid_rating", [0, 6, -1])
def test_publish_review_out_of_bounds_rating_raises_business_rule_error(
    invalid_rating: int,
) -> None:
    use_case = PublishReviewUseCase(
        user_repo=MagicMock(spec=UserRepositoryPort),
        track_repo=MagicMock(spec=TrackRepositoryPort),
        review_repo=MagicMock(spec=ReviewRepositoryPort),
    )
    command = PublishReviewCommand(
        user_id=1,
        track_id=10,
        rating=invalid_rating,
        text="Bad rating",
    )

    with pytest.raises(
        BusinessRuleViolationError, match="Rating must be between 1 and 5"
    ):
        use_case.execute(command)


def test_publish_review_user_not_found_raises_entity_not_found() -> None:
    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = None

    use_case = PublishReviewUseCase(
        user_repo=user_repo,
        track_repo=MagicMock(spec=TrackRepositoryPort),
        review_repo=MagicMock(spec=ReviewRepositoryPort),
    )
    command = PublishReviewCommand(user_id=999, track_id=10, rating=4)

    with pytest.raises(EntityNotFoundError, match="User with ID 999 not found"):
        use_case.execute(command)


def test_publish_review_soft_deleted_track_raises_entity_not_found() -> None:
    user = User(
        user_id=1,
        email="critic@ribbit.com",
        password_hash="pw",
        display_name="Critic Frog",
        age=28,
        plan_id=1,
    )
    deleted_track = Track(
        track_id=10,
        title="Deleted Song",
        artist="Artist",
        duration_seconds=200,
        genre="Jazz",
        is_deleted=True,
    )

    user_repo = MagicMock(spec=UserRepositoryPort)
    user_repo.find_by_id.return_value = user

    track_repo = MagicMock(spec=TrackRepositoryPort)
    track_repo.find_by_id.return_value = deleted_track

    review_repo = MagicMock(spec=ReviewRepositoryPort)

    use_case = PublishReviewUseCase(
        user_repo=user_repo,
        track_repo=track_repo,
        review_repo=review_repo,
    )
    command = PublishReviewCommand(user_id=1, track_id=10, rating=4)

    with pytest.raises(
        EntityNotFoundError, match="Track with ID 10 not found or inactive"
    ):
        use_case.execute(command)

    review_repo.save.assert_not_called()
