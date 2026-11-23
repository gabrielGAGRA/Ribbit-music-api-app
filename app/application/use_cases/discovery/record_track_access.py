"""Use case for recording an explicit user track access event."""

from dataclasses import dataclass

from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
)
from app.domain.models.track_access import (
    VALID_TRACK_ACCESS_SOURCES,
    TrackAccess,
    TrackAccessSource,
)
lazy from app.application.ports.repositories.track_access_repository import (
    TrackAccessRepositoryPort,
)
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort


@dataclass(slots=True, frozen=True)
class RecordTrackAccessUseCase:
    """Validates eligibility and records a user track access event."""

    user_repo: UserRepositoryPort
    track_repo: TrackRepositoryPort
    track_access_repo: TrackAccessRepositoryPort

    def execute(
        self,
        user_id: int,
        track_id: int,
        source: TrackAccessSource | str = "play",
    ) -> TrackAccess:
        normalized_source = str(source).strip().lower()
        if normalized_source not in VALID_TRACK_ACCESS_SOURCES:
            raise BusinessRuleViolationError(f"Invalid track access source '{source}'.")

        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        track = self.track_repo.find_by_id(track_id)
        if not track or track.is_deleted:
            raise EntityNotFoundError(
                f"Track with ID {track_id} not found or inactive."
            )

        if user.is_track_restricted_for_minor(track):
            raise BusinessRuleViolationError("Track is restricted for minor users.")

        return self.track_access_repo.record(
            TrackAccess(
                user_id=user_id,
                track_id=track_id,
                source=normalized_source,
            )
        )
