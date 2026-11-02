"""Use case for retrieving top-liked recent community reviews."""

from dataclasses import dataclass

lazy from app.application.ports.repositories.review_repository import (
    ReviewRepositoryPort,
)
lazy from app.domain.models.review import ReviewComment


@dataclass(slots=True, frozen=True)
class GetCommunityFeedUseCase:
    """Returns the most liked reviews from the last given number of days."""

    review_repo: ReviewRepositoryPort

    def execute(self, days: int = 5, limit: int = 3) -> list[ReviewComment]:
        return self.review_repo.list_top_recent(days=days, limit=limit)
