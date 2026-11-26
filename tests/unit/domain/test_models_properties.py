"""Property-based tests for core domain models using Hypothesis."""

from datetime import date

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from app.domain.exceptions import BusinessRuleViolationError
from app.domain.models.jam import Jam, JamQueueItem
from app.domain.models.plan import Plan
from app.domain.models.review import ReviewComment
from app.domain.models.track import Track
from app.domain.models.user import User


def _assert_normalized_genres(genres: frozenset[str], raw: list[str]) -> None:
    expected = frozenset(item.strip().casefold() for item in raw if item.strip())
    assert genres == expected
    for genre in genres:
        assert genre != ""
        assert genre == genre.strip()
        assert genre == genre.casefold()


@given(
    blocked=st.lists(st.text()),
    favorites=st.lists(st.text()),
    new_blocked=st.lists(st.text()),
    new_favorites=st.lists(st.text()),
)
@settings(max_examples=50, deadline=None)
def test_user_genre_normalization_invariant(
    blocked: list[str],
    favorites: list[str],
    new_blocked: list[str],
    new_favorites: list[str],
) -> None:
    user = User(
        email="user@example.com",
        password_hash="hashed_pw",
        display_name="User",
        plan_id=1,
        blocked_genres=frozenset(blocked),
        favorite_genres=frozenset(favorites),
    )
    _assert_normalized_genres(user.blocked_genres, blocked)
    _assert_normalized_genres(user.favorite_genres, favorites)

    user.update_blocked_genres(new_blocked)
    user.update_favorite_genres(new_favorites)
    _assert_normalized_genres(user.blocked_genres, new_blocked)
    _assert_normalized_genres(user.favorite_genres, new_favorites)


@given(
    d1=st.dates(min_value=date(1900, 1, 1), max_value=date(2100, 12, 31)),
    d2=st.dates(min_value=date(1900, 1, 1), max_value=date(2100, 12, 31)),
)
@example(d1=date(2000, 2, 29), d2=date(2018, 2, 28))
@example(d1=date(2000, 2, 29), d2=date(2018, 3, 1))
@settings(max_examples=50, deadline=None)
def test_user_current_age_invariant(d1: date, d2: date) -> None:
    birth_date, today = (d1, d2) if d1 <= d2 else (d2, d1)
    user = User(
        email="user@example.com",
        password_hash="hashed_pw",
        display_name="User",
        plan_id=1,
        birth_date=birth_date.isoformat(),
    )
    expected = (
        today.year
        - birth_date.year
        - ((today.month, today.day) < (birth_date.month, birth_date.day))
    )
    age = user.current_age(today)
    assert age == expected
    assert age >= 0


@given(age=st.integers(min_value=0, max_value=120))
@example(age=17)
@example(age=18)
@settings(max_examples=50, deadline=None)
def test_user_is_minor_invariant(age: int) -> None:
    user = User(
        email="user@example.com",
        password_hash="hashed_pw",
        display_name="User",
        age=age,
        plan_id=1,
    )
    assert user.is_minor() is (age < 18)


def test_user_can_use_plan_blocks_minors_on_free_or_unlinked() -> None:
    free_plan = Plan(
        plan_id=1, name="Free", initial_monthly_price=0.0, initial_max_profiles=1
    )
    family_plan = Plan(
        plan_id=3, name="Família", initial_monthly_price=27.90, initial_max_profiles=4
    )

    minor_free = User(
        email="minor@example.com",
        password_hash="hashed_pw",
        display_name="Minor",
        age=16,
        plan_id=1,
    )
    minor_linked = User(
        email="minor-dep@example.com",
        password_hash="hashed_pw",
        display_name="Minor Dep",
        age=16,
        plan_id=3,
        primary_account_id=1,
    )
    adult_free = User(
        email="adult@example.com",
        password_hash="hashed_pw",
        display_name="Adult",
        age=20,
        plan_id=1,
    )

    assert minor_free.can_use_plan(free_plan) is False
    assert minor_free.can_use_plan(family_plan) is False
    assert minor_linked.can_use_plan(free_plan) is False
    assert minor_linked.can_use_plan(family_plan) is True
    assert adult_free.can_use_plan(free_plan) is True


