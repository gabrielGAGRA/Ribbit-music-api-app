"""Unit tests for Plan and User domain models."""

from datetime import UTC, datetime

import pytest

from app.domain.models import Plan, Track, User


def test_plan_default_free_plan_constant() -> None:
    assert Plan.DEFAULT_FREE_PLAN_NAME == "Free"


def test_plan_construction_and_properties_free_plan() -> None:
    plan = Plan(plan_id=1, name="Free", initial_monthly_price=0.0)
    assert plan.plan_id == 1
    assert plan.name == "Free"
    assert plan.monthly_price == 0.0
    assert plan.max_profiles == 1
    assert plan.is_paid is False
    assert plan.allows_dependents is False
    assert plan.can_accommodate(1) is True
    assert plan.can_accommodate(2) is False
    assert plan.can_accommodate_new_dependent(0) is False


def test_plan_construction_paid_single_and_family_plan() -> None:
    single_paid = Plan(
        plan_id=2,
        name="Premium Individual",
        initial_monthly_price=19.90,
        initial_max_profiles=1,
    )
    assert single_paid.is_paid is True
    assert single_paid.allows_dependents is False
    assert single_paid.can_accommodate_new_dependent(0) is False

    family_free = Plan(
        plan_id=3,
        name="Promo Multi",
        initial_monthly_price=0.0,
        initial_max_profiles=4,
    )
    assert family_free.is_paid is False
    assert family_free.allows_dependents is False
    assert family_free.can_accommodate_new_dependent(0) is False

    family_paid = Plan(
        plan_id=4,
        name="Family Plan",
        initial_monthly_price=34.90,
        initial_max_profiles=4,
    )
    assert family_paid.is_paid is True
    assert family_paid.allows_dependents is True
    assert family_paid.can_accommodate(4) is True
    assert family_paid.can_accommodate(5) is False
    assert family_paid.can_accommodate_new_dependent(0) is True
    assert family_paid.can_accommodate_new_dependent(2) is True
    assert family_paid.can_accommodate_new_dependent(3) is False


def test_plan_update_methods_and_chaining() -> None:
    plan = Plan(name="Basic", initial_monthly_price=5.0, initial_max_profiles=1)
    returned = (
        plan.update_name("  Super Family  ").update_price(29.99).update_max_profiles(6)
    )
    assert returned is plan
    assert plan.name == "Super Family"
    assert plan.monthly_price == 29.99
    assert plan.max_profiles == 6


def test_plan_validation_errors() -> None:
    with pytest.raises(ValueError, match="Monthly price cannot be negative"):
        Plan(name="Invalid", initial_monthly_price=-0.01)

    with pytest.raises(ValueError, match="Max profiles must be at least 1"):
        Plan(name="Invalid", initial_monthly_price=10.0, initial_max_profiles=0)

    plan = Plan(name="Valid", initial_monthly_price=10.0, initial_max_profiles=2)
    with pytest.raises(ValueError, match="Plan name cannot be blank"):
        plan.update_name("   ")

    with pytest.raises(ValueError, match="Monthly price cannot be negative"):
        plan.update_price(-5.0)

    with pytest.raises(ValueError, match="Max profiles must be at least 1"):
        plan.update_max_profiles(-1)


def test_user_construction_and_genre_normalization() -> None:
    now = datetime.now(tz=UTC)
    user = User(
        user_id=10,
        email="alice@example.com",
        password_hash="hashed_pw",
        display_name="Alice",
        age=20,
        plan_id=1,
        blocked_genres=frozenset({"  Rock ", "POP", "   "}),
        created_at=now,
    )
    assert user.user_id == 10
    assert user.email == "alice@example.com"
    assert user.password_hash == "hashed_pw"
    assert user.display_name == "Alice"
    assert user.age == 20
    assert user.plan_id == 1
    assert user.spotify_id is None
    assert user.primary_account_id is None
    assert user.is_admin is False
    assert user.created_at == now
    assert isinstance(user.blocked_genres, frozenset)
    assert user.blocked_genres == frozenset({"rock", "pop"})
    assert user.is_adult is True


