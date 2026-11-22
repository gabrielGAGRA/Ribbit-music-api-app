"""Property-based tests for recommendation, analytics, and family plan domain services."""

import math
import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.domain.exceptions import BusinessRuleViolationError
from app.domain.models.plan import Plan
from app.domain.models.track import Track
from app.domain.models.user import User
from app.domain.services.family_plan_service import FamilyPlanService
from app.domain.services.recommendation import (
    _deterministic_unit_interval,
    order_tracks_by_weighted_seed,
    select_weighted_track,
)
from app.domain.services.subscription_analytics_service import (
    SubscriptionAnalyticsService,
)

GENRE_POOL = (
    "pop",
    "rock",
    "jazz",
    "funk",
    "hip hop",
    "rap",
    "trap",
    "indie",
    "classical",
)


@st.composite
def tracks_strategy(
    draw: st.DrawFn, *, min_size: int = 0, max_size: int = 20
) -> list[Track]:
    """Generate a list of Tracks with unique positive track_ids."""
    track_ids = draw(
        st.lists(
            st.integers(min_value=1, max_value=100_000),
            min_size=min_size,
            max_size=max_size,
            unique=True,
        )
    )
    return [
        Track(
            track_id=tid,
            title=f"Track {tid}",
            artist=f"Artist {tid}",
            duration_seconds=draw(st.integers(min_value=30, max_value=600)),
            genre=draw(st.sampled_from(GENRE_POOL)),
            explicit=draw(st.booleans()),
            is_deleted=draw(st.booleans()),
        )
        for tid in track_ids
    ]


@st.composite
def users_strategy(
    draw: st.DrawFn,
    *,
    user_id: int | None = None,
    plan_id: int = 1,
    primary_account_id: int | None = None,
) -> User:
    """Generate a valid User with random age, favorite genres, and blocked genres."""
    age = draw(st.integers(min_value=5, max_value=80))
    favorite_genres = draw(st.frozensets(st.sampled_from(GENRE_POOL), max_size=4))
    blocked_genres = draw(st.frozensets(st.sampled_from(GENRE_POOL), max_size=4))
    return User(
        user_id=user_id,
        email=f"user{user_id or 1}@example.com",
        password_hash="hashed_secret",
        display_name=f"User {user_id or 1}",
        age=age,
        plan_id=plan_id,
        primary_account_id=primary_account_id,
        favorite_genres=favorite_genres,
        blocked_genres=blocked_genres,
    )


@st.composite
def plans_strategy(
    draw: st.DrawFn, *, min_size: int = 1, max_size: int = 6
) -> list[Plan]:
    """Generate a list of Plans with distinct positive plan_ids and distinct names."""
    plan_ids = draw(
        st.lists(
            st.integers(min_value=1, max_value=1_000),
            min_size=min_size,
            max_size=max_size,
            unique=True,
        )
    )
    plans: list[Plan] = []
    for pid in plan_ids:
        price = draw(
            st.floats(
                min_value=0.0, max_value=500.0, allow_nan=False, allow_infinity=False
            )
        )
        max_profiles = draw(st.integers(min_value=1, max_value=10))
        plans.append(
            Plan(
                plan_id=pid,
                name=f"Plan-{pid}",
                initial_monthly_price=round(price, 2),
                initial_max_profiles=max_profiles,
            )
        )
    return plans


@settings(max_examples=50, deadline=None)
@given(seed_key=st.text(), track_id=st.integers())
def test_deterministic_unit_interval_bounds_and_determinism(
    seed_key: str, track_id: int
) -> None:
    first = _deterministic_unit_interval(seed_key, track_id)
    second = _deterministic_unit_interval(seed_key, track_id)
    assert first == second
    assert 0.0 < first < 1.0


