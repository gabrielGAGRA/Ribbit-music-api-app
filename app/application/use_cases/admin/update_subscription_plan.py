"""Use case for updating subscription plan prices and parameters."""

from dataclasses import dataclass

from app.domain.exceptions import (
    BusinessRuleViolationError,
    DuplicateEntityError,
    EntityNotFoundError,
)
lazy from app.application.dtos.admin_dtos import (
    UpdateSubscriptionPlanCommand,
)
lazy from app.application.ports.repositories.plan_repository import PlanRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.plan import Plan


@dataclass(slots=True, frozen=True)
class UpdateSubscriptionPlanUseCase:
    """Modifies pricing, names, or profile quotas on existing plans with capacity constraints."""

    plan_repo: PlanRepositoryPort
    user_repo: UserRepositoryPort | None = None

    def _validate_max_profiles_capacity(self, plan_id: int, max_profiles: int) -> None:
        if self.user_repo is None:
            return
        for user in self.user_repo.list_all():
            if (
                user.plan_id == plan_id
                and user.primary_account_id is None
                and user.user_id is not None
            ):
                dependents = self.user_repo.list_dependents(user.user_id)
                if len(dependents) + 1 > max_profiles:
                    raise BusinessRuleViolationError(
                        "O limite não pode ser menor que os perfis já vinculados."
                    )

    def execute(self, command: UpdateSubscriptionPlanCommand) -> Plan:
        plan = self.plan_repo.find_by_id(command.plan_id)
        if not plan:
            raise EntityNotFoundError(f"Plan {command.plan_id} not found.")

        if command.new_price is not None:
            plan.update_price(command.new_price)

        if command.new_name is not None:
            cleaned = command.new_name.strip()
            if not cleaned:
                raise BusinessRuleViolationError("O nome do plano é obrigatório.")
            existing = self.plan_repo.find_by_name(cleaned)
            if (
                existing is not None
                and isinstance(getattr(existing, "plan_id", None), int)
                and existing.plan_id != command.plan_id
            ):
                raise DuplicateEntityError("Já existe um plano com esse nome.")
            plan.update_name(cleaned)

        if command.max_profiles is not None:
            self._validate_max_profiles_capacity(command.plan_id, command.max_profiles)
            plan.update_max_profiles(command.max_profiles)

        return self.plan_repo.save(plan)


__all__ = ["UpdateSubscriptionPlanUseCase"]
