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
    """Updates blocked music genre filters for a Premium user or family dependent."""

    user_repo: UserRepositoryPort
    plan_repo: PlanRepositoryPort

    def execute(self, user_id: int, blocked_genres: Sequence[str]) -> User:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        plan = self.plan_repo.find_by_id(user.plan_id)
        if not user.has_premium_access(plan):
            raise PremiumRequiredError("Feature exclusive to Premium subscribers.")

        user.update_blocked_genres(blocked_genres)
        return self.user_repo.save(user)

    def execute_for_dependent(
        self,
        primary_user_id: int,
        dependent_user_id: int,
        blocked_genres: Sequence[str],
    ) -> User:
        primary_user = self.user_repo.find_by_id(primary_user_id)
        if not primary_user:
            raise EntityNotFoundError(
                f"Primary user with ID {primary_user_id} not found."
            )
        if primary_user.primary_account_id is not None:
            raise PermissionDeniedError(
                "A dependent user cannot manage family members."
            )

        plan = self.plan_repo.find_by_id(primary_user.plan_id)
        if not primary_user.has_family_access(plan):
            raise PermissionDeniedError("Current plan does not support family members.")

        dependent = self.user_repo.find_by_id(dependent_user_id)
        if not dependent:
            raise EntityNotFoundError(f"Dependent user {dependent_user_id} not found.")
        if dependent.primary_account_id != primary_user_id:
            raise PermissionDeniedError(
                "This profile does not belong to your family account."
            )

        dependent.update_blocked_genres(blocked_genres)
        return self.user_repo.save(dependent)