def test_user_validation_errors_on_init() -> None:
    with pytest.raises(ValueError, match="Email cannot be blank"):
        User(
            email="   ",
            password_hash="hash",
            display_name="Bob",
            age=25,
            plan_id=1,
        )

    with pytest.raises(ValueError, match="Display name cannot be blank"):
        User(
            email="bob@example.com",
            password_hash="hash",
            display_name="  ",
            age=25,
            plan_id=1,
        )

    with pytest.raises(ValueError, match="Age cannot be negative"):
        User(
            email="bob@example.com",
            password_hash="hash",
            display_name="Bob",
            age=-1,
            plan_id=1,
        )


def test_user_is_adult_and_can_listen_filtering() -> None:
    minor = User(
        user_id=1,
        email="minor@example.com",
        password_hash="hash",
        display_name="Minor",
        age=17,
        plan_id=1,
        blocked_genres=frozenset({"funk"}),
    )
    adult = User(
        user_id=2,
        email="adult@example.com",
        password_hash="hash",
        display_name="Adult",
        age=18,
        plan_id=1,
        blocked_genres=frozenset({"metal"}),
    )

    clean_jazz = Track(
        track_id=1,
        title="Blue in Green",
        artist="Miles Davis",
        duration_seconds=327,
        genre="Jazz",
        explicit=False,
    )
    explicit_jazz = Track(
        track_id=2,
        title="Explicit Jazz",
        artist="Artist",
        duration_seconds=200,
        genre="Jazz",
        explicit=True,
    )
    clean_funk = Track(
        track_id=3,
        title="Funky",
        artist="Artist",
        duration_seconds=180,
        genre="  FUNK ",
        explicit=False,
    )
    explicit_metal = Track(
        track_id=4,
        title="Heavy",
        artist="Artist",
        duration_seconds=240,
        genre="Metal",
        explicit=True,
    )

    assert minor.is_adult is False
    assert minor.can_listen(clean_jazz) is True
    assert minor.can_listen(explicit_jazz) is False
    assert minor.can_listen(clean_funk) is False

    assert adult.is_adult is True
    assert adult.can_listen(clean_jazz) is True
    assert adult.can_listen(explicit_jazz) is True
    assert adult.can_listen(explicit_metal) is False


def test_user_family_plan_linking_and_unlinking() -> None:
    dependent = User(
        user_id=5,
        email="dep@example.com",
        password_hash="hash",
        display_name="Dep",
        age=15,
        plan_id=1,
    )
    res = dependent.link_primary_account(1)
    assert res is dependent
    assert dependent.primary_account_id == 1

    with pytest.raises(
        ValueError, match="Cannot link user account to itself as primary account"
    ):
        dependent.link_primary_account(5)

    unlinked = dependent.unlink_primary_account(fallback_plan_id=10)
    assert unlinked is dependent
    assert dependent.primary_account_id is None
    assert dependent.plan_id == 10


def test_user_link_primary_account_when_user_id_is_none() -> None:
    unpersisted = User(
        email="new@example.com",
        password_hash="hash",
        display_name="New",
        age=20,
        plan_id=2,
    )
    unpersisted.link_primary_account(99)
    assert unpersisted.primary_account_id == 99


def test_user_admin_plan_spotify_and_blocked_genres_mutations() -> None:
    user = User(
        user_id=1,
        email="user@example.com",
        password_hash="hash",
        display_name="User",
        age=22,
        plan_id=1,
    )

    assert user.promote_to_admin() is user
    assert user.is_admin is True

    assert user.change_plan(3) is user
    assert user.plan_id == 3

    assert user.link_spotify("  spotify_user_123  ") is user
    assert user.spotify_id == "spotify_user_123"

    with pytest.raises(ValueError, match="Spotify ID cannot be blank"):
        user.link_spotify("   ")

    assert user.update_blocked_genres([" Techno ", "COUNTRY", ""]) is user
    assert user.blocked_genres == frozenset({"techno", "country"})


def test_user_update_profile_success_and_validation() -> None:
    user = User(
        user_id=1,
        email="user@example.com",
        password_hash="old_hash",
        display_name="Old Name",
        age=22,
        plan_id=1,
    )

    assert user.update_profile(display_name="  New Name  ") is user
    assert user.display_name == "New Name"
    assert user.password_hash == "old_hash"

    assert user.update_profile(password_hash="new_hash") is user
    assert user.display_name == "New Name"
    assert user.password_hash == "new_hash"

    assert user.update_profile() is user

    with pytest.raises(ValueError, match="Display name cannot be blank"):
        user.update_profile(display_name="   ")

    with pytest.raises(ValueError, match="Password hash cannot be blank"):
        user.update_profile(password_hash="   ")