@settings(max_examples=50, deadline=None)
@given(
    candidates=tracks_strategy(),
    user=users_strategy(user_id=1),
    seed_key=st.text(),
    favorite_multiplier=st.floats(
        min_value=1.0, max_value=20.0, allow_nan=False, allow_infinity=False
    ),
)
def test_order_tracks_by_weighted_seed_properties(
    candidates: list[Track],
    user: User,
    seed_key: str,
    favorite_multiplier: float,
) -> None:
    first = order_tracks_by_weighted_seed(
        candidates,
        user,
        seed_key=seed_key,
        favorite_multiplier=favorite_multiplier,
    )
    second = order_tracks_by_weighted_seed(
        candidates,
        user,
        seed_key=seed_key,
        favorite_multiplier=favorite_multiplier,
    )

    first_ids = [track.track_id for track in first]
    second_ids = [track.track_id for track in second]
    assert first_ids == second_ids

    assert all(not track.is_deleted and user.can_listen(track) for track in first)

    expected_ids = {
        track.track_id
        for track in candidates
        if not track.is_deleted and user.can_listen(track)
    }
    assert set(first_ids) == expected_ids
    assert len(first_ids) == len(expected_ids)


@settings(max_examples=50, deadline=None)
@given(
    candidates=tracks_strategy(),
    user=users_strategy(user_id=1),
    rng_seed=st.integers(),
    favorite_multiplier=st.floats(
        min_value=1.0, max_value=20.0, allow_nan=False, allow_infinity=False
    ),
)
def test_select_weighted_track_properties(
    candidates: list[Track],
    user: User,
    rng_seed: int,
    favorite_multiplier: float,
) -> None:
    eligible = [t for t in candidates if not t.is_deleted and user.can_listen(t)]
    selected = select_weighted_track(
        candidates,
        user,
        rng=random.Random(rng_seed),  # noqa: S311
        favorite_multiplier=favorite_multiplier,
    )

    if not eligible:
        assert selected is None
    else:
        assert selected is not None
        assert selected in candidates
        assert not selected.is_deleted
        assert user.can_listen(selected)


@st.composite
def analytics_inputs_strategy(
    draw: st.DrawFn,
) -> tuple[list[Plan], list[User], list[User], int, float, float, float]:
    """Generate plans, initial users, extra dependent users, and finite cost parameters."""
    plans = draw(plans_strategy(min_size=1, max_size=5))
    plan_ids = [p.plan_id for p in plans if p.plan_id is not None]

    user_count = draw(st.integers(min_value=0, max_value=15))
    users: list[User] = []
    for idx in range(1, user_count + 1):
        pid = draw(st.sampled_from(plan_ids))
        is_dep = draw(st.booleans())
        primary_id = draw(st.integers(min_value=1, max_value=100)) if is_dep else None
        users.append(
            draw(
                users_strategy(user_id=idx, plan_id=pid, primary_account_id=primary_id)
            )
        )

    extra_dep_count = draw(st.integers(min_value=1, max_value=5))
    extra_dependents: list[User] = []
    for offset in range(1, extra_dep_count + 1):
        uid = user_count + offset
        pid = draw(st.sampled_from(plan_ids))
        primary_id = draw(st.integers(min_value=1, max_value=100))
        extra_dependents.append(
            draw(
                users_strategy(user_id=uid, plan_id=pid, primary_account_id=primary_id)
            )
        )

    active_tracks_count = draw(st.integers(min_value=0, max_value=10_000))
    cost_st = st.floats(
        min_value=0.0, max_value=1_000.0, allow_nan=False, allow_infinity=False
    )
    content_cost_per_track = round(draw(cost_st), 4)
    infrastructure_fixed_cost = round(draw(cost_st), 2)
    infrastructure_cost_per_user = round(draw(cost_st), 4)

    return (
        plans,
        users,
        extra_dependents,
        active_tracks_count,
        content_cost_per_track,
        infrastructure_fixed_cost,
        infrastructure_cost_per_user,
    )


