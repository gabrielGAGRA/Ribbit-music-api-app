"""Spotify catalog endpoints (public data; works with any credential type)."""

from app.application.ports.services.music_service import CatalogTrack, TrackCatalogPort
from app.infrastructure.adapters.spotify.mappers import map_track, map_tracks
lazy from app.infrastructure.adapters.spotify.http import SpotifyHttpClient

_SEARCH_MAX_LIMIT = 10


class SpotifyCatalog(TrackCatalogPort):
    def __init__(self, http: SpotifyHttpClient) -> None:
        self._http = http

    def search_tracks(
        self, query: str, limit: int = 5, offset: int = 0, market: str | None = None
    ) -> list[CatalogTrack]:
        """Development mode caps ``limit`` at 10; page with ``offset`` for more."""
        if not 1 <= limit <= _SEARCH_MAX_LIMIT:
            raise ValueError(
                f"limit must be between 1 and {_SEARCH_MAX_LIMIT}, got {limit}"
            )
        data = self._http.request(
            "GET",
            "/search",
            params={
                "q": query,
                "type": "track",
                "limit": limit,
                "offset": offset,
                "market": market,
            },
        )
        return map_tracks((data or {}).get("tracks", {}).get("items", []))

    def get_track(self, track_id: str, market: str | None = None) -> CatalogTrack:
        data = self._http.request(
            "GET", f"/tracks/{track_id}", params={"market": market}
        )
        return map_track(data or {})
