"""Domain service calculating platform-level subscription and revenue analytics."""

from dataclasses import dataclass
lazy from collections.abc import Sequence

lazy from app.domain.models.plan import Plan
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True, kw_only=True)
class RevenueBreakdown:
    total_users: int
    estimated_net_revenue: float
    users_by_plan: dict[str, int]
    revenue_by_plan: dict[str, float]
    gross_revenue: float = 0.0
    content_cost: float = 0.0
    infrastructure_cost: float = 0.0
    total_costs: float = 0.0
    active_tracks_count: int = 0


@dataclass(slots=True, frozen=True)
class SubscriptionAnalyticsService:
    """Encapsulates cross-entity billing calculations and plan distribution."""

    def calculate_revenue_breakdown(
        self,
        *,
        users: Sequence[User],
        plans: Sequence[Plan],
        active_tracks_count: int = 0,
        content_cost_per_track: float = 0.0,
        infrastructure_fixed_cost: float = 0.0,
        infrastructure_cost_per_user: float = 0.0,
    ) -> RevenueBreakdown:
        plan_map = {p.plan_id: p for p in plans if p.plan_id is not None}

        total_revenue = 0.0
        users_by_plan: dict[str, int] = {p.name: 0 for p in plans}
        revenue_by_plan: dict[str, float] = {p.name: 0.0 for p in plans}

        for user in users:
            plan = plan_map.get(user.plan_id)
            if plan:
                users_by_plan[plan.name] = users_by_plan.get(plan.name, 0) + 1
                if user.primary_account_id is None and not user.is_admin:
                    total_revenue += plan.monthly_price
                    revenue_by_plan[plan.name] = (
                        revenue_by_plan.get(plan.name, 0.0) + plan.monthly_price
                    )

        gross_revenue = round(total_revenue, 2)
        content_cost = round(active_tracks_count * content_cost_per_track, 2)
        infrastructure_cost = round(
            infrastructure_fixed_cost + len(users) * infrastructure_cost_per_user, 2
        )
        total_costs = round(content_cost + infrastructure_cost, 2)
        estimated_net_revenue = round(gross_revenue - total_costs, 2)

        return RevenueBreakdown(
            total_users=len(users),
            estimated_net_revenue=estimated_net_revenue,
            users_by_plan=users_by_plan,
            revenue_by_plan={k: round(v, 2) for k, v in revenue_by_plan.items()},
            gross_revenue=gross_revenue,
            content_cost=content_cost,
            infrastructure_cost=infrastructure_cost,
            total_costs=total_costs,
            active_tracks_count=active_tracks_count,
        )


__all__ = ["RevenueBreakdown", "SubscriptionAnalyticsService"]
