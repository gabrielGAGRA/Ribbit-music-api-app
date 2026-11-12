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

    @classmethod
    def aliases(cls) -> dict[str, Self]:
        return {
            "like": cls.LIKE,
            "curtida": cls.LIKE,
            "superlike": cls.SUPERLIKE,
            "amada": cls.SUPERLIKE,
            "dislike": cls.DISLIKE,
            "deslike": cls.DISLIKE,
            "rejeitada": cls.DISLIKE,
            "rejeitar": cls.DISLIKE,
        }

    @classmethod
    def parse(cls, value: str | Self | None, default: Self | None = None) -> Self:
        if isinstance(value, cls):
            return value
        if value is None:
            if default is not None:
                return default
            raise ValueError("Interaction action cannot be None.")
        norm = str(value).strip().lower()
        if not norm:
            if default is not None:
                return default
            raise ValueError("Interaction action cannot be empty.")
        aliases = cls.aliases()
        if norm in aliases:
            return aliases[norm]
        if default is not None:
            return default
        raise ValueError(f"Invalid interaction action: '{value}'. Valid: {list(cls)}")


class InteractionSource(StrEnum):
    DISCOVERY = "discovery"
    JAM = "jam"
    PLAYLIST = "playlist"
    SEARCH = "search"
    PROFILE = "profile"


@dataclass(slots=True, kw_only=True, eq=False)
class Interaction:
    interaction_id: int | None = None
    user_id: int
    track_id: int
    action: InteractionAction
    created_at: datetime | None = None
    source: InteractionSource | str | None = None
    jam_id: int | None = None

    @property
    def is_positive(self) -> bool:
        return self.action.is_positive

    def change_action(self, new_action: InteractionAction) -> Self:
        self.action = new_action
        return self
