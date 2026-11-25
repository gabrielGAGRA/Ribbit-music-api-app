"""Domain service calculating platform-level subscription and revenue analytics."""

from dataclasses import dataclass, field
lazy from collections.abc import Sequence

lazy from app.domain.models.plan import Plan
lazy from app.domain.models.user import User

FIRESTORE_FREE_READS_PER_DAY = 50_000
FIRESTORE_FREE_WRITES_PER_DAY = 20_000
FIRESTORE_FREE_DELETES_PER_DAY = 20_000
FIRESTORE_FREE_STORAGE_GIB = 1.0
FIRESTORE_FREE_EGRESS_GIB_MONTH = 10.0

FIRESTORE_READ_COST_PER_100K = 0.06
FIRESTORE_WRITE_COST_PER_100K = 0.18
FIRESTORE_DELETE_COST_PER_100K = 0.02
FIRESTORE_STORAGE_COST_PER_GIB_MONTH = 0.18
FIRESTORE_EGRESS_COST_PER_GIB = 0.12

_BYTES_PER_GIB = 1024**3


@dataclass(slots=True, frozen=True, kw_only=True)
class FirestoreUsageMetrics:
    """Raw Firestore operation and storage counters."""

    reads_today: int = 0
    writes_today: int = 0
    deletes_today: int = 0
    stored_bytes: int = 0
    egress_bytes_month: int = 0


@dataclass(slots=True, frozen=True, kw_only=True)
class FirestoreQuotaSummary:
    """Firestore usage vs free-tier quotas and projected monthly USD cost."""

    reads_today: int = 0
    reads_free_limit: int = FIRESTORE_FREE_READS_PER_DAY
    reads_percent: float = 0.0
    reads_rate_per_100k: float = FIRESTORE_READ_COST_PER_100K
    writes_today: int = 0
    writes_free_limit: int = FIRESTORE_FREE_WRITES_PER_DAY
    writes_percent: float = 0.0
    writes_rate_per_100k: float = FIRESTORE_WRITE_COST_PER_100K
    deletes_today: int = 0
    deletes_free_limit: int = FIRESTORE_FREE_DELETES_PER_DAY
    deletes_percent: float = 0.0
    deletes_rate_per_100k: float = FIRESTORE_DELETE_COST_PER_100K
    stored_bytes: int = 0
    stored_gib: float = 0.0
    stored_free_limit_gib: float = FIRESTORE_FREE_STORAGE_GIB
    stored_percent: float = 0.0
    egress_bytes_month: int = 0
    egress_gib_month: float = 0.0
    egress_free_limit_gib: float = FIRESTORE_FREE_EGRESS_GIB_MONTH
    egress_percent: float = 0.0
    monthly_estimated_cost: float = 0.0


def _quota_percent(used: float, limit: float) -> float:
    if limit <= 0:
        return 0.0
    return min(100.0, round((max(0.0, used) / limit) * 100.0, 2))


def calculate_firestore_content_cost(
    usage: FirestoreUsageMetrics,
) -> FirestoreQuotaSummary:
    """Computes Firestore free-tier utilization % and projected monthly USD cost."""
    reads_today = max(0, usage.reads_today)
    writes_today = max(0, usage.writes_today)
    deletes_today = max(0, usage.deletes_today)
    stored_bytes = max(0, usage.stored_bytes)
    egress_bytes_month = max(0, usage.egress_bytes_month)
    raw_stored_gib = stored_bytes / _BYTES_PER_GIB
    raw_egress_gib = egress_bytes_month / _BYTES_PER_GIB
    stored_gib = round(raw_stored_gib, 6)
    egress_gib_month = round(raw_egress_gib, 6)

    daily_reads_overage = max(0, reads_today - FIRESTORE_FREE_READS_PER_DAY)
    daily_writes_overage = max(0, writes_today - FIRESTORE_FREE_WRITES_PER_DAY)
    daily_deletes_overage = max(0, deletes_today - FIRESTORE_FREE_DELETES_PER_DAY)

    daily_ops_cost = (
        (daily_reads_overage / 100_000.0) * FIRESTORE_READ_COST_PER_100K
        + (daily_writes_overage / 100_000.0) * FIRESTORE_WRITE_COST_PER_100K
        + (daily_deletes_overage / 100_000.0) * FIRESTORE_DELETE_COST_PER_100K
    )
    storage_cost = (
        max(0.0, raw_stored_gib - FIRESTORE_FREE_STORAGE_GIB)
        * FIRESTORE_STORAGE_COST_PER_GIB_MONTH
    )
    egress_cost = (
        max(0.0, raw_egress_gib - FIRESTORE_FREE_EGRESS_GIB_MONTH)
        * FIRESTORE_EGRESS_COST_PER_GIB
    )
    monthly_estimated_cost = round(
        daily_ops_cost * 30.0 + storage_cost + egress_cost, 2
    )

    return FirestoreQuotaSummary(
        reads_today=reads_today,
        reads_percent=_quota_percent(reads_today, FIRESTORE_FREE_READS_PER_DAY),
        writes_today=writes_today,
        writes_percent=_quota_percent(writes_today, FIRESTORE_FREE_WRITES_PER_DAY),
        deletes_today=deletes_today,
        deletes_percent=_quota_percent(deletes_today, FIRESTORE_FREE_DELETES_PER_DAY),
        stored_bytes=stored_bytes,
        stored_gib=stored_gib,
        stored_percent=_quota_percent(raw_stored_gib, FIRESTORE_FREE_STORAGE_GIB),
        egress_bytes_month=egress_bytes_month,
        egress_gib_month=egress_gib_month,
        egress_percent=_quota_percent(raw_egress_gib, FIRESTORE_FREE_EGRESS_GIB_MONTH),
        monthly_estimated_cost=monthly_estimated_cost,
    )


