"""Use case for listing global track access history for administrators."""

from dataclasses import dataclass

lazy from app.application.ports.repositories.track_access_repository import (
    TrackAccessRepositoryPort,
)
lazy from app.domain.models.track_access import AdminTrackAccessEntry


@dataclass(slots=True, frozen=True)
class ListAdminAccessHistoryUseCase:
    """Lists track accesses across all users, preserving soft-deleted tracks."""

    track_access_repo: TrackAccessRepositoryPort

    def execute(
        self,
        *,
        user_id: int | None = None,
        track_id: int | None = None,
        only_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AdminTrackAccessEntry]:
        return self.track_access_repo.list_all_admin(
            user_id=user_id,
            track_id=track_id,
            only_deleted=only_deleted,
            limit=limit,
            offset=offset,
        )
