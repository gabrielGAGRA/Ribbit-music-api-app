"""Use case for listing blocked music genres for a user."""

from dataclasses import dataclass

from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    PermissionDeniedError,
)
lazy from app.application.ports.repositories.plan_repository import PlanRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort


class PremiumRequiredError(BusinessRuleViolationError, PermissionDeniedError):
    """Raised when an operation requires a paid subscription plan."""


@dataclass(slots=True, frozen=True)
class ListBlockedGenresUseCase:
    """Lists all blocked genres configured on a user's profile."""

    user_repo: UserRepositoryPort
    plan_repo: PlanRepositoryPort | None = None

    def execute(self, user_id: int) -> list[str]:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        if self.plan_repo is not None:
            plan = self.plan_repo.find_by_id(user.plan_id)
            if not plan or not plan.is_paid:
                raise PremiumRequiredError("Feature exclusive to Premium subscribers.")

        return sorted(user.blocked_genres)
