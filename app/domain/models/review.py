"""Domain model for track community reviews and comments."""

from dataclasses import InitVar, dataclass, field
from typing import ClassVar, Self
lazy from datetime import datetime

from app.domain.exceptions import BusinessRuleViolationError


@dataclass(slots=True, kw_only=True, eq=False)
class ReviewComment:
    MIN_RATING: ClassVar[int] = 1
    MAX_RATING: ClassVar[int] = 5

    review_id: int | None = None
    user_id: int
    track_id: int
    initial_rating: InitVar[int]
    text: str | None = None
    initial_likes_count: InitVar[int] = 0
    is_deleted: bool = False
    created_at: datetime | None = None
    _rating: int = field(init=False, repr=False)
    _likes_count: int = field(init=False, repr=False)

    def __post_init__(self, initial_rating: int, initial_likes_count: int) -> None:
        if initial_likes_count < 0:
            raise ValueError("Likes count cannot be negative.")
        self._rating = self._checked_rating(initial_rating)
        self._likes_count = initial_likes_count

    @property
    def rating(self) -> int:
        return self._rating

    @property
    def likes_count(self) -> int:
        return self._likes_count

    @classmethod
    def is_valid_rating(cls, rating: int) -> bool:
        return cls.MIN_RATING <= rating <= cls.MAX_RATING

    @classmethod
    def _checked_rating(cls, rating: int) -> int:
        if not cls.is_valid_rating(rating):
            raise ValueError(
                f"Rating must be between {cls.MIN_RATING} and {cls.MAX_RATING}, "
                f"got {rating}."
            )
        return rating

    def like(self) -> Self:
        self._likes_count += 1
        return self

    def mark_as_deleted(self) -> Self:
        self.is_deleted = True
        return self

    def update_content(self, new_rating: int, new_text: str | None) -> Self:
        if self.is_deleted:
            raise BusinessRuleViolationError("Cannot update a deleted review.")
        self._rating = self._checked_rating(new_rating)
        self.text = new_text
        return self
