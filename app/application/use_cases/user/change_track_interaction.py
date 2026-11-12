"""Use case for changing a track swipe interaction by a Premium user."""

from dataclasses import dataclass

from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    PermissionDeniedError,
)
lazy from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
lazy from app.application.ports.repositories.plan_repository import PlanRepositoryPort
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.interaction import (
    Interaction,
    InteractionAction,
    InteractionSource,
)


@dataclass(slots=True, frozen=True)
class ChangeTrackInteractionUseCase:
    """Allows Premium subscribers to revise previous swipe gestures on tracks."""

    user_repo: UserRepositoryPort
    plan_repo: PlanRepositoryPort
    interaction_repo: InteractionRepositoryPort
    track_repo: TrackRepositoryPort | None = None

    def execute(
        self, user_id: int, track_id: int, new_action: InteractionAction
    ) -> Interaction:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        plan = self.plan_repo.find_by_id(user.plan_id)
        if not plan or not plan.is_paid:
            raise PermissionDeniedError("Feature exclusive to Premium subscribers.")

        if self.track_repo is not None:
            track = self.track_repo.find_by_id(track_id)
            if not track or track.is_deleted:
                raise EntityNotFoundError("Track not found or inactive.")
            if user.is_track_restricted_for_minor(track):
                raise BusinessRuleViolationError("Track is restricted for minor users.")

        interaction = self.interaction_repo.find_by_user_and_track(user_id, track_id)
        if not interaction:
            raise EntityNotFoundError("Interaction for this track was not found.")

        interaction.change_action(new_action)
        interaction.source = InteractionSource.PROFILE
        return self.interaction_repo.save(interaction)


__all__ = ["ChangeTrackInteractionUseCase"]
