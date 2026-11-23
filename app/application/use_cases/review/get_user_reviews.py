"""Use case for retrieving all-time reviews authored by a user."""

from dataclasses import dataclass

lazy from app.application.ports.repositories.review_repository import (
    ReviewRepositoryPort,
)
lazy from app.domain.models.review import ReviewComment


@dataclass(slots=True, frozen=True)
class GetUserReviewsUseCase:
    """Returns non-deleted reviews authored by the given user."""

    review_repo: ReviewRepositoryPort

    def execute(self, user_id: int, limit: int = 50) -> list[ReviewComment]:
        return self.review_repo.list_by_user(user_id=user_id, limit=limit)
