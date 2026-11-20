"""Use case for generating system audience and catalog metrics."""

from dataclasses import dataclass

from app.application.dtos.admin_dtos import (
    AudienceReportResult,
    GenreAccessCountResult,
    TrackAccessRankResult,
)
lazy from app.application.ports.repositories.track_access_repository import (
    TrackAccessRepositoryPort,
)
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort


@dataclass(slots=True, frozen=True)
class GetAudienceReportUseCase:
    """Returns platform counters for registered users, tracks, blocked genres, and accesses."""

    user_repo: UserRepositoryPort
    track_repo: TrackRepositoryPort
    track_access_repo: TrackAccessRepositoryPort | None = None

    def execute(self) -> AudienceReportResult:
        total_users = self.user_repo.count_all()
        total_tracks = self.track_repo.count_all()
        active_tracks = self.track_repo.count_active()

        blocked_genres: dict[str, int] = {}
        users = self.user_repo.list_all()
        if isinstance(users, list):
            for user in users:
                for genre in getattr(user, "blocked_genres", ()):
                    clean = genre.strip().lower()
                    if clean:
                        blocked_genres[clean] = blocked_genres.get(clean, 0) + 1

        total_accesses = 0
        accesses_by_track: list[TrackAccessRankResult] = []
        accesses_by_genre: list[GenreAccessCountResult] = []
        if self.track_access_repo is not None:
            total_accesses = self.track_access_repo.count_all()
            accesses_by_track = [
                TrackAccessRankResult(
                    track_id=item.track_id or 0,
                    title=item.label,
                    artist=item.artist or "",
                    is_deleted=item.is_deleted,
                    access_count=item.access_count,
                )
                for item in self.track_access_repo.count_by_track(
                    limit=10, include_deleted=True
                )
            ]
            accesses_by_genre = [
                GenreAccessCountResult(
                    genre=item.label,
                    access_count=item.access_count,
                )
                for item in self.track_access_repo.count_by_genre(include_deleted=True)
            ]

        return AudienceReportResult(
            total_users=total_users,
            total_tracks=total_tracks,
            active_tracks=active_tracks,
            blocked_genres=blocked_genres,
            total_accesses=total_accesses,
            accesses_by_track=accesses_by_track,
            accesses_by_genre=accesses_by_genre,
        )


__all__ = ["GetAudienceReportUseCase"]
