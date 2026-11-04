"""Discovery and interaction presentation schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class InteractionRequest(BaseModel):
    """Payload to record a swipe interaction on a track."""

    model_config = ConfigDict(extra="forbid")

    track_id: int
    action: Literal["like", "superlike", "dislike"]


class ChangeInteractionRequest(BaseModel):
    """Payload to modify an existing swipe interaction."""

    model_config = ConfigDict(extra="forbid")

    track_id: int
    new_action: Literal["like", "superlike", "dislike"]


class InteractionResponse(BaseModel):
    """Public representation of an interaction event."""

    model_config = ConfigDict(from_attributes=True)

    interaction_id: int
    user_id: int
    track_id: int
    action: str
    created_at: datetime | None = None


class UndoInteractionResponse(BaseModel):
    """Result of undoing the latest discovery swipe."""

    success: bool = True
    interaction_id: int
    track_id: int
    action: str
    created_at: datetime | None = None


class TrackSearchQuery(BaseModel):
    """Query parameters for track catalog searches."""

    query: str | None = None
    artist: str | None = None
    album: str | None = None
    genre: str | None = None
    year: int | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


__all__ = [
    "ChangeInteractionRequest",
    "InteractionRequest",
    "InteractionResponse",
    "TrackSearchQuery",
    "UndoInteractionResponse",
]