@given(
    age=st.integers(min_value=0, max_value=100),
    blocked=st.lists(st.text(max_size=20), max_size=5),
    favorites=st.lists(st.text(max_size=20), max_size=5),
    genre=st.text(max_size=25),
    explicit=st.booleans(),
    multiplier=st.floats(
        min_value=0.01, max_value=50.0, allow_nan=False, allow_infinity=False
    ),
)
@settings(max_examples=50, deadline=None)
def test_user_can_listen_and_recommendation_weight(
    age: int,
    blocked: list[str],
    favorites: list[str],
    genre: str,
    explicit: bool,
    multiplier: float,
) -> None:
    user = User(
        email="user@example.com",
        password_hash="hashed_pw",
        display_name="User",
        age=age,
        plan_id=1,
        blocked_genres=frozenset(blocked),
        favorite_genres=frozenset(favorites),
    )
    track = Track(
        title="Song",
        artist="Artist",
        duration_seconds=180,
        genre=genre,
        explicit=explicit,
    )

    if user.is_minor() and track.explicit:
        assert user.can_listen(track) is False

    normalized_genre = track.genre.strip().casefold()
    if normalized_genre and normalized_genre in user.blocked_genres:
        assert user.can_listen(track) is False

    weight = user.recommendation_weight(track, favorite_multiplier=multiplier)
    if not user.can_listen(track):
        assert weight == 0.0
    elif user.is_favorite_genre(track):
        assert weight == multiplier
    else:
        assert weight == 1.0


@given(
    monthly_price=st.floats(
        min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False
    ),
    max_profiles=st.integers(min_value=1, max_value=50),
    current_dependents=st.integers(min_value=0, max_value=50),
)
@settings(max_examples=50, deadline=None)
def test_plan_pricing_and_dependents_invariant(
    monthly_price: float,
    max_profiles: int,
    current_dependents: int,
) -> None:
    plan = Plan(
        name="Test Plan",
        initial_monthly_price=monthly_price,
        initial_max_profiles=max_profiles,
    )
    assert plan.is_paid is (monthly_price > 0.0)
    assert plan.allows_dependents is (plan.is_paid and max_profiles > 1)
    assert plan.can_accommodate_new_dependent(current_dependents) is (
        plan.allows_dependents and (current_dependents + 2 <= max_profiles)
    )


@given(
    initial_points=st.integers(
        min_value=JamQueueItem.MIN_POINTS, max_value=JamQueueItem.MAX_POINTS
    ),
    deltas=st.lists(st.integers(min_value=-100, max_value=100), max_size=50),
)
@settings(max_examples=50, deadline=None)
def test_jam_queue_item_vote_clamping(
    initial_points: int,
    deltas: list[int],
) -> None:
    item = JamQueueItem(
        jam_id=1,
        track_id=1,
        initial_vote_points=initial_points,
    )
    for delta in deltas:
        item.vote(delta)
        assert JamQueueItem.MIN_POINTS <= item.vote_points <= JamQueueItem.MAX_POINTS


@given(max_superlikes=st.integers(min_value=0, max_value=30))
@settings(max_examples=50, deadline=None)
def test_jam_superlike_limit(max_superlikes: int) -> None:
    jam = Jam.create(
        host_user_id=1,
        room_name="Test Room",
        max_superlikes=max_superlikes,
    )
    for index in range(max_superlikes):
        jam.use_superlike()
        assert jam.superlikes_used == index + 1

    with pytest.raises(BusinessRuleViolationError):
        jam.use_superlike()


@given(
    duration_minutes=st.integers(min_value=1, max_value=120),
    increments=st.lists(st.integers(min_value=1, max_value=3600), max_size=30),
)
@settings(max_examples=50, deadline=None)
def test_jam_duration_and_active_state(
    duration_minutes: int,
    increments: list[int],
) -> None:
    jam = Jam.create(
        host_user_id=1,
        room_name="Test Room",
        duration_minutes=duration_minutes,
    )
    max_seconds = duration_minutes * 60
    for seconds in increments:
        jam.add_accumulated_duration(seconds)
        assert jam.is_active is (jam.accumulated_duration_seconds < max_seconds)

    if not jam.is_active:
        with pytest.raises(BusinessRuleViolationError):
            jam.set_current_track(10)
    else:
        jam.set_current_track(10)
        assert jam.current_track_id == 10


@given(rating=st.integers(min_value=-100, max_value=100))
@settings(max_examples=50, deadline=None)
def test_review_comment_rating_validation(rating: int) -> None:
    assert ReviewComment.is_valid_rating(rating) is (1 <= rating <= 5)


@given(rating=st.one_of(st.integers(max_value=0), st.integers(min_value=6)))
@settings(max_examples=50, deadline=None)
def test_review_comment_invalid_rating_raises(rating: int) -> None:
    with pytest.raises(ValueError):
        ReviewComment(user_id=1, track_id=1, initial_rating=rating)

    review = ReviewComment(user_id=1, track_id=1, initial_rating=3)
    with pytest.raises(ValueError):
        review.update_content(rating, "updated")


@given(
    initial_likes=st.integers(min_value=0, max_value=100),
    k=st.integers(min_value=0, max_value=100),
)
@settings(max_examples=50, deadline=None)
def test_review_comment_likes_count_invariant(
    initial_likes: int,
    k: int,
) -> None:
    review = ReviewComment(
        user_id=1,
        track_id=1,
        initial_rating=4,
        initial_likes_count=initial_likes,
    )
    for _ in range(k):
        review.like()
    assert review.likes_count == initial_likes + k
