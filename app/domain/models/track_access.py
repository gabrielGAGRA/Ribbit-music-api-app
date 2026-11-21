"""Domain models and projections for track access history."""

from dataclasses import dataclass
from typing import Literal
lazy from datetime import datetime

TrackAccessSource = Literal[
    "swipe",
    "play",
    "details",
    "search",
    "playlist",
    "profile",
    "jam",
]

VALID_TRACK_ACCESS_SOURCES: frozenset[str] = frozenset(
    {"swipe", "play", "details", "search", "playlist", "profile", "jam"}
)


@dataclass(slots=True, kw_only=True, eq=False)
class TrackAccess:
    """Represents a single recorded user access to a track."""

    access_id: int | None = None
    user_id: int
    track_id: int
    source: TrackAccessSource | str
    accessed_at: datetime | None = None


@dataclass(slots=True, frozen=True, kw_only=True)
class TrackAccessEntry:
    """Listener-facing projection of a track access joined with track metadata."""

    access_id: int
    user_id: int
    track_id: int
    track_title: str
    track_artist: str
    track_genre: str
    track_album: str | None = None
    track_duration_seconds: int = 0
    track_cover_url: str | None = None
    track_preview_url: str | None = None
    track_explicit: bool = False
    track_is_deleted: bool = False
    source: str
    accessed_at: datetime


@dataclass(slots=True, frozen=True, kw_only=True)
class AdminTrackAccessEntry:
    """Admin-facing projection preserving user identity and soft-delete status."""

    access_id: int
    user_id: int
    user_display_name: str
    user_email: str
    track_id: int
    track_title: str
    track_artist: str
    track_genre: str
    track_is_deleted: bool
    source: str
    accessed_at: datetime


@dataclass(slots=True, frozen=True, kw_only=True)
class TrackAccessCount:
    """Aggregated access count for a track or genre."""

    label: str
    access_count: int
    track_id: int | None = None
    artist: str | None = None
    is_deleted: bool = False
