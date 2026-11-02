"""Use case for deleting a user account."""

from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError
lazy from app.application.ports.repositories.plan_repository import PlanRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.plan import Plan


@dataclass(slots=True, frozen=True)
class DeleteUserAccountUseCase:
    """Deletes a user account and associated personal settings."""

    user_repo: UserRepositoryPort
    plan_repo: PlanRepositoryPort | None = None

    def execute(self, user_id: int) -> bool:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        dependents = self.user_repo.list_dependents(user_id)
        if dependents and self.plan_repo is not None:
            free_plan = self.plan_repo.find_by_name(Plan.DEFAULT_FREE_PLAN_NAME)
            if not free_plan or free_plan.plan_id is None:
                raise EntityNotFoundError("Default Free plan not found.")
            for dep in dependents:
                dep.unlink_primary_account(free_plan.plan_id)
                self.user_repo.save(dep)

        return self.user_repo.delete(user_id)
