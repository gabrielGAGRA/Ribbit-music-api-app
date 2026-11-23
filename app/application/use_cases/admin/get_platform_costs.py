"""Use case for retrieving current platform operational cost settings."""

from dataclasses import dataclass

lazy from app.application.ports.repositories.platform_cost_repository import (
    PlatformCostRepositoryPort,
)
lazy from app.domain.models.platform_costs import PlatformCostSettings


@dataclass(slots=True, frozen=True)
class GetPlatformCostsUseCase:
    """Returns the current configurable platform operational cost settings."""

    cost_repo: PlatformCostRepositoryPort

    def execute(self) -> PlatformCostSettings:
        return self.cost_repo.get_settings()
