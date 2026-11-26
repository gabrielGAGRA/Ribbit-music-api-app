"""Use case for recording user swipe interactions."""

from dataclasses import dataclass

from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
)
from app.domain.models.interaction import (
    Interaction,
    InteractionAction,
    InteractionSource,
)
from app.domain.models.track_access import TrackAccess
lazy from app.application.dtos.discovery_dtos import RecordSwipeCommand
lazy from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
lazy from app.application.ports.repositories.track_access_repository import (
    TrackAccessRepositoryPort,
)
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort


@dataclass(slots=True, frozen=True)
class RecordSwipeInteractionUseCase:
    """Records user gesture interactions (like, superlike, dislike) on tracks."""

    user_repo: UserRepositoryPort
    track_repo: TrackRepositoryPort
    interaction_repo: InteractionRepositoryPort
    track_access_repo: TrackAccessRepositoryPort | None = None

    def execute(self, command: RecordSwipeCommand) -> Interaction:
        user = self.user_repo.find_by_id(command.user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {command.user_id} not found.")

        track = self.track_repo.find_by_id(command.track_id)
        if not track or track.is_deleted:
            raise EntityNotFoundError(
                f"Track with ID {command.track_id} not found or inactive."
            )

        if user.is_track_restricted_for_minor(track):
            raise BusinessRuleViolationError("Track is restricted for minor users.")

        if not user.can_listen(track):
            raise BusinessRuleViolationError("Genre is blocked by user.")

        try:
            action_enum = InteractionAction.parse(command.action)
        except ValueError as exc:
            raise BusinessRuleViolationError(
                f"Invalid action '{command.action}'. Valid: like, superlike, dislike."
            ) from exc

        interaction = Interaction(
            interaction_id=None,
            user_id=command.user_id,
            track_id=command.track_id,
            action=action_enum,
            source=InteractionSource.DISCOVERY,
        )
        saved = self.interaction_repo.save(interaction)
        if self.track_access_repo is not None:
            self.track_access_repo.record(
                TrackAccess(
                    user_id=command.user_id,
                    track_id=command.track_id,
                    source="swipe",
                )
            )
        return saved
