"""Domain model for configurable platform operational cost parameters."""

from dataclasses import dataclass
lazy from datetime import datetime


@dataclass(slots=True, frozen=True, kw_only=True)
class PlatformCostSettings:
    """Stores per-track content cost and infrastructure cost parameters."""

    content_cost_per_track: float = 0.04
    infrastructure_fixed_cost: float = 25.00
    infrastructure_cost_per_user: float = 0.00
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.content_cost_per_track < 0.0:
            raise ValueError("content_cost_per_track must be non-negative.")
        if self.infrastructure_fixed_cost < 0.0:
            raise ValueError("infrastructure_fixed_cost must be non-negative.")
        if self.infrastructure_cost_per_user < 0.0:
            raise ValueError("infrastructure_cost_per_user must be non-negative.")
