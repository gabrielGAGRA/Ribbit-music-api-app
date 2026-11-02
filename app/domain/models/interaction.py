"""Domain models for user track interactions and swipe actions."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Self
lazy from datetime import datetime


class InteractionAction(StrEnum):
    LIKE = "like"
    SUPERLIKE = "superlike"
    DISLIKE = "dislike"

    @property
    def is_positive(self) -> bool:
        return self in (InteractionAction.LIKE, InteractionAction.SUPERLIKE)


@dataclass(slots=True, kw_only=True, eq=False)
class Interaction:
    interaction_id: int | None = None
    user_id: int
    track_id: int
    action: InteractionAction
    created_at: datetime | None = None

    @property
    def is_positive(self) -> bool:
        return self.action.is_positive

    def change_action(self, new_action: InteractionAction) -> Self:
        self.action = new_action
        return self
