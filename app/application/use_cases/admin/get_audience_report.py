"""Use case for generating system audience and catalog metrics."""

from dataclasses import dataclass

from app.application.dtos.admin_dtos import AudienceReportResult
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort


@dataclass(slots=True, frozen=True)
class GetAudienceReportUseCase:
    """Returns platform counters for registered users, tracks, and aggregated blocked genres."""

    user_repo: UserRepositoryPort
    track_repo: TrackRepositoryPort

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

        return AudienceReportResult(
            total_users=total_users,
            total_tracks=total_tracks,
            active_tracks=active_tracks,
            blocked_genres=blocked_genres,
        )


__all__ = ["GetAudienceReportUseCase"]
