"""Unit tests for platform cost settings, executive dashboard, and audience analytics."""

import pytest

from app.application.dtos.admin_dtos import UpdatePlatformCostsCommand
from app.application.use_cases.admin import (
    GetAudienceReportUseCase,
    GetExecutiveDashboardUseCase,
    GetPlatformCostsUseCase,
    UpdatePlatformCostsUseCase,
)
from app.domain.exceptions import BusinessRuleViolationError
from app.domain.models.plan import Plan
from app.domain.models.platform_costs import PlatformCostSettings
from app.domain.models.track import Track
from app.domain.models.track_access import TrackAccess
from app.domain.models.user import User
from app.domain.services import SubscriptionAnalyticsService
from app.infrastructure.repositories import (
    SQLitePlanRepository,
    SQLitePlatformCostRepository,
    SQLiteTrackAccessRepository,
    SQLiteTrackRepository,
    SQLiteUserRepository,
    create_connection,
)
from app.infrastructure.repositories.seed import migrate_additive_columns


def test_subscription_analytics_service_positive_and_negative_net_revenue() -> None:
    svc = SubscriptionAnalyticsService()
    free = Plan(
        plan_id=1, name="Free", initial_monthly_price=0.0, initial_max_profiles=1
    )
    pro = Plan(
        plan_id=2, name="Individual", initial_monthly_price=15.0, initial_max_profiles=1
    )
    users = [
        User(
            user_id=1,
            email="u1@example.com",
            password_hash="h",
            display_name="U1",
            age=25,
            plan_id=2,
        ),
        User(
            user_id=2,
            email="u2@example.com",
            password_hash="h",
            display_name="U2",
            age=26,
            plan_id=1,
        ),
    ]

    positive = svc.calculate_revenue_breakdown(
        users=users,
        plans=[free, pro],
        active_tracks_count=10,
        content_cost_per_track=0.10,
        infrastructure_fixed_cost=5.0,
        infrastructure_cost_per_user=0.5,
    )
    assert positive.gross_revenue == 15.0
    assert positive.content_cost == 1.0
    assert positive.infrastructure_cost == 6.0
    assert positive.total_costs == 7.0
    assert positive.estimated_net_revenue == 8.0

    negative = svc.calculate_revenue_breakdown(
        users=users,
        plans=[free, pro],
        active_tracks_count=500,
        content_cost_per_track=0.05,
        infrastructure_fixed_cost=10.0,
        infrastructure_cost_per_user=1.0,
    )
    assert negative.gross_revenue == 15.0
    assert negative.total_costs == 37.0
    assert negative.estimated_net_revenue == -22.0


def test_platform_cost_use_cases_and_validation() -> None:
    conn = create_connection(":memory:")
    migrate_additive_columns(conn)
    try:
        cost_repo = SQLitePlatformCostRepository(conn)
        get_uc = GetPlatformCostsUseCase(cost_repo)
        update_uc = UpdatePlatformCostsUseCase(cost_repo)

        defaults = get_uc.execute()
        assert defaults.content_cost_per_track == 0.04
        assert defaults.infrastructure_fixed_cost == 10.00
        assert defaults.infrastructure_cost_per_user == 0.50

        updated = update_uc.execute(
            UpdatePlatformCostsCommand(
                content_cost_per_track=0.08,
                infrastructure_fixed_cost=25.0,
                infrastructure_cost_per_user=1.25,
            )
        )
        assert updated.content_cost_per_track == 0.08
        assert get_uc.execute().infrastructure_fixed_cost == 25.0

        with pytest.raises(BusinessRuleViolationError):
            update_uc.execute(
                UpdatePlatformCostsCommand(
                    content_cost_per_track=-0.01,
                    infrastructure_fixed_cost=10.0,
                    infrastructure_cost_per_user=0.5,
                )
            )
        with pytest.raises(ValueError):
            PlatformCostSettings(infrastructure_fixed_cost=-1.0)
    finally:
        conn.close()


def test_executive_dashboard_and_audience_report_with_costs_and_accesses() -> None:
    conn = create_connection(":memory:")
    migrate_additive_columns(conn)
    try:
        user_repo = SQLiteUserRepository(conn)
        plan_repo = SQLitePlanRepository(conn)
        track_repo = SQLiteTrackRepository(conn)
        cost_repo = SQLitePlatformCostRepository(conn)
        access_repo = SQLiteTrackAccessRepository(conn)

        plan = plan_repo.save(
            Plan(name="Individual", initial_monthly_price=20.0, initial_max_profiles=1)
        )
        assert plan.plan_id is not None
        user = user_repo.save(
            User(
                email="buyer@example.com",
                password_hash="h",
                display_name="Buyer",
                age=25,
                plan_id=plan.plan_id,
            )
        )
        assert user.user_id is not None
        t1 = track_repo.save(
            Track(title="T1", artist="A1", duration_seconds=180, genre="Pop")
        )
        t2 = track_repo.save(
            Track(title="T2", artist="A2", duration_seconds=200, genre="Rock")
        )
        assert t1.track_id is not None and t2.track_id is not None

        cost_repo.save_settings(
            PlatformCostSettings(
                content_cost_per_track=1.0,
                infrastructure_fixed_cost=5.0,
                infrastructure_cost_per_user=2.0,
            )
        )

        dash_uc = GetExecutiveDashboardUseCase(
            user_repo, plan_repo, track_repo=track_repo, cost_repo=cost_repo
        )
        dash = dash_uc.execute()
        assert dash.gross_revenue == 20.0
        assert dash.content_cost == 2.0
        assert dash.infrastructure_cost == 7.0
        assert dash.total_costs == 9.0
        assert dash.estimated_net_revenue == 11.0
        assert dash.active_tracks_count == 2

        access_repo.record(
            TrackAccess(user_id=user.user_id, track_id=t1.track_id, source="play")
        )
        access_repo.record(
            TrackAccess(user_id=user.user_id, track_id=t1.track_id, source="details")
        )
        access_repo.record(
            TrackAccess(user_id=user.user_id, track_id=t2.track_id, source="search")
        )

        aud_uc = GetAudienceReportUseCase(
            user_repo, track_repo, track_access_repo=access_repo
        )
        aud = aud_uc.execute()
        assert aud.total_accesses == 3
        assert aud.accesses_by_track[0].track_id == t1.track_id
        assert aud.accesses_by_track[0].access_count == 2
        assert {g.genre: g.access_count for g in aud.accesses_by_genre} == {
            "Pop": 2,
            "Rock": 1,
        }
    finally:
        conn.close()
