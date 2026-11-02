"""Use case for retrieving top-liked reviews for administrative moderation."""

from dataclasses import dataclass

lazy from app.application.ports.repositories.review_repository import (
    ReviewRepositoryPort,
)
lazy from app.domain.models.review import ReviewComment


@dataclass(slots=True, frozen=True)
class GetTopModerationReviewsUseCase:
    """Returns top liked reviews from the last 30 days for content moderation."""

    review_repo: ReviewRepositoryPort

    def execute(self) -> list[ReviewComment]:
        return self.review_repo.list_top_recent(days=30, limit=10)
