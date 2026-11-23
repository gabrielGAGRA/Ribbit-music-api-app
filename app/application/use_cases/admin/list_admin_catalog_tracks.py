"""Use case for listing catalog tracks with interaction and review metrics for admin."""

from dataclasses import dataclass

lazy from app.application.dtos.admin_dtos import AdminCatalogTrackResult
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort


@dataclass(slots=True, frozen=True)
class ListAdminCatalogTracksUseCase:
    """Returns catalog tracks enriched with interaction counts and rating averages."""

    track_repo: TrackRepositoryPort

    def execute(
        self,
        *,
        query: str | None = None,
        include_deleted: bool = False,
        min_dislikes: int | None = None,
        sort_by: str = "id_asc",
        limit: int = 100,
        offset: int = 0,
    ) -> list[AdminCatalogTrackResult]:
        return self.track_repo.list_admin_catalog(
            query=query,
            include_deleted=include_deleted,
            min_dislikes=min_dislikes,
            sort_by=sort_by,
            limit=limit,
            offset=offset,
        )


__all__ = ["ListAdminCatalogTracksUseCase"]
