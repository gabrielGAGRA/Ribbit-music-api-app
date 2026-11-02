"""Use case for updating blocked music genres for a user."""

from dataclasses import dataclass
lazy from collections.abc import Sequence

from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    PermissionDeniedError,
)
lazy from app.application.ports.repositories.plan_repository import PlanRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.user import User


class PremiumRequiredError(BusinessRuleViolationError, PermissionDeniedError):
    """Raised when an operation requires a paid subscription plan."""


@dataclass(slots=True, frozen=True)
class UpdateBlockedGenresUseCase:
    """Updates blocked music genre filters for a Premium user."""

    user_repo: UserRepositoryPort
    plan_repo: PlanRepositoryPort

    def execute(self, user_id: int, blocked_genres: Sequence[str]) -> User:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        plan = self.plan_repo.find_by_id(user.plan_id)
        if not plan or not plan.is_paid:
            raise PremiumRequiredError("Feature exclusive to Premium subscribers.")

        user.update_blocked_genres(blocked_genres)
        return self.user_repo.save(user)
