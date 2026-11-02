"""Domain models for collaborative Jam sessions and voting queues."""

import secrets
import string
from dataclasses import InitVar, dataclass, field
from typing import ClassVar, Self
lazy from datetime import datetime

from app.domain.exceptions import BusinessRuleViolationError


@dataclass(slots=True, kw_only=True, eq=False)
class Jam:
    @staticmethod
    def generate_room_code() -> str:
        return "".join(secrets.choice(string.digits) for _ in range(6))

    jam_id: int | None = None
    host_user_id: int
    room_name: str
    room_code: str = field(default_factory=generate_room_code)
    is_active: bool = True
    current_track_id: int | None = None
    created_at: datetime | None = None
    duration_minutes: int = 60
    max_superlikes: int = 10
    superlikes_used: int = 0
    skip_votes_threshold: int = 3
    accumulated_duration_seconds: int = 0
    deck_source: str = "livre"
    source_playlist_id: int | None = None

    def __post_init__(self) -> None:
        if not self.room_name.strip():
            raise ValueError("Jam room name cannot be blank.")

    @classmethod
    def create(
        cls,
        host_user_id: int,
        room_name: str,
        room_code: str | None = None,
        *,
        duration_minutes: int = 60,
        max_superlikes: int = 10,
        skip_votes_threshold: int = 3,
        deck_source: str = "livre",
        source_playlist_id: int | None = None,
    ) -> Self:
        return cls(
            host_user_id=host_user_id,
            room_name=room_name,
            room_code=room_code or cls.generate_room_code(),
            duration_minutes=duration_minutes,
            max_superlikes=max_superlikes,
            skip_votes_threshold=skip_votes_threshold,
            deck_source=deck_source,
            source_playlist_id=source_playlist_id,
        )

    def is_host(self, user_id: int) -> bool:
        return self.host_user_id == user_id

    @property
    def max_duration_seconds(self) -> int:
        return self.duration_minutes * 60

    def can_use_superlike(self) -> bool:
        return self.superlikes_used < self.max_superlikes

    def use_superlike(self) -> Self:
        if not self.can_use_superlike():
            raise BusinessRuleViolationError(
                "Superlike limit reached for this Jam session."
            )
        self.superlikes_used += 1
        return self

    def is_duration_exceeded(self) -> bool:
        return self.accumulated_duration_seconds >= self.max_duration_seconds

    def add_accumulated_duration(self, seconds: int) -> Self:
        self.accumulated_duration_seconds += seconds
        if self.is_duration_exceeded():
            self.close()
        return self

    def set_current_track(self, track_id: int | None) -> Self:
        if not self.is_active:
            raise BusinessRuleViolationError(
                "Cannot set current track on a closed Jam session."
            )
        self.current_track_id = track_id
        return self

    def close(self) -> Self:
        self.is_active = False
        return self


@dataclass(slots=True, kw_only=True, eq=False)
class JamQueueItem:
    MIN_POINTS: ClassVar[int] = -10
    MAX_POINTS: ClassVar[int] = 10

    jam_id: int
    track_id: int
    jam_queue_id: int | None = None
    added_at: datetime | None = None
    initial_vote_points: InitVar[int] = 0
    _vote_points: int = field(init=False, repr=False)

    def __post_init__(self, initial_vote_points: int) -> None:
        if not self.MIN_POINTS <= initial_vote_points <= self.MAX_POINTS:
            raise ValueError(
                f"Vote points must be between {self.MIN_POINTS} and {self.MAX_POINTS}."
            )
        self._vote_points = initial_vote_points

    @property
    def vote_points(self) -> int:
        return self._vote_points

    def vote(self, points: int) -> Self:
        """Adds points to the running total, clamped to MIN_POINTS..MAX_POINTS."""
        total = self._vote_points + points
        self._vote_points = max(self.MIN_POINTS, min(self.MAX_POINTS, total))
        return self
