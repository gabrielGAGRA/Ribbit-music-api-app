"""Ports and result types for external music catalog and export services."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
lazy from collections.abc import Sequence

lazy from app.domain.models.track import ExternalTrackId

_FEAT_SUFFIX_RE = re.compile(r"\s*[\(\[](?:feat|ft)\.?\s+[^)\]]*[\)\]]", re.IGNORECASE)
_NON_ALNUM_RE = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_match_text(value: str | None) -> str:
    if not value:
        return ""
    stripped = _FEAT_SUFFIX_RE.sub("", value)
    ascii_folded = "".join(
        ch
        for ch in unicodedata.normalize("NFKD", stripped)
        if not unicodedata.combining(ch)
    )
    cleaned = _NON_ALNUM_RE.sub(" ", ascii_folded.lower())
    return " ".join(cleaned.split())


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
    explicit: bool = False


@dataclass(slots=True, frozen=True, kw_only=True)
class TrackPreview:
    external_id: ExternalTrackId | str
    title: str | None
    artist: str | None
    preview_url: str | None
    cover_url: str | None
    genre: str | None = None
    country: str | None = None
    album: str | None = None
    release_year: int | None = None

    def matches_track(self, *, title: str, artist: str) -> bool:
        """Verifies the preview's title and artist reasonably match the target track."""
        p_title = normalize_match_text(self.title)
        t_title = normalize_match_text(title)
        p_artist = normalize_match_text(self.artist)
        t_artist = normalize_match_text(artist)
        if not p_title or not t_title or not p_artist or not t_artist:
            return False
        title_ok = p_title in t_title or t_title in p_title
        artist_parts = [
            normalize_match_text(part)
            for part in artist.split(",")
            if normalize_match_text(part)
        ]
        artist_ok = (
            p_artist in t_artist
            or t_artist in p_artist
            or any(part in p_artist or p_artist in part for part in artist_parts)
        )
        return title_ok and artist_ok


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


def lookup_matching_preview(
    preview_port: TrackPreviewPort, *, title: str, artist: str
) -> TrackPreview | None:
    """Queries preview_port with progressive fallback terms and returns the first valid match."""
    primary_artist = artist.split(",", maxsplit=1)[0].strip()
    base_title = title.split("--", maxsplit=1)[0].split(" - ", maxsplit=1)[0].strip()
    candidates = [
        f"{artist} {title}".strip(),
        f"{primary_artist} {base_title}".strip(),
    ]
    seen: set[str] = set()
    for term in candidates:
        if not term or term in seen:
            continue
        seen.add(term)
        preview = preview_port.find_preview(term)
        if preview is not None and preview.matches_track(title=title, artist=artist):
            return preview
    return None


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
        self,
        account_id: str,
        name: str,
        track_ids: Sequence[ExternalTrackId | str],
        *,
        access_token: str | None = None,
        refresh_token: str | None = None,
    ) -> str:
        """Returns the identifier of the playlist created at the provider.

        Raises:
            ExternalServiceError: If the external provider fails or times out.
        """
        ...
