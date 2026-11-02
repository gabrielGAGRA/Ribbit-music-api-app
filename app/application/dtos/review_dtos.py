"""Data transfer objects for catalog search and reviews."""

from dataclasses import dataclass

lazy from app.domain.models.interaction import Interaction
lazy from app.domain.models.track import Track


@dataclass(slots=True, frozen=True, kw_only=True)
class SearchTracksCommand:
    user_id: int
    artist: str | None = None
    album: str | None = None
    genre: str | None = None
    year: int | None = None
    query: str | None = None
    limit: int = 50
    offset: int = 0


@dataclass(slots=True, frozen=True, kw_only=True)
class PublishReviewCommand:
    user_id: int
    track_id: int
    rating: int
    text: str | None = None


@dataclass(slots=True, frozen=True, kw_only=True)
class SaveSearchTrackLikeCommand:
    user_id: int
    track_id: int
    playlist_id: int | None = None


@dataclass(slots=True, frozen=True, kw_only=True)
class UserTrackInteractionResult:
    interaction: Interaction
    track: Track


__all__ = [
    "PublishReviewCommand",
    "SaveSearchTrackLikeCommand",
    "SearchTracksCommand",
    "UserTrackInteractionResult",
]
