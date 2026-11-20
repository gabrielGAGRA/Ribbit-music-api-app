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

    def execute(
        self, days: int | None = None, limit: int = 10, sort_by: str = "likes"
    ) -> list[ReviewComment]:
        return self.review_repo.list_top_recent(days=days, limit=limit, sort_by=sort_by)
