"""Use case for calculating executive metrics and financial dashboard."""

from dataclasses import dataclass, field

from app.application.dtos.admin_dtos import ExecutiveDashboardResult
from app.domain.models.platform_costs import PlatformCostSettings
from app.domain.services import SubscriptionAnalyticsService
lazy from app.application.ports.repositories.plan_repository import PlanRepositoryPort
lazy from app.application.ports.repositories.platform_cost_repository import (
    PlatformCostRepositoryPort,
)
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort


@dataclass(slots=True, frozen=True)
class GetExecutiveDashboardUseCase:
    """Calculates financial metrics, operational costs, and subscriber distribution."""

    user_repo: UserRepositoryPort
    plan_repo: PlanRepositoryPort
    analytics_service: SubscriptionAnalyticsService = field(
        default_factory=SubscriptionAnalyticsService
    )
    track_repo: TrackRepositoryPort | None = None
    cost_repo: PlatformCostRepositoryPort | None = None

    def execute(self) -> ExecutiveDashboardResult:
        users = self.user_repo.list_all()
        plans = self.plan_repo.list_all()
        active_tracks_count = (
            self.track_repo.count_active() if self.track_repo is not None else 0
        )
        costs = (
            self.cost_repo.get_settings()
            if self.cost_repo is not None
            else PlatformCostSettings(
                content_cost_per_track=0.0,
                infrastructure_fixed_cost=0.0,
                infrastructure_cost_per_user=0.0,
            )
        )

        breakdown = self.analytics_service.calculate_revenue_breakdown(
            users=users,
            plans=plans,
            active_tracks_count=active_tracks_count,
            content_cost_per_track=costs.content_cost_per_track,
            infrastructure_fixed_cost=costs.infrastructure_fixed_cost,
            infrastructure_cost_per_user=costs.infrastructure_cost_per_user,
        )

        return ExecutiveDashboardResult(
            total_users=breakdown.total_users,
            estimated_net_revenue=breakdown.estimated_net_revenue,
            users_by_plan=breakdown.users_by_plan,
            revenue_by_plan=breakdown.revenue_by_plan,
            gross_revenue=breakdown.gross_revenue,
            content_cost=breakdown.content_cost,
            infrastructure_cost=breakdown.infrastructure_cost,
            total_costs=breakdown.total_costs,
            active_tracks_count=breakdown.active_tracks_count,
            content_cost_per_track=costs.content_cost_per_track,
            infrastructure_fixed_cost=costs.infrastructure_fixed_cost,
            infrastructure_cost_per_user=costs.infrastructure_cost_per_user,
        )
