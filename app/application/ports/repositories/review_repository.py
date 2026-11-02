"""Persistence port for reviews and comments."""

from typing import Protocol, runtime_checkable

lazy from app.domain.models import ReviewComment


@runtime_checkable
class ReviewRepositoryPort(Protocol):
    def find_by_id(self, review_id: int) -> ReviewComment | None: ...

    def save(self, review: ReviewComment) -> ReviewComment: ...

    def list_by_track(self, track_id: int, limit: int) -> list[ReviewComment]:
        """Returns non-deleted reviews for a track."""
        ...

    def list_top_recent(self, days: int, limit: int) -> list[ReviewComment]:
        """Returns the most liked non-deleted reviews from the last `days` days."""
        ...

    def has_user_liked(self, review_id: int, user_id: int) -> bool: ...

    def record_like(self, review_id: int, user_id: int) -> None: ...

    def find_active_by_user_and_track(
        self, user_id: int, track_id: int
    ) -> ReviewComment | None: ...

    def delete(self, review_id: int) -> bool: ...
