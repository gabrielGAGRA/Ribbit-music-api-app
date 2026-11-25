"""Unit tests for genre preference weighting and weighted track recommendation."""

import random

from app.domain.models.track import Track
from app.domain.models.user import User
from app.domain.services.recommendation import (
    order_tracks_by_weighted_preference,
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


def test_genre_alias_matching_handles_portuguese_and_subgenres() -> None:
    user = _make_user(
        favorite_genres=frozenset({"eletrônica", "rock"}),
        blocked_genres=frozenset({"metal"}),
    )

    assert user.is_favorite_genre(_make_track(1, "Electronic")) is True
    assert user.is_favorite_genre(_make_track(2, "drum and bass")) is True
    assert user.is_favorite_genre(_make_track(3, "hard rock")) is True
    assert user.is_favorite_genre(_make_track(4, "roc")) is True
    assert user.can_listen(_make_track(5, "black metal")) is False
    assert user.can_listen(_make_track(6, "death metal")) is False
    assert user.can_listen(_make_track(7, "Electronic")) is True


def test_catalog_genre_dictionary_matches_real_db_genres() -> None:
    from app.domain.services.genre_names import (
        CATALOG_GENRES,
        GENRE_CATALOG_DICT,
        GENRE_DB_TO_CANONICAL,
        expand_genre_db_values,
        genre_matches_preference,
    )

    assert len(CATALOG_GENRES) == 30
    assert "Hip Hop" in GENRE_CATALOG_DICT
    assert "Forró" in GENRE_CATALOG_DICT
    assert "Axé" in GENRE_CATALOG_DICT
    assert GENRE_DB_TO_CANONICAL["hip-hop"] == "Hip Hop"
    assert GENRE_DB_TO_CANONICAL["r&b"] == "R&B"
    assert GENRE_DB_TO_CANONICAL["forro"] == "Forró"
    assert GENRE_DB_TO_CANONICAL["axe"] == "Axé"
    assert GENRE_DB_TO_CANONICAL["detroit-techno"] == "Electronic"
    assert GENRE_DB_TO_CANONICAL["música tropical"] == "Latin"

    assert "hip-hop" in expand_genre_db_values("Hip Hop")
    assert "r&b" in expand_genre_db_values("R&B")
    assert "forro" in expand_genre_db_values("Forró")
    assert "axe" in expand_genre_db_values("Axé")

    assert genre_matches_preference("hip-hop", "Hip Hop") is True
    assert genre_matches_preference("r&b", "R&B") is True
    assert genre_matches_preference("forro", "Forró") is True
    assert genre_matches_preference("axe", "Axé") is True
    assert genre_matches_preference("k-pop", "K-Pop") is True
    assert genre_matches_preference("detroit-techno", "Electronic") is True
    assert genre_matches_preference("música tropical", "Latin") is True
    assert genre_matches_preference("sertanejo", "Rock") is False


def test_order_tracks_by_weighted_preference_randomizes_even_without_favorites() -> (
    None
):
    user = _make_user()
    candidates = [_make_track(i, "Rock") for i in range(1, 31)]

    ordered_a = order_tracks_by_weighted_preference(
        candidates, user, seed_key="playlist:24:user:4"
    )
    ordered_a_repeat = order_tracks_by_weighted_preference(
        candidates, user, seed_key="playlist:24:user:4"
    )
    ordered_b = order_tracks_by_weighted_preference(
        candidates, user, seed_key="playlist:25:user:4"
    )
    ordered_rng = order_tracks_by_weighted_preference(
        candidates,
        user,
        rng=random.Random(7),  # noqa: S311
    )

    ids_a = [t.track_id for t in ordered_a]
    assert ids_a == [t.track_id for t in ordered_a_repeat]
    assert ids_a != list(range(1, 31))
    assert ids_a != [t.track_id for t in ordered_b]
    assert [t.track_id for t in ordered_rng] != list(range(1, 31))
    assert set(ids_a) == set(range(1, 31))


def test_order_tracks_by_weighted_preference_favors_favorites_and_filters_restricted() -> (
    None
):
    user = _make_user(
        age=16,
        favorite_genres=frozenset({"rock"}),
        blocked_genres=frozenset({"jazz"}),
    )
    candidates = [
        *[_make_track(i, "Rock" if i <= 20 else "Pop") for i in range(1, 41)],
        _make_track(101, "Jazz"),
        _make_track(102, "Trap"),
        _make_track(103, "Rock", explicit=True),
        _make_track(104, "Rock", is_deleted=True),
    ]

    ordered = order_tracks_by_weighted_preference(
        candidates, user, seed_key="playlist:10:user:1"
    )
    returned_ids = {t.track_id for t in ordered}
    assert returned_ids.isdisjoint({101, 102, 103, 104})
    assert len(ordered) == 40
    top_10_rock = sum(1 for t in ordered[:10] if t.genre == "Rock")
    assert top_10_rock >= 6
    assert any(t.genre == "Pop" for t in ordered)
