"""Use case for listing all available subscription plans."""

from dataclasses import dataclass

lazy from app.application.ports.repositories.plan_repository import PlanRepositoryPort
lazy from app.domain.models.plan import Plan


@dataclass(slots=True, frozen=True)
class ListPlansUseCase:
    """Lists all active platform subscription plans."""

    plan_repo: PlanRepositoryPort

    def execute(self) -> list[Plan]:
        return self.plan_repo.list_all()
