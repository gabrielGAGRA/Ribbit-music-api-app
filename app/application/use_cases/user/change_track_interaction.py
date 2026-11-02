"""Use case for changing a track swipe interaction by a Premium user."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError
lazy from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
lazy from app.application.ports.repositories.plan_repository import PlanRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.interaction import Interaction, InteractionAction


@dataclass(slots=True, frozen=True)
class ChangeTrackInteractionUseCase:
    """Allows Premium subscribers to revise previous swipe gestures on tracks."""

    user_repo: UserRepositoryPort
    plan_repo: PlanRepositoryPort
    interaction_repo: InteractionRepositoryPort

    def execute(
        self, user_id: int, track_id: int, new_action: InteractionAction
    ) -> Interaction:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        plan = self.plan_repo.find_by_id(user.plan_id)
        if not plan or not plan.is_paid:
            raise PermissionDeniedError("Feature exclusive to Premium subscribers.")

        interaction = self.interaction_repo.find_by_user_and_track(user_id, track_id)
        if not interaction:
            raise EntityNotFoundError("Interaction for this track was not found.")

        interaction.change_action(new_action)
        return self.interaction_repo.save(interaction)
