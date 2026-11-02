"""Port definitions for external file-based music catalog sources."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable
lazy from collections.abc import Sequence


@dataclass(slots=True, frozen=True, kw_only=True)
class CatalogSourceTrack:
    """Represents a music track entry loaded from an external file source."""

    title: str
    artist: str
    duration_seconds: int = 180
    genre: str | None = "Unknown"
    album: str | None = None
    country: str | None = None
    release_year: int | None = None
    cover_url: str | None = None
    spotify_id: str | None = None
    itunes_preview_url: str | None = None
    explicit: bool = False


@dataclass(slots=True, frozen=True, kw_only=True)
class CatalogVersionInfo:
    """Catalog version and timestamp metadata."""

    version: int
    updated_at: str


@runtime_checkable
class TrackCatalogFilePort(Protocol):
    """Port for fetching, modifying, and compacting catalog tracks from an external file source."""

    def fetch_tracks(self) -> Sequence[CatalogSourceTrack]:
        """Loads and returns track records from the file source, merging any pending deltas."""
        ...

    def write_track_delta(
        self,
        *,
        title: str,
        artist: str,
        preview_url: str | None = None,
        genre: str | None = None,
        spotify_id: str | None = None,
    ) -> None:
        """Writes a lightweight micro-delta file to remote storage for enriched track metadata."""
        ...

    def write_preview_delta(
        self,
        *,
        title: str,
        artist: str,
        preview_url: str,
        spotify_id: str | None = None,
    ) -> None:
        """Writes a lightweight micro-delta file to remote storage for an enriched preview URL."""
        ...

    def compact_catalog(self) -> int:
        """Consolidates pending deltas into base catalog file, cleanses deltas, bumps version.

        Returns:
            The new catalog version number.
        """
        ...

    def get_catalog_version(self) -> CatalogVersionInfo:
        """Reads the remote catalog version sentinel."""
        ...


__all__ = ["CatalogSourceTrack", "CatalogVersionInfo", "TrackCatalogFilePort"]