@settings(max_examples=50, deadline=None)
@given(data=analytics_inputs_strategy())
def test_subscription_analytics_revenue_breakdown_invariants(
    data: tuple[list[Plan], list[User], list[User], int, float, float, float],
) -> None:
    (
        plans,
        users,
        extra_dependents,
        active_tracks_count,
        content_cost_per_track,
        infrastructure_fixed_cost,
        infrastructure_cost_per_user,
    ) = data
    service = SubscriptionAnalyticsService()

    base = service.calculate_revenue_breakdown(
        users=users,
        plans=plans,
        active_tracks_count=active_tracks_count,
        content_cost_per_track=content_cost_per_track,
        infrastructure_fixed_cost=infrastructure_fixed_cost,
        infrastructure_cost_per_user=infrastructure_cost_per_user,
    )

    assert base.total_users == len(users)
    assert math.isclose(
        base.total_costs,
        round(base.content_cost + base.infrastructure_cost, 2),
        abs_tol=1e-9,
    )
    assert math.isclose(
        base.estimated_net_revenue,
        round(base.gross_revenue - base.total_costs, 2),
        abs_tol=1e-9,
    )

    with_deps = service.calculate_revenue_breakdown(
        users=[*users, *extra_dependents],
        plans=plans,
        active_tracks_count=active_tracks_count,
        content_cost_per_track=content_cost_per_track,
        infrastructure_fixed_cost=infrastructure_fixed_cost,
        infrastructure_cost_per_user=infrastructure_cost_per_user,
    )

    assert with_deps.gross_revenue == base.gross_revenue
    assert with_deps.revenue_by_plan == base.revenue_by_plan
    assert with_deps.total_users == base.total_users + len(extra_dependents)
    assert sum(with_deps.users_by_plan.values()) == (
        sum(base.users_by_plan.values()) + len(extra_dependents)
    )


@settings(max_examples=50, deadline=None)
@given(
    plan_id=st.integers(min_value=1, max_value=1_000),
    monthly_price=st.floats(
        min_value=0.01, max_value=500.0, allow_nan=False, allow_infinity=False
    ),
    max_profiles=st.integers(min_value=2, max_value=12),
    p_id=st.integers(min_value=1, max_value=10_000),
    d_offset=st.integers(min_value=1, max_value=10_000),
    current_dependents_count=st.integers(min_value=0, max_value=15),
    fb_id=st.integers(min_value=1, max_value=1_000),
)
def test_family_plan_service_roundtrip_and_quota(
    plan_id: int,
    monthly_price: float,
    max_profiles: int,
    p_id: int,
    d_offset: int,
    current_dependents_count: int,
    fb_id: int,
) -> None:
    d_id = p_id + d_offset
    plan = Plan(
        plan_id=plan_id,
        name=f"Family-{plan_id}",
        initial_monthly_price=monthly_price,
        initial_max_profiles=max_profiles,
    )
    primary = User(
        user_id=p_id,
        email=f"primary{p_id}@example.com",
        password_hash="hashed",
        display_name="Primary",
        age=30,
        plan_id=plan_id,
        primary_account_id=None,
    )
    dependent = User(
        user_id=d_id,
        email=f"dep{d_id}@example.com",
        password_hash="hashed",
        display_name="Dependent",
        age=14,
        plan_id=fb_id,
        primary_account_id=None,
    )
    service = FamilyPlanService()
    should_succeed = current_dependents_count <= plan.max_profiles - 2

    if not should_succeed:
        with pytest.raises(BusinessRuleViolationError):
            service.link_dependent(
                primary_user=primary,
                dependent_user=dependent,
                plan=plan,
                current_dependents_count=current_dependents_count,
            )
        return

    linked = service.link_dependent(
        primary_user=primary,
        dependent_user=dependent,
        plan=plan,
        current_dependents_count=current_dependents_count,
    )
    assert linked.primary_account_id == p_id
    assert linked.plan_id == plan_id

    idempotent = service.link_dependent(
        primary_user=primary,
        dependent_user=dependent,
        plan=plan,
        current_dependents_count=current_dependents_count + 1,
    )
    assert idempotent.primary_account_id == p_id
    assert idempotent.plan_id == plan_id

    unlinked = service.unlink_dependent(
        primary_user_id=p_id,
        member_user=dependent,
        fallback_plan_id=fb_id,
    )
    assert unlinked.primary_account_id is None
    assert unlinked.plan_id == fb_id
