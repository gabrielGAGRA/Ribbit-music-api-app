"""Domain service for weighted track recommendation in swipe flows."""

import hashlib
import random
from dataclasses import dataclass, field
lazy from collections.abc import Mapping, Sequence

from app.domain.models.user import DEFAULT_FAVORITE_WEIGHT_MULTIPLIER
from app.domain.services.genre_names import genre_matches_preference
lazy from app.domain.models.track import Track
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True)
class RecommendationProfile:
    """Aggregated listener preference signals derived from history and interactions."""

    positive_genres: Mapping[str, float] = field(default_factory=dict)
    disliked_genres: Mapping[str, float] = field(default_factory=dict)
    positive_artists: Mapping[str, float] = field(default_factory=dict)
    disliked_artists: Mapping[str, float] = field(default_factory=dict)
    positive_decades: Mapping[int, float] = field(default_factory=dict)
    disliked_decades: Mapping[int, float] = field(default_factory=dict)


def _lookup_genre_affinity(genre: str, affinity_map: Mapping[str, float]) -> float:
    if not genre or not affinity_map:
        return 0.0
    total = 0.0
    for key, score in affinity_map.items():
        if genre_matches_preference(genre, key):
            total += score
    return total


def _apply_profile_signals(
    weight: float,
    track: Track,
    user: User,
    profile: RecommendationProfile,
) -> float:
    pos_genre = _lookup_genre_affinity(track.genre, profile.positive_genres)
    if pos_genre > 0.0:
        weight += min(2.0, pos_genre * 0.5)

    artist_key = track.artist.strip().casefold()
    pos_artist = profile.positive_artists.get(artist_key, 0.0)
    if pos_artist > 0.0:
        weight += min(1.5, pos_artist * 0.5)

    if track.release_year is not None:
        decade = (track.release_year // 10) * 10
        pos_decade = profile.positive_decades.get(decade, 0.0)
        if pos_decade > 0.0:
            weight += min(0.6, pos_decade * 0.2)

    disliked_genre = _lookup_genre_affinity(track.genre, profile.disliked_genres)
    if disliked_genre > 0.0 and not user.is_favorite_genre(track):
        weight *= max(0.15, 1.0 / (1.0 + disliked_genre))

    disliked_artist = profile.disliked_artists.get(artist_key, 0.0)
    if disliked_artist > 0.0:
        weight *= max(0.15, 1.0 / (1.0 + disliked_artist))
    return weight


def _apply_rating_multiplier(weight: float, track: Track) -> float:
    if track.average_rating is None or track.average_rating <= 0.0:
        return weight
    if track.average_rating >= 3.5:
        return weight * (1.0 + min(0.5, (track.average_rating - 3.0) * 0.25))
    if track.average_rating < 2.5:
        return weight * 0.75
    return weight


def score_track_for_user(
    track: Track,
    user: User,
    *,
    profile: RecommendationProfile | None = None,
    favorite_multiplier: float = DEFAULT_FAVORITE_WEIGHT_MULTIPLIER,
) -> float:
    """Computes a non-negative recommendation weight combining preferences, history, and ratings."""
    if track.is_deleted:
        return 0.0
    weight = user.recommendation_weight(track, favorite_multiplier=favorite_multiplier)
    if weight <= 0.0:
        return 0.0
    if profile is not None:
        weight = _apply_profile_signals(weight, track, user, profile)
    weight = _apply_rating_multiplier(weight, track)
    return max(0.05, weight)


def _has_favorite_genres(user: User) -> bool:
    return any(genre and genre.strip() for genre in user.favorite_genres)


def _deterministic_unit_interval(seed_key: str, track_id: int) -> float:
    digest = hashlib.sha256(f"{seed_key}:{track_id}".encode()).digest()
    raw_int = int.from_bytes(digest[:8], "big")
    return (raw_int + 1) / (2**64 + 2)


def select_weighted_track(
    candidates: Sequence[Track],
    user: User,
    *,
    rng: random.Random | None = None,
    favorite_multiplier: float = DEFAULT_FAVORITE_WEIGHT_MULTIPLIER,
    profile: RecommendationProfile | None = None,
) -> Track | None:
    """Selects a single track using genre preference weights, history, and ratings."""
    eligible: list[Track] = []
    weights: list[float] = []

    for track in candidates:
        weight = score_track_for_user(
            track,
            user,
            profile=profile,
            favorite_multiplier=favorite_multiplier,
        )
        if weight > 0.0:
            eligible.append(track)
            weights.append(weight)

    if not eligible:
        return None
    if len(eligible) == 1:
        return eligible[0]

    chooser = rng if rng is not None else random
    return chooser.choices(eligible, weights=weights, k=1)[0]


def order_tracks_by_weighted_seed(
    candidates: Sequence[Track],
    user: User,
    *,
    seed_key: str,
    favorite_multiplier: float = DEFAULT_FAVORITE_WEIGHT_MULTIPLIER,
) -> list[Track]:
    """Orders eligible tracks deterministically using Efraimidis-Spirakis weighted keys."""
    eligible = [
        track for track in candidates if not track.is_deleted and user.can_listen(track)
    ]
    if not _has_favorite_genres(user):
        return sorted(eligible, key=lambda track: track.track_id or 0)

    scored: list[tuple[float, int, Track]] = []
    for track in eligible:
        tid = track.track_id or 0
        weight = user.recommendation_weight(
            track, favorite_multiplier=favorite_multiplier
        )
        if weight <= 0.0:
            continue
        u = _deterministic_unit_interval(seed_key, tid)
        score = u ** (1.0 / weight)
        scored.append((score, tid, track))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored]


def order_tracks_by_weighted_preference(
    candidates: Sequence[Track],
    user: User,
    *,
    seed_key: str | None = None,
    rng: random.Random | None = None,
    favorite_multiplier: float = DEFAULT_FAVORITE_WEIGHT_MULTIPLIER,
) -> list[Track]:
    """Orders eligible tracks using Efraimidis-Spirakis genre-preference weights.

    Unlike `order_tracks_by_weighted_seed` (used by Jam), this always randomizes
    track order even when the user has no favorite genres (uniform weight 1.0).
    When `seed_key` is provided, keys are deterministic for cursor pagination;
    otherwise fresh random keys are drawn from `rng` (or module `random`).
    """
    chooser = rng if rng is not None else random
    scored: list[tuple[float, int, Track]] = []
    for track in candidates:
        if track.is_deleted:
            continue
        weight = user.recommendation_weight(
            track, favorite_multiplier=favorite_multiplier
        )
        if weight <= 0.0:
            continue
        tid = track.track_id or 0
        u = (
            _deterministic_unit_interval(seed_key, tid)
            if seed_key is not None
            else (1.0 - chooser.random())
        )
        score = u ** (1.0 / weight)
        scored.append((score, tid, track))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored]


__all__ = [
    "DEFAULT_FAVORITE_WEIGHT_MULTIPLIER",
    "RecommendationProfile",
    "order_tracks_by_weighted_preference",
    "order_tracks_by_weighted_seed",
    "score_track_for_user",
    "select_weighted_track",
]
