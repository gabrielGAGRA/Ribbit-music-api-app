"""Use case for fetching reviews authored by a specific user."""

from dataclasses import dataclass

lazy from app.application.ports.repositories.review_repository import (
    ReviewRepositoryPort,
)
lazy from app.domain.models.review import ReviewComment


@dataclass(slots=True, frozen=True)
class GetUserReviewsUseCase:
    """Returns non-deleted reviews authored by the authenticated user."""

    review_repo: ReviewRepositoryPort

    def execute(self, user_id: int, limit: int = 50) -> list[ReviewComment]:
        return self.review_repo.list_by_user(user_id, limit=limit)


__all__ = ["GetUserReviewsUseCase"]
