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
from app.domain.services import (
    FirestoreUsageMetrics,
    SubscriptionAnalyticsService,
    calculate_firestore_content_cost,
)
from app.infrastructure.repositories import (
    FirestoreUsageTracker,
    SQLitePlanRepository,
    SQLitePlatformCostRepository,
    SQLiteTrackAccessRepository,
    SQLiteTrackRepository,
    SQLiteUserRepository,
    create_connection,
)
from app.infrastructure.repositories.seed import (
    _seed_platform_costs,
    migrate_additive_columns,
)


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
        assert defaults.infrastructure_fixed_cost == 25.00
        assert defaults.infrastructure_cost_per_user == 0.00

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


def test_firestore_content_cost_free_tier_and_overage_plus_paid_plan_profit() -> None:
    within_free = calculate_firestore_content_cost(
        FirestoreUsageMetrics(
            reads_today=25_000,
            writes_today=10_000,
            deletes_today=5_000,
            stored_bytes=512 * 1024 * 1024,
            egress_bytes_month=2 * 1024**3,
        )
    )
    assert within_free.reads_percent == 50.0
    assert within_free.writes_percent == 50.0
    assert within_free.deletes_percent == 25.0
    assert within_free.stored_percent == 50.0
    assert within_free.egress_percent == 20.0
    assert within_free.monthly_estimated_cost == 0.0

    # Overage: +100k reads ($0.06/day), +100k writes ($0.18/day), +100k deletes ($0.02/day)
    # = $0.26/day * 30 = $7.80/month
    overage_usage = FirestoreUsageMetrics(
        reads_today=150_000,
        writes_today=120_000,
        deletes_today=120_000,
        stored_bytes=1024**3,
        egress_bytes_month=10 * 1024**3,
    )
    svc = SubscriptionAnalyticsService()
    free = Plan(
        plan_id=1, name="Free", initial_monthly_price=0.0, initial_max_profiles=1
    )
    pro = Plan(
        plan_id=2, name="Individual", initial_monthly_price=20.0, initial_max_profiles=1
    )
    fam = Plan(
        plan_id=3, name="Família", initial_monthly_price=35.0, initial_max_profiles=4
    )
    users = [
        User(
            user_id=1,
            email="f@example.com",
            password_hash="h",
            display_name="F",
            age=25,
            plan_id=1,
        ),
        User(
            user_id=2,
            email="p1@example.com",
            password_hash="h",
            display_name="P1",
            age=25,
            plan_id=2,
        ),
        User(
            user_id=3,
            email="p2@example.com",
            password_hash="h",
            display_name="P2",
            age=25,
            plan_id=2,
        ),
        User(
            user_id=4,
            email="fam@example.com",
            password_hash="h",
            display_name="Fam",
            age=25,
            plan_id=3,
        ),
    ]
    breakdown = svc.calculate_revenue_breakdown(
        users=users,
        plans=[free, pro, fam],
        infrastructure_fixed_cost=25.0,
        infrastructure_cost_per_user=0.0,
        firestore_usage=overage_usage,
    )
    assert breakdown.content_cost == 7.8
    assert breakdown.infrastructure_cost == 25.0
    assert breakdown.total_costs == 32.8
    assert breakdown.gross_revenue == 75.0
    # Individual has 2/4 users -> allocated 16.40 -> profit 40.0 - 16.40 = 23.60
    # Família has 1/4 users -> allocated 8.20 -> profit 35.0 - 8.20 = 26.80
    assert breakdown.profit_by_plan["Free"] == 0.0
    assert breakdown.profit_by_plan["Individual"] == 23.6
    assert breakdown.profit_by_plan["Família"] == 26.8
    assert breakdown.paid_plans_revenue == 75.0
    assert breakdown.paid_plans_profit == 50.4
    assert breakdown.cost_to_revenue_percent == 43.7


def test_seed_platform_costs_upgrades_legacy_seed_and_preserves_custom_edits() -> None:
    conn = create_connection(":memory:")
    migrate_additive_columns(conn)
    try:
        conn.execute(
            """
            INSERT INTO platform_cost_settings (
                settings_id, content_cost_per_track, infrastructure_fixed_cost,
                infrastructure_cost_per_user, updated_at
            ) VALUES (1, 0.04, 10.00, 0.50, '1970-01-01T00:00:00+00:00')
            """
        )
        conn.commit()

        _seed_platform_costs(conn, "1970-01-01T00:00:00+00:00")
        upgraded = SQLitePlatformCostRepository(conn).get_settings()
        assert upgraded.infrastructure_fixed_cost == 25.00
        assert upgraded.infrastructure_cost_per_user == 0.00

        # Manually edited settings (non-seed updated_at) must not be overwritten
        conn.execute(
            """
            UPDATE platform_cost_settings
            SET infrastructure_fixed_cost = 42.00,
                infrastructure_cost_per_user = 0.25,
                updated_at = '2026-11-25T10:00:00+00:00'
            WHERE settings_id = 1
            """
        )
        conn.commit()
        _seed_platform_costs(conn, "1970-01-01T00:00:00+00:00")
        preserved = SQLitePlatformCostRepository(conn).get_settings()
        assert preserved.infrastructure_fixed_cost == 42.00
        assert preserved.infrastructure_cost_per_user == 0.25
    finally:
        conn.close()


def test_firestore_usage_tracker_records_flushes_and_persists_across_restarts() -> None:
    conn = create_connection(":memory:")
    migrate_additive_columns(conn)
    try:
        tracker1 = FirestoreUsageTracker()
        tracker1.record_sql_statement("SELECT * FROM users WHERE email = ?")
        tracker1.record_sql_statement("INSERT INTO reviews (user_id) VALUES (?)")
        tracker1.record_sql_statement("DELETE FROM review_likes WHERE review_id = ?")
        # Non-synced/internal tables and PRAGMA statements should be ignored
        tracker1.record_sql_statement("SELECT * FROM tracks LIMIT 10")
        tracker1.record_sql_statement("PRAGMA page_count;")
        tracker1.record_sql_statement("SELECT * FROM firestore_usage_counters")

        metrics1 = tracker1.get_usage_metrics(conn)
        assert metrics1.reads_today == 1
        assert metrics1.writes_today == 1
        assert metrics1.deletes_today == 1
        assert metrics1.egress_bytes_month >= 512 + 256
        assert metrics1.stored_bytes > 0

        # A fresh tracker reading the same DB preserves flushed counts across restart
        tracker2 = FirestoreUsageTracker()
        tracker2.record(reads=2, egress_bytes=1024)
        metrics2 = tracker2.get_usage_metrics(conn)
        assert metrics2.reads_today == 3
        assert metrics2.writes_today == 1
        assert metrics2.deletes_today == 1
        assert metrics2.egress_bytes_month >= 512 + 256 + 1024
    finally:
        conn.close()
