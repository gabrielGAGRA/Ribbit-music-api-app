"""Data transfer objects for playlist operations and projections."""

from dataclasses import dataclass
from typing import Any
lazy from collections.abc import Iterator

lazy from app.domain.models.playlist import Playlist
lazy from app.domain.models.track import Track


@dataclass(slots=True, frozen=True, kw_only=True)
class CreateDeckPlaylistCommand:
    user_id: int
    name: str
    duration_minutes: int | None = None
    genre: str | list[str] | None = None
    year: int | list[int] | None = None
    artist: str | list[str] | None = None
    country: str | list[str] | None = None
    description: str | None = None
    deck_filters: str | dict[str, Any] | None = None
    populate_tracks: bool = True
    source_playlist_id: int | None = None
    reference_playlist_id: int | None = None

    def __post_init__(self) -> None:
        effective = self.source_playlist_id or self.reference_playlist_id
        if self.source_playlist_id != effective:
            object.__setattr__(self, "source_playlist_id", effective)


@dataclass(slots=True, frozen=True, kw_only=True)
class GetPlaylistDeckCommand:
    playlist_id: int
    user_id: int
    limit: int = 20
    cursor_id: int | None = None


@dataclass(slots=True, frozen=True, kw_only=True)
class PlaylistDeckResult:
    items: list[Track]
    next_cursor: int | None = None
    has_more: bool = False

    def __iter__(self) -> Iterator[object]:
        return iter((self.items, self.next_cursor, self.has_more))


@dataclass(slots=True, frozen=True, kw_only=True)
class AddTrackToPlaylistCommand:
    playlist_id: int
    track_id: int
    user_id: int
    action: str = "like"


@dataclass(slots=True, frozen=True, kw_only=True)
class RemoveTrackFromPlaylistCommand:
    playlist_id: int
    track_id: int
    user_id: int


@dataclass(slots=True, frozen=True, kw_only=True)
class DeletePlaylistCommand:
    playlist_id: int
    user_id: int


@dataclass(slots=True, frozen=True, kw_only=True)
class PlaylistWithTracksResult:
    playlist: Playlist
    tracks: list[Track]


__all__ = [
    "AddTrackToPlaylistCommand",
    "CreateDeckPlaylistCommand",
    "DeletePlaylistCommand",
    "GetPlaylistDeckCommand",
    "PlaylistDeckResult",
    "PlaylistWithTracksResult",
    "RemoveTrackFromPlaylistCommand",
]
