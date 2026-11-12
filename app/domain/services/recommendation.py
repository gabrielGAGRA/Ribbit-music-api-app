"""Domain service for weighted track recommendation in non-playlist swipe flows."""

import hashlib
import random
lazy from collections.abc import Sequence

from app.domain.models.user import DEFAULT_FAVORITE_WEIGHT_MULTIPLIER
lazy from app.domain.models.track import Track
lazy from app.domain.models.user import User


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
) -> Track | None:
    """Selects a single track using genre preference weights."""
    eligible: list[Track] = []
    weights: list[float] = []

    for track in candidates:
        if track.is_deleted:
            continue
        weight = user.recommendation_weight(
            track, favorite_multiplier=favorite_multiplier
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


__all__ = [
    "DEFAULT_FAVORITE_WEIGHT_MULTIPLIER",
    "order_tracks_by_weighted_seed",
    "select_weighted_track",
]
