"""Application ports for the Spotify Web API capabilities beyond catalog search."""

from typing import Protocol, runtime_checkable
lazy from collections.abc import Sequence

from app.application.ports.services.music_service import PlaylistSourcePort
lazy from app.application.dtos.spotify_dtos import (
    SpotifyPlaybackState,
    SpotifyQueue,
    SpotifyTokens,
)
lazy from app.application.ports.services.music_service import ProviderPlaylist


@runtime_checkable
class SpotifyAuthPort(Protocol):
    def get_authorize_url(self, scopes: Sequence[str], state: str) -> str: ...

    def exchange_code(self, code: str) -> SpotifyTokens: ...

    def refresh_access_token(self) -> SpotifyTokens: ...

    def get_client_credentials_token(self) -> SpotifyTokens: ...


@runtime_checkable
class SpotifyPlaylistsPort(PlaylistSourcePort, Protocol):
    def get_my_playlists(
        self, limit: int = 20, offset: int = 0
    ) -> list[ProviderPlaylist]: ...

    def create_playlist(
        self,
        name: str,
        *,
        public: bool = False,
        collaborative: bool = False,
        description: str | None = None,
    ) -> ProviderPlaylist: ...

    def update_playlist_details(
        self,
        playlist_id: str,
        *,
        name: str | None = None,
        public: bool | None = None,
        collaborative: bool | None = None,
        description: str | None = None,
    ) -> None: ...

    def add_playlist_items(
        self, playlist_id: str, uris: Sequence[str], position: int | None = None
    ) -> str:
        """Returns the new snapshot id."""
        ...

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
        """Reorders items, or replaces them all when only ``uris`` is given."""
        ...

    def remove_playlist_items(
        self, playlist_id: str, uris: Sequence[str], snapshot_id: str | None = None
    ) -> str: ...

    def get_playlist_cover(self, playlist_id: str) -> list[str]: ...

    def upload_playlist_cover(self, playlist_id: str, base64_jpeg: str) -> None: ...


@runtime_checkable
class SpotifyQueuePort(Protocol):
    def get_playback_state(
        self, market: str | None = None
    ) -> SpotifyPlaybackState | None:
        """Returns None when no player is active."""
        ...

    def get_queue(self) -> SpotifyQueue: ...

    def add_to_queue(self, uri: str, device_id: str | None = None) -> None: ...

    def next_track(self, device_id: str | None = None) -> None: ...

    def previous_track(self, device_id: str | None = None) -> None: ...

    def seek(self, position_ms: int, device_id: str | None = None) -> None: ...

    def play(
        self,
        *,
        context_uri: str | None = None,
        uris: Sequence[str] | None = None,
        offset: int | None = None,
        position_ms: int | None = None,
        device_id: str | None = None,
    ) -> None:
        """Starts the given context/uris, or resumes playback when nothing is given."""
        ...

    def pause(self, device_id: str | None = None) -> None: ...
