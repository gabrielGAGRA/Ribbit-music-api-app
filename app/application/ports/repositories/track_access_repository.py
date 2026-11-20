"""Persistence port for track access history and analytical aggregations."""

from typing import Protocol, runtime_checkable

lazy from app.domain.models.track_access import (
    AdminTrackAccessEntry,
    TrackAccess,
    TrackAccessCount,
    TrackAccessEntry,
)


@runtime_checkable
class TrackAccessRepositoryPort(Protocol):
    """Port for recording and querying user track accesses."""

    def record(self, access: TrackAccess) -> TrackAccess: ...

    def list_by_user(
        self,
        user_id: int,
        *,
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TrackAccessEntry]: ...

    def list_seen_track_ids(self, user_id: int) -> list[int]: ...

    def list_all_admin(
        self,
        *,
        user_id: int | None = None,
        track_id: int | None = None,
        only_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AdminTrackAccessEntry]: ...

    def count_all(self) -> int: ...

    def count_by_track(
        self, limit: int = 10, include_deleted: bool = True
    ) -> list[TrackAccessCount]: ...

    def count_by_genre(
        self, include_deleted: bool = True
    ) -> list[TrackAccessCount]: ...
