"""Ports and result types for external music catalog and export services."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable
lazy from collections.abc import Sequence

lazy from app.domain.models.track import ExternalTrackId


@dataclass(slots=True, frozen=True, kw_only=True)
class CatalogTrack:
    external_id: ExternalTrackId | str | None
    title: str | None
    artist: str
    album: str | None
    preview_url: str | None
    uri: str | None = None
    duration_ms: int | None = None
    cover_url: str | None = None
    release_year: int | None = None


@dataclass(slots=True, frozen=True, kw_only=True)
class TrackPreview:
    external_id: ExternalTrackId | str
    title: str | None
    artist: str | None
    preview_url: str | None
    cover_url: str | None


@dataclass(slots=True, frozen=True, kw_only=True)
class ProviderPlaylist:
    external_id: str
    name: str
    description: str | None = None
    public: bool | None = None
    snapshot_id: str | None = None


@dataclass(slots=True, frozen=True, kw_only=True)
class PlaylistItemsPage:
    items: list[CatalogTrack]
    total: int = 0
    raw_item_count: int = 0


@runtime_checkable
class TrackCatalogPort(Protocol):
    def search_tracks(
        self, query: str, limit: int = 5, offset: int = 0, market: str | None = None
    ) -> list[CatalogTrack]: ...

    def get_track(self, track_id: str, market: str | None = None) -> CatalogTrack: ...


@runtime_checkable
class TrackPreviewPort(Protocol):
    def find_preview(self, term: str) -> TrackPreview | None:
        """Returns None when the provider has no match.

        Raises:
            ExternalServiceError: If the external provider fails or times out.
        """
        ...


@runtime_checkable
class PlaylistSourcePort(Protocol):
    def get_playlist(
        self, playlist_id: str, market: str | None = None
    ) -> ProviderPlaylist: ...

    def get_playlist_items(
        self,
        playlist_id: str,
        limit: int = 50,
        offset: int = 0,
        market: str | None = None,
    ) -> PlaylistItemsPage: ...


@runtime_checkable
class PlaylistExportPort(Protocol):
    def export_playlist(
        self, account_id: str, name: str, track_ids: Sequence[ExternalTrackId | str]
    ) -> str:
        """Returns the identifier of the playlist created at the provider.

        Raises:
            ExternalServiceError: If the external provider fails or times out.
        """
        ...
