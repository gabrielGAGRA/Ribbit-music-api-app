"""Domain model representing a music track."""

from dataclasses import dataclass
from typing import NewType, Self
lazy from datetime import datetime

TrackId = NewType("TrackId", int)
ExternalTrackId = NewType("ExternalTrackId", str)


@dataclass(slots=True, kw_only=True, eq=False)
class Track:
    track_id: int | None = None
    title: str
    artist: str
    duration_seconds: int
    genre: str
    spotify_id: str | None = None
    album: str | None = None
    country: str | None = None
    release_year: int | None = None
    cover_url: str | None = None
    itunes_preview_url: str | None = None
    explicit: bool = False
    is_deleted: bool = False
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.duration_seconds <= 0:
            raise ValueError("Track duration must be positive.")

    def set_explicit(self, explicit: bool) -> Self:
        self.explicit = explicit
        return self

    def refresh_catalog_metadata(
        self,
        *,
        title: str,
        artist: str,
        duration_seconds: int,
        album: str | None,
        cover_url: str | None,
        release_year: int | None,
    ) -> Self:
        """Updates provider-owned fields, keeping genre, explicit flag, and deletion."""
        if duration_seconds <= 0:
            raise ValueError("Track duration must be positive.")
        self.title = title
        self.artist = artist
        self.duration_seconds = duration_seconds
        self.album = album
        self.cover_url = cover_url
        self.release_year = release_year
        return self

    def mark_as_deleted(self) -> Self:
        self.is_deleted = True
        return self

    def restore(self) -> Self:
        self.is_deleted = False
        return self
