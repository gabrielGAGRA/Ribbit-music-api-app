"""Use case for cancelling a subscription plan and unlinking dependents."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError
from app.domain.models.plan import Plan
lazy from app.application.ports.repositories.plan_repository import PlanRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True)
class CancelSubscriptionPlanUseCase:
    """Cancels a paid subscription plan, reverting user and dependents to Free."""

    user_repo: UserRepositoryPort
    plan_repo: PlanRepositoryPort

    def execute(self, user_id: int) -> User:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        if user.primary_account_id is not None:
            raise PermissionDeniedError(
                "Dependentes não podem cancelar o plano do titular."
            )

        free_plan = self.plan_repo.find_by_name(Plan.DEFAULT_FREE_PLAN_NAME)
        if not free_plan or free_plan.plan_id is None:
            raise EntityNotFoundError("Default Free plan not found.")

        user.change_plan(free_plan.plan_id)
        saved_user = self.user_repo.save(user)
        for dep in self.user_repo.list_dependents(user_id):
            dep.unlink_primary_account(free_plan.plan_id)
            self.user_repo.save(dep)

        return saved_user
