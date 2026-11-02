"""Use case for calculating executive metrics and financial dashboard."""

from dataclasses import dataclass, field

from app.application.dtos.admin_dtos import ExecutiveDashboardResult
from app.domain.services import SubscriptionAnalyticsService
lazy from app.application.ports.repositories.plan_repository import PlanRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort


@dataclass(slots=True, frozen=True)
class GetExecutiveDashboardUseCase:
    """Calculates financial metrics and subscriber distribution."""

    user_repo: UserRepositoryPort
    plan_repo: PlanRepositoryPort
    analytics_service: SubscriptionAnalyticsService = field(
        default_factory=SubscriptionAnalyticsService
    )

    def execute(self) -> ExecutiveDashboardResult:
        users = self.user_repo.list_all()
        plans = self.plan_repo.list_all()

        breakdown = self.analytics_service.calculate_revenue_breakdown(
            users=users,
            plans=plans,
        )

        return ExecutiveDashboardResult(
            total_users=breakdown.total_users,
            estimated_net_revenue=breakdown.estimated_net_revenue,
            users_by_plan=breakdown.users_by_plan,
            revenue_by_plan=breakdown.revenue_by_plan,
        )
