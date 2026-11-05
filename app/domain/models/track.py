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

    def has_known_genre(self) -> bool:
        return bool(
            self.genre
            and self.genre.strip()
            and self.genre.strip().lower() != "unknown"
        )

    def set_genre(self, genre: str) -> Self:
        cleaned = genre.strip()
        if not cleaned:
            raise ValueError("Track genre must not be empty.")
        self.genre = cleaned
        return self

    def merge_missing_metadata(
        self,
        *,
        cover_url: str | None = None,
        album: str | None = None,
        release_year: int | None = None,
        country: str | None = None,
        itunes_preview_url: str | None = None,
        genre: str | None = None,
        spotify_id: str | None = None,
    ) -> bool:
        changed = False
        if not self.cover_url and cover_url:
            self.cover_url = cover_url
            changed = True
        if not self.album and album:
            self.album = album
            changed = True
        if self.release_year is None and release_year is not None:
            self.release_year = release_year
            changed = True
        if not self.country and country:
            self.country = country
            changed = True
        if not self.itunes_preview_url and itunes_preview_url:
            self.itunes_preview_url = itunes_preview_url
            changed = True
        if not self.spotify_id and spotify_id:
            self.spotify_id = spotify_id
            changed = True
        if (
            genre is not None
            and not self.has_known_genre()
            and genre.strip()
            and genre.strip().lower() != "unknown"
        ):
            self.genre = genre.strip()
            changed = True
        return changed

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
