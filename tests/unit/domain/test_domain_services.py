"""Unit tests for domain services implementing multi-entity business policies."""

import pytest

from app.domain.exceptions import (
    BusinessRuleViolationError,
    PermissionDeniedError,
)
from app.domain.models import Plan, User
from app.domain.services import (
    FamilyPlanService,
    SubscriptionAnalyticsService,
)


def _make_user(
    user_id: int,
    plan_id: int = 1,
    primary_account_id: int | None = None,
) -> User:
    return User(
        user_id=user_id,
        email=f"user{user_id}@ribbit.com",
        password_hash="hash",
        display_name=f"User {user_id}",
        age=25,
        plan_id=plan_id,
        primary_account_id=primary_account_id,
    )


def test_family_plan_service_link_dependent_rejects_plan_without_dependents() -> None:
    service = FamilyPlanService()
    primary = _make_user(1, plan_id=1)
    dep = _make_user(2, plan_id=1)
    plan = Plan(
        plan_id=1, name="Solo", initial_monthly_price=9.9, initial_max_profiles=1
    )

    with pytest.raises(PermissionDeniedError, match="Current plan does not support"):
        service.link_dependent(
            primary_user=primary,
            dependent_user=dep,
            plan=plan,
            current_dependents_count=0,
        )


def test_family_plan_service_link_dependent_rejects_dependent_as_manager() -> None:
    service = FamilyPlanService()
    primary = _make_user(2, plan_id=2, primary_account_id=1)
    dep = _make_user(3, plan_id=1)
    plan = Plan(
        plan_id=2, name="Family", initial_monthly_price=29.9, initial_max_profiles=4
    )

    with pytest.raises(PermissionDeniedError, match="dependent user cannot manage"):
        service.link_dependent(
            primary_user=primary,
            dependent_user=dep,
            plan=plan,
            current_dependents_count=1,
        )


def test_family_plan_service_link_dependent_rejects_self_linking() -> None:
    service = FamilyPlanService()
    primary = _make_user(1, plan_id=2)
    plan = Plan(
        plan_id=2, name="Family", initial_monthly_price=29.9, initial_max_profiles=4
    )

    with pytest.raises(BusinessRuleViolationError, match="cannot add themselves"):
        service.link_dependent(
            primary_user=primary,
            dependent_user=primary,
            plan=plan,
            current_dependents_count=0,
        )


def test_family_plan_service_link_dependent_idempotent_if_already_linked() -> None:
    service = FamilyPlanService()
    primary = _make_user(1, plan_id=2)
    dep = _make_user(2, plan_id=2, primary_account_id=1)
    plan = Plan(
        plan_id=2, name="Family", initial_monthly_price=29.9, initial_max_profiles=4
    )

    result = service.link_dependent(
        primary_user=primary,
        dependent_user=dep,
        plan=plan,
        current_dependents_count=1,
    )
    assert result is dep
    assert result.primary_account_id == 1


def test_family_plan_service_link_dependent_rejects_already_linked_to_other() -> None:
    service = FamilyPlanService()
    primary = _make_user(1, plan_id=2)
    dep = _make_user(2, plan_id=2, primary_account_id=99)
    plan = Plan(
        plan_id=2, name="Family", initial_monthly_price=29.9, initial_max_profiles=4
    )

    with pytest.raises(BusinessRuleViolationError, match="already linked to another"):
        service.link_dependent(
            primary_user=primary,
            dependent_user=dep,
            plan=plan,
            current_dependents_count=0,
        )


def test_family_plan_service_link_dependent_rejects_when_quota_exceeded() -> None:
    service = FamilyPlanService()
    primary = _make_user(1, plan_id=2)
    dep = _make_user(5, plan_id=1)
    plan = Plan(
        plan_id=2, name="Family", initial_monthly_price=29.9, initial_max_profiles=3
    )

    # max_profiles=3 allows primary + 2 dependents. If 2 dependents already exist:
    with pytest.raises(BusinessRuleViolationError, match="profile limit of 3 reached"):
        service.link_dependent(
            primary_user=primary,
            dependent_user=dep,
            plan=plan,
            current_dependents_count=2,
        )


def test_family_plan_service_link_dependent_success() -> None:
    service = FamilyPlanService()
    primary = _make_user(1, plan_id=2)
    dep = _make_user(3, plan_id=1)
    plan = Plan(
        plan_id=2, name="Family", initial_monthly_price=29.9, initial_max_profiles=4
    )

    result = service.link_dependent(
        primary_user=primary,
        dependent_user=dep,
        plan=plan,
        current_dependents_count=1,
    )
    assert result.primary_account_id == 1
    assert result.plan_id == 2


def test_family_plan_service_unlink_dependent_rejects_foreign_member() -> None:
    service = FamilyPlanService()
    member = _make_user(3, plan_id=2, primary_account_id=99)

    with pytest.raises(PermissionDeniedError, match="does not belong to your family"):
        service.unlink_dependent(
            primary_user_id=1,
            member_user=member,
            fallback_plan_id=1,
        )


def test_family_plan_service_unlink_dependent_success() -> None:
    service = FamilyPlanService()
    member = _make_user(3, plan_id=2, primary_account_id=1)

    result = service.unlink_dependent(
        primary_user_id=1,
        member_user=member,
        fallback_plan_id=5,
    )
    assert result.primary_account_id is None
    assert result.plan_id == 5


def test_subscription_analytics_service_calculates_breakdown() -> None:
    service = SubscriptionAnalyticsService()
    free_plan = Plan(
        plan_id=1, name="Free", initial_monthly_price=0.0, initial_max_profiles=1
    )
    pro_plan = Plan(
        plan_id=2, name="Pro", initial_monthly_price=10.0, initial_max_profiles=1
    )
    family_plan = Plan(
        plan_id=3, name="Family", initial_monthly_price=30.0, initial_max_profiles=4
    )
    plans = [free_plan, pro_plan, family_plan]

    users = [
        _make_user(1, plan_id=1),  # Free primary
        _make_user(2, plan_id=2),  # Pro primary
        _make_user(3, plan_id=3),  # Family primary
        _make_user(4, plan_id=3, primary_account_id=3),  # Family dependent
    ]

    breakdown = service.calculate_revenue_breakdown(users=users, plans=plans)

    assert breakdown.total_users == 4
    # Revenue only from primary accounts: 0.0 + 10.0 + 30.0 = 40.0 (dependent contributes 0)
    assert breakdown.estimated_net_revenue == 40.0
    assert breakdown.users_by_plan == {"Free": 1, "Pro": 1, "Family": 2}
    assert breakdown.revenue_by_plan == {"Free": 0.0, "Pro": 10.0, "Family": 30.0}
