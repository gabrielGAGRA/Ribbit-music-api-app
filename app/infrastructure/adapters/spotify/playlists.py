"""Spotify playlist endpoints (user token required)."""

from typing import TYPE_CHECKING
lazy from collections.abc import Sequence

from app.application.ports.services.music_service import PlaylistItemsPage
from app.application.ports.services.spotify import SpotifyPlaylistsPort
from app.infrastructure.adapters.spotify.mappers import (
    drop_none,
    map_playlist,
    map_tracks,
    read_snapshot_id,
)
lazy from app.infrastructure.adapters.spotify.http import SpotifyHttpClient

if TYPE_CHECKING:
    from app.application.ports.services.music_service import (
        ProviderPlaylist,
    )

_READ = frozenset({"playlist-read-private", "playlist-read-collaborative"})
_MODIFY = frozenset({"playlist-modify-public", "playlist-modify-private"})


class SpotifyPlaylists(SpotifyPlaylistsPort):
    """In Development mode, item routes use ``/items`` and return content only for own playlists."""

    def __init__(self, http: SpotifyHttpClient) -> None:
        self._http = http

    def get_my_playlists(
        self, limit: int = 20, offset: int = 0
    ) -> list[ProviderPlaylist]:
        data = self._http.request(
            "GET",
            "/me/playlists",
            params={"limit": limit, "offset": offset},
            scopes=_READ,
        )
        return [map_playlist(item) for item in (data or {}).get("items", [])]

    def create_playlist(
        self,
        name: str,
        *,
        public: bool = False,
        collaborative: bool = False,
        description: str | None = None,
    ) -> ProviderPlaylist:
        body = drop_none(
            {
                "name": name,
                "public": public,
                "collaborative": collaborative,
                "description": description,
            }
        )
        data = self._http.request("POST", "/me/playlists", json=body, scopes=_MODIFY)
        return map_playlist(data or {})

    def update_playlist_details(
        self,
        playlist_id: str,
        *,
        name: str | None = None,
        public: bool | None = None,
        collaborative: bool | None = None,
        description: str | None = None,
    ) -> None:
        body = drop_none(
            {
                "name": name,
                "public": public,
                "collaborative": collaborative,
                "description": description,
            }
        )
        self._http.request(
            "PUT", f"/playlists/{playlist_id}", json=body, scopes=_MODIFY
        )

    def get_playlist(
        self, playlist_id: str, market: str | None = None
    ) -> ProviderPlaylist:
        data = self._http.request(
            "GET",
            f"/playlists/{playlist_id}",
            params={"market": market},
            scopes=frozenset({"playlist-read-private"}),
        )
        return map_playlist(data or {})

    def get_playlist_items(
        self,
        playlist_id: str,
        limit: int = 50,
        offset: int = 0,
        market: str | None = None,
    ) -> PlaylistItemsPage:
        data = self._http.request(
            "GET",
            f"/playlists/{playlist_id}/items",
            params={"limit": limit, "offset": offset, "market": market},
            scopes=_READ,
        )
        raw_items = (data or {}).get("items", [])
        total = int((data or {}).get("total", 0))
        return PlaylistItemsPage(
            items=map_tracks(entry.get("item") for entry in raw_items),
            total=total,
            raw_item_count=len(raw_items),
        )

    def add_playlist_items(
        self, playlist_id: str, uris: Sequence[str], position: int | None = None
    ) -> str:
        body = drop_none({"uris": list(uris), "position": position})
        data = self._http.request(
            "POST", f"/playlists/{playlist_id}/items", json=body, scopes=_MODIFY
        )
        return read_snapshot_id(data)

    def update_playlist_items(
        self,
        playlist_id: str,
        *,
        uris: Sequence[str] | None = None,
        range_start: int | None = None,
        insert_before: int | None = None,
        range_length: int | None = None,
        snapshot_id: str | None = None,
    ) -> str | None:
        body = drop_none(
            {
                "uris": list(uris) if uris is not None else None,
                "range_start": range_start,
                "insert_before": insert_before,
                "range_length": range_length,
                "snapshot_id": snapshot_id,
            }
        )
        data = self._http.request(
            "PUT", f"/playlists/{playlist_id}/items", json=body, scopes=_MODIFY
        )
        return read_snapshot_id(data) if data else None

    def remove_playlist_items(
        self, playlist_id: str, uris: Sequence[str], snapshot_id: str | None = None
    ) -> str:
        body = drop_none(
            {"items": [{"uri": uri} for uri in uris], "snapshot_id": snapshot_id}
        )
        data = self._http.request(
            "DELETE", f"/playlists/{playlist_id}/items", json=body, scopes=_MODIFY
        )
        return read_snapshot_id(data)

    def get_playlist_cover(self, playlist_id: str) -> list[str]:
        data = self._http.request("GET", f"/playlists/{playlist_id}/images")
        return [image["url"] for image in data or []]

    def upload_playlist_cover(self, playlist_id: str, base64_jpeg: str) -> None:
        """Has its own, stricter Spotify rate limit."""
        self._http.request(
            "PUT",
            f"/playlists/{playlist_id}/images",
            data=base64_jpeg,
            content_type="image/jpeg",
            scopes=frozenset({"ugc-image-upload"}),
        )
