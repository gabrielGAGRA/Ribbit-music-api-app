"""Use case for liking a review comment."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError
lazy from app.application.ports.repositories.review_repository import (
    ReviewRepositoryPort,
)
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.review import ReviewComment


@dataclass(slots=True, frozen=True)
class LikeReviewCommentUseCase:
    """Increments the like counter of a community review comment idempotently."""

    review_repo: ReviewRepositoryPort
    user_repo: UserRepositoryPort | None = None

    def execute(self, review_id: int, user_id: int) -> ReviewComment:
        if self.user_repo is not None:
            user = self.user_repo.find_by_id(user_id)
            if not user:
                raise EntityNotFoundError(f"User with ID {user_id} not found.")

        review = self.review_repo.find_by_id(review_id)
        if not review or review.is_deleted:
            raise EntityNotFoundError("Review not found or deleted.")

        if self.review_repo.has_user_liked(review_id, user_id):
            return review

        review.like()
        saved = self.review_repo.save(review)
        self.review_repo.record_like(review_id, user_id)
        return saved


__all__ = ["LikeReviewCommentUseCase"]
