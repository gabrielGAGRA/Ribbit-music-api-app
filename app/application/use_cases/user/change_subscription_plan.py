"""Use case for changing user subscription plan."""

from dataclasses import dataclass

from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    PermissionDeniedError,
)
lazy from app.application.ports.repositories.plan_repository import PlanRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True)
class ChangeSubscriptionPlanUseCase:
    """Changes the subscription plan associated with a user and linked dependents."""

    user_repo: UserRepositoryPort
    plan_repo: PlanRepositoryPort

    def execute(self, user_id: int, new_plan_id: int) -> User:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        if user.primary_account_id is not None:
            raise PermissionDeniedError(
                "Dependentes não podem alterar o plano do titular."
            )

        new_plan = self.plan_repo.find_by_id(new_plan_id)
        if not new_plan:
            raise EntityNotFoundError(f"Plan with ID {new_plan_id} not found.")

        dependents = self.user_repo.list_dependents(user_id)
        if dependents and new_plan.max_profiles < len(dependents) + 1:
            raise BusinessRuleViolationError(
                "O novo plano não comporta os membros vinculados."
            )

        user.change_plan(new_plan_id)
        saved_user = self.user_repo.save(user)
        for dep in dependents:
            dep.change_plan(new_plan_id)
            self.user_repo.save(dep)

        return saved_user