@dataclass(slots=True, frozen=True, kw_only=True)
class RevenueBreakdown:
    total_users: int
    estimated_net_revenue: float
    users_by_plan: dict[str, int]
    revenue_by_plan: dict[str, float]
    profit_by_plan: dict[str, float] = field(default_factory=dict)
    paid_plans_revenue: float = 0.0
    paid_plans_profit: float = 0.0
    cost_to_revenue_percent: float = 0.0
    gross_revenue: float = 0.0
    content_cost: float = 0.0
    infrastructure_cost: float = 0.0
    total_costs: float = 0.0
    active_tracks_count: int = 0
    firestore_usage: FirestoreQuotaSummary | None = None


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
        firestore_usage: FirestoreUsageMetrics | None = None,
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
        quota_summary = (
            calculate_firestore_content_cost(firestore_usage)
            if firestore_usage is not None
            else None
        )
        content_cost = (
            quota_summary.monthly_estimated_cost
            if quota_summary is not None
            else round(active_tracks_count * content_cost_per_track, 2)
        )
        total_users = len(users)
        infrastructure_cost = round(
            infrastructure_fixed_cost + total_users * infrastructure_cost_per_user, 2
        )
        total_costs = round(content_cost + infrastructure_cost, 2)
        estimated_net_revenue = round(gross_revenue - total_costs, 2)

        rounded_revenue_by_plan = {k: round(v, 2) for k, v in revenue_by_plan.items()}
        profit_by_plan: dict[str, float] = {}
        paid_plans_revenue = 0.0
        paid_plans_profit = 0.0
        for plan in plans:
            plan_rev = rounded_revenue_by_plan.get(plan.name, 0.0)
            if plan.monthly_price > 0:
                user_share = (
                    (users_by_plan.get(plan.name, 0) / total_users)
                    if total_users > 0
                    else 0.0
                )
                allocated_cost = total_costs * user_share
                plan_profit = round(plan_rev - allocated_cost, 2)
                profit_by_plan[plan.name] = plan_profit
                paid_plans_revenue += plan_rev
                paid_plans_profit += plan_profit
            else:
                profit_by_plan[plan.name] = 0.0

        cost_to_revenue_percent = (
            round((total_costs / gross_revenue) * 100.0, 1)
            if gross_revenue > 0
            else (100.0 if total_costs > 0 else 0.0)
        )

        return RevenueBreakdown(
            total_users=total_users,
            estimated_net_revenue=estimated_net_revenue,
            users_by_plan=users_by_plan,
            revenue_by_plan=rounded_revenue_by_plan,
            profit_by_plan=profit_by_plan,
            paid_plans_revenue=round(paid_plans_revenue, 2),
            paid_plans_profit=round(paid_plans_profit, 2),
            cost_to_revenue_percent=cost_to_revenue_percent,
            gross_revenue=gross_revenue,
            content_cost=content_cost,
            infrastructure_cost=infrastructure_cost,
            total_costs=total_costs,
            active_tracks_count=active_tracks_count,
            firestore_usage=quota_summary,
        )


__all__ = [
    "FirestoreQuotaSummary",
    "FirestoreUsageMetrics",
    "RevenueBreakdown",
    "SubscriptionAnalyticsService",
    "calculate_firestore_content_cost",
]
