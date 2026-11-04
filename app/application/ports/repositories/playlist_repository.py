"""Persistence port for playlists."""

from typing import Protocol, runtime_checkable

lazy from app.domain.models import Playlist


@runtime_checkable
class PlaylistRepositoryPort(Protocol):
    def find_by_id(self, playlist_id: int) -> Playlist | None:
        """Returns the playlist aggregate including its tracks."""
        ...

    def list_by_user(self, user_id: int) -> list[Playlist]: ...

    def save(self, playlist: Playlist) -> Playlist:
        """Persists the whole aggregate, including track membership."""
        ...

    def delete(self, playlist_id: int) -> bool: ...

    def remove_track(self, playlist_id: int, track_id: int) -> bool: ...

    def save_cover_image(
        self,
        playlist_id: int,
        content_type: str,
        image_data: bytes,
        cover_image_url: str,
    ) -> bool:
        """Stores/replaces a playlist cover image; returns false if playlist is missing."""
        ...

    def get_cover_image(self, playlist_id: int) -> tuple[str, bytes] | None:
        """Returns a playlist cover's media type and bytes, if present."""
        ...
