"""Use cases for author and administrator review deletion."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError, ForbiddenError
lazy from app.application.ports.repositories.review_repository import (
    ReviewRepositoryPort,
)


@dataclass(slots=True, frozen=True)
class DeleteReviewUseCase:
    """Soft deletes reviews by their author or an administrator."""

    review_repo: ReviewRepositoryPort

    def execute(self, review_id: int, user_id: int) -> bool:
        return self._delete(review_id, user_id=user_id)

    def execute_as_admin(self, review_id: int) -> bool:
        return self._delete(review_id)

    def _delete(self, review_id: int, user_id: int | None = None) -> bool:
        review = self.review_repo.find_by_id(review_id)
        if not review:
            raise EntityNotFoundError(f"Review with ID {review_id} not found.")

        if user_id is not None and review.user_id != user_id:
            raise ForbiddenError("Only the author can delete this review.")

        return self.review_repo.delete(review_id)


__all__ = ["DeleteReviewUseCase"]
