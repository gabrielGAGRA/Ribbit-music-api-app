"""Spotify player and queue endpoints (user token, Premium for control commands)."""

from typing import TYPE_CHECKING
lazy from collections.abc import Sequence

from app.application.ports.services.spotify import SpotifyQueuePort
from app.infrastructure.adapters.spotify.mappers import (
    drop_none,
    map_playback_state,
    map_queue,
)
lazy from app.infrastructure.adapters.spotify.http import SpotifyHttpClient

if TYPE_CHECKING:
    from app.application.dtos.spotify_dtos import SpotifyPlaybackState, SpotifyQueue

_READ_STATE = frozenset({"user-read-playback-state"})
_READ_QUEUE = frozenset({"user-read-currently-playing", "user-read-playback-state"})
_MODIFY = frozenset({"user-modify-playback-state"})


class SpotifyPlayer(SpotifyQueuePort):
    """Control commands need Premium and a device with ``is_restricted == false``."""

    def __init__(self, http: SpotifyHttpClient) -> None:
        self._http = http

    def get_playback_state(
        self, market: str | None = None
    ) -> SpotifyPlaybackState | None:
        """Returns None when no player is active; poll every 30-60s then to save quota."""
        data = self._http.request(
            "GET", "/me/player", params={"market": market}, scopes=_READ_STATE
        )
        return map_playback_state(data) if data else None

    def get_queue(self) -> SpotifyQueue:
        data = self._http.request("GET", "/me/player/queue", scopes=_READ_QUEUE)
        return map_queue(data or {})

    def add_to_queue(self, uri: str, device_id: str | None = None) -> None:
        self._http.request(
            "POST",
            "/me/player/queue",
            params={"uri": uri, "device_id": device_id},
            scopes=_MODIFY,
        )

    def next_track(self, device_id: str | None = None) -> None:
        self._http.request(
            "POST", "/me/player/next", params={"device_id": device_id}, scopes=_MODIFY
        )

    def previous_track(self, device_id: str | None = None) -> None:
        self._http.request(
            "POST",
            "/me/player/previous",
            params={"device_id": device_id},
            scopes=_MODIFY,
        )

    def seek(self, position_ms: int, device_id: str | None = None) -> None:
        self._http.request(
            "PUT",
            "/me/player/seek",
            params={"position_ms": position_ms, "device_id": device_id},
            scopes=_MODIFY,
        )

    def play(
        self,
        *,
        context_uri: str | None = None,
        uris: Sequence[str] | None = None,
        offset: int | None = None,
        position_ms: int | None = None,
        device_id: str | None = None,
    ) -> None:
        body = drop_none(
            {
                "context_uri": context_uri,
                "uris": list(uris) if uris is not None else None,
                "offset": {"position": offset} if offset is not None else None,
                "position_ms": position_ms,
            }
        )
        self._http.request(
            "PUT",
            "/me/player/play",
            params={"device_id": device_id},
            json=body or None,
            scopes=_MODIFY,
        )

    def pause(self, device_id: str | None = None) -> None:
        self._http.request(
            "PUT", "/me/player/pause", params={"device_id": device_id}, scopes=_MODIFY
        )
