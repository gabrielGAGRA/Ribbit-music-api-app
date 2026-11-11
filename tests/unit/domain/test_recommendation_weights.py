"""Unit tests for genre preference weighting and weighted track recommendation."""

import random

from app.domain.models.track import Track
from app.domain.models.user import User
from app.domain.services.recommendation import (
    order_tracks_by_weighted_seed,
    select_weighted_track,
)


def _make_user(
    *,
    age: int = 25,
    favorite_genres: frozenset[str] = frozenset(),
    blocked_genres: frozenset[str] = frozenset(),
) -> User:
    return User(
        user_id=1,
        email="listener@ribbit.com",
        password_hash="hashed",
        display_name="Listener",
        age=age,
        plan_id=1,
        favorite_genres=favorite_genres,
        blocked_genres=blocked_genres,
    )


def _make_track(
    track_id: int,
    genre: str,
    *,
    explicit: bool = False,
    is_deleted: bool = False,
) -> Track:
    return Track(
        track_id=track_id,
        title=f"Song {track_id}",
        artist="Artist",
        duration_seconds=180,
        genre=genre,
        explicit=explicit,
        is_deleted=is_deleted,
    )


def test_user_is_favorite_genre_matches_exact_and_tokenized_subgenres() -> None:
    user = _make_user(favorite_genres=frozenset({"Rock", "Hip Hop"}))

    assert user.is_favorite_genre(_make_track(1, "rock")) is True
    assert user.is_favorite_genre(_make_track(2, "Indie Rock")) is True
    assert user.is_favorite_genre(_make_track(3, "Alternative / Hip Hop")) is True
    assert user.is_favorite_genre(_make_track(4, "Jazz")) is False
    assert user.is_favorite_genre(_make_track(5, "")) is False


def test_user_recommendation_weight_respects_favorites_and_restrictions() -> None:
    user = _make_user(
        age=16,
        favorite_genres=frozenset({"rock", "trap", "jazz"}),
        blocked_genres=frozenset({"jazz"}),
    )

    # Favorite & allowed -> 3.0
    assert user.recommendation_weight(_make_track(1, "Rock")) == 3.0
    # Non-favorite & allowed -> 1.0
    assert user.recommendation_weight(_make_track(2, "Classical")) == 1.0
    # Blocked genre even if in favorite_genres -> 0.0
    assert user.recommendation_weight(_make_track(3, "Jazz")) == 0.0
    # Minor-restricted genre ("trap") even if in favorite_genres -> 0.0
    assert user.recommendation_weight(_make_track(4, "Trap")) == 0.0
    # Explicit track for minor -> 0.0
    assert user.recommendation_weight(_make_track(5, "Rock", explicit=True)) == 0.0


def test_select_weighted_track_favors_favorite_genre_while_allowing_others() -> None:
    user = _make_user(favorite_genres=frozenset({"rock"}))
    fav_track = _make_track(1, "Rock")
    other_track = _make_track(2, "Pop")
    rng = random.Random(42)  # noqa: S311

    picks = [
        select_weighted_track([fav_track, other_track], user, rng=rng)
        for _ in range(400)
    ]
    fav_count = sum(1 for pick in picks if pick and pick.track_id == 1)
    other_count = sum(1 for pick in picks if pick and pick.track_id == 2)

    # With 3:1 weight ratio (~75% expected), favorite should clearly dominate
    # while non-favorite still gets picked (>0).
    assert 260 <= fav_count <= 340
    assert other_count > 0
    assert fav_count + other_count == 400


def test_select_weighted_track_returns_none_when_no_eligible_candidates() -> None:
    user = _make_user(blocked_genres=frozenset({"pop"}))
    blocked = _make_track(1, "Pop")
    deleted = _make_track(2, "Rock", is_deleted=True)

    assert select_weighted_track([blocked, deleted], user) is None


def test_order_tracks_by_weighted_seed_preserves_id_order_without_favorites() -> None:
    user = _make_user()
    t1 = _make_track(30, "Pop")
    t2 = _make_track(10, "Rock")
    t3 = _make_track(20, "Jazz")

    ordered = order_tracks_by_weighted_seed([t1, t2, t3], user, seed_key="jam:1:user:1")
    assert [t.track_id for t in ordered] == [10, 20, 30]


def test_order_tracks_by_weighted_seed_is_deterministic_and_prioritizes_favorites() -> (
    None
):
    user = _make_user(favorite_genres=frozenset({"rock"}))
    candidates = [_make_track(i, "Rock" if i <= 20 else "Pop") for i in range(1, 41)]

    first_run = order_tracks_by_weighted_seed(
        candidates, user, seed_key="jam:10:user:1"
    )
    second_run = order_tracks_by_weighted_seed(
        candidates, user, seed_key="jam:10:user:1"
    )

    assert [t.track_id for t in first_run] == [t.track_id for t in second_run]
    # In the top 10 of 40 tracks, Rock (weight 3.0) should outnumber Pop (weight 1.0)
    top_10_rock = sum(1 for t in first_run[:10] if t.genre == "Rock")
    assert top_10_rock >= 6
