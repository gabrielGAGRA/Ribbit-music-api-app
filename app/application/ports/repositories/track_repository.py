"""Persistence port for tracks."""

from typing import Protocol, runtime_checkable
lazy from collections.abc import Sequence

lazy from app.domain.models.track import Track, TrackId


@runtime_checkable
class TrackRepositoryPort(Protocol):
    def find_by_id(self, track_id: TrackId | int) -> Track | None: ...

    def find_by_ids(self, track_ids: Sequence[TrackId | int]) -> dict[int, Track]: ...

    def save(self, track: Track) -> Track: ...

    def list_active(
        self,
        *,
        limit: int,
        excluded_genres: Sequence[str] = (),
        block_explicit: bool = False,
        excluded_ids: Sequence[int] = (),
    ) -> list[Track]:
        """Returns non-deleted tracks eligible for discovery, in a stable order."""
        ...

    def find_by_filters(
        self,
        *,
        artist: str | None = None,
        album: str | None = None,
        genre: str | None = None,
        year: int | None = None,
        query: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Track]: ...

    def count_all(self) -> int: ...

    def count_active(self) -> int: ...

    def find_by_spotify_id(self, spotify_id: str) -> Track | None: ...

    def find_by_title_and_artist(self, title: str, artist: str) -> Track | None: ...

    def list_blocked(self) -> list[Track]: ...
