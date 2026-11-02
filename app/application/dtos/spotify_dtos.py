"""Spotify tokens, player projections, and sync commands exchanged across layers."""

from dataclasses import dataclass

from app.domain.exceptions import BusinessRuleViolationError
lazy from app.application.ports.services.music_service import CatalogTrack


@dataclass(slots=True, frozen=True, kw_only=True)
class SpotifyTokens:
    access_token: str
    expires_in: int
    refresh_token: str | None = None
    scope: str | None = None


@dataclass(slots=True, frozen=True, kw_only=True)
class SpotifyQueue:
    currently_playing: CatalogTrack | None = None
    queue: tuple[CatalogTrack, ...] = ()


@dataclass(slots=True, frozen=True, kw_only=True)
class SpotifyPlaybackState:
    is_playing: bool
    progress_ms: int | None = None
    device_id: str | None = None
    device_name: str | None = None
    track: CatalogTrack | None = None


@dataclass(slots=True, frozen=True, kw_only=True)
class SyncTracksFromSpotifyCommand:
    """``genre`` fills the catalog genre because Spotify exposes none in Development mode."""

    query: str
    limit: int = 10
    offset: int = 0
    genre: str = "Desconhecido"

    def __post_init__(self) -> None:
        if not 1 <= self.limit <= 10:
            raise BusinessRuleViolationError(
                f"limit must be between 1 and 10, got {self.limit}",
                rule_name="spotify_search_limit",
                details={"limit": self.limit},
            )
        if self.offset < 0:
            raise BusinessRuleViolationError(
                "offset must be non-negative",
                rule_name="spotify_search_offset",
                details={"offset": self.offset},
            )


@dataclass(slots=True, frozen=True, kw_only=True)
class SyncPlaylistFromSpotifyCommand:
    """``max_items`` bounds API calls: Spotify has no batch routes and quota is shared."""

    user_id: int
    spotify_playlist_id: str
    max_items: int = 100
    genre: str = "Desconhecido"

    def __post_init__(self) -> None:
        if self.max_items <= 0:
            raise BusinessRuleViolationError(
                "max_items must be positive",
                rule_name="spotify_sync_max_items",
                details={"max_items": self.max_items},
            )
