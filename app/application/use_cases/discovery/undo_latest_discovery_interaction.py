"""Use case for undoing a user's latest discovery swipe."""

from dataclasses import dataclass

from app.domain.exceptions import (
    EntityNotFoundError,
    PermissionDeniedError,
)
lazy from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
lazy from app.application.ports.repositories.plan_repository import PlanRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.interaction import Interaction


@dataclass(slots=True, frozen=True)
class UndoLatestDiscoveryInteractionUseCase:
    """Allows paid subscribers to undo their latest discovery swipe."""

    user_repo: UserRepositoryPort
    plan_repo: PlanRepositoryPort
    interaction_repo: InteractionRepositoryPort

    def execute(self, user_id: int) -> Interaction:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        plan = self.plan_repo.find_by_id(user.plan_id)
        if not plan or not plan.is_paid:
            raise PermissionDeniedError("Feature exclusive to Premium subscribers.")

        interaction = self.interaction_repo.delete_latest_discovery(user_id)
        if interaction is None:
            raise EntityNotFoundError("No discovery interaction is available to undo.")
        return interaction


__all__ = ["UndoLatestDiscoveryInteractionUseCase"]
