"""Use case for retrieving user profile and active subscription plan."""

from dataclasses import dataclass

from app.application.dtos.user_dtos import UserProfileResult
from app.domain.exceptions import EntityNotFoundError
lazy from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
lazy from app.application.ports.repositories.plan_repository import PlanRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.interaction import Interaction


@dataclass(slots=True, frozen=True)
class GetUserProfileUseCase:
    """Retrieves full profile details for a given user alongside their plan."""

    user_repo: UserRepositoryPort
    plan_repo: PlanRepositoryPort
    interaction_repo: InteractionRepositoryPort | None = None

    def execute(self, user_id: int) -> UserProfileResult:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        plan = self.plan_repo.find_by_id(user.plan_id)
        if not plan:
            raise EntityNotFoundError(f"Plan with ID {user.plan_id} not found.")

        recent_interactions: list[Interaction] = []
        if self.interaction_repo is not None:
            recent_interactions = list(self.interaction_repo.list_by_user(user_id)[:5])

        return UserProfileResult(
            user=user,
            plan=plan,
            recent_interactions=recent_interactions,
        )
