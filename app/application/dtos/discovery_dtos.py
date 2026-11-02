"""Data transfer objects for track discovery and swipes."""

from dataclasses import dataclass

lazy from app.domain.models.interaction import InteractionAction


@dataclass(slots=True, frozen=True, kw_only=True)
class RecordSwipeCommand:
    user_id: int
    track_id: int
    action: InteractionAction | str


__all__ = ["RecordSwipeCommand"]
