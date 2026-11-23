"""Use case for updating platform operational cost settings."""

from dataclasses import dataclass

from app.domain.exceptions import BusinessRuleViolationError
from app.domain.models.platform_costs import PlatformCostSettings
lazy from app.application.dtos.admin_dtos import UpdatePlatformCostsCommand
lazy from app.application.ports.repositories.platform_cost_repository import (
    PlatformCostRepositoryPort,
)


@dataclass(slots=True, frozen=True)
class UpdatePlatformCostsUseCase:
    """Validates and persists updated platform cost parameters."""

    cost_repo: PlatformCostRepositoryPort

    def execute(self, command: UpdatePlatformCostsCommand) -> PlatformCostSettings:
        try:
            settings = PlatformCostSettings(
                content_cost_per_track=command.content_cost_per_track,
                infrastructure_fixed_cost=command.infrastructure_fixed_cost,
                infrastructure_cost_per_user=command.infrastructure_cost_per_user,
            )
        except ValueError as exc:
            raise BusinessRuleViolationError(str(exc)) from exc
        return self.cost_repo.save_settings(settings)
