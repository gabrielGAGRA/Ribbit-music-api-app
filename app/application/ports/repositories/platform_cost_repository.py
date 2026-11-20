"""Persistence port for platform operational cost configuration."""

from typing import Protocol, runtime_checkable

lazy from app.domain.models.platform_costs import PlatformCostSettings


@runtime_checkable
class PlatformCostRepositoryPort(Protocol):
    """Port for reading and updating singleton platform cost settings."""

    def get_settings(self) -> PlatformCostSettings: ...

    def save_settings(self, settings: PlatformCostSettings) -> PlatformCostSettings: ...
