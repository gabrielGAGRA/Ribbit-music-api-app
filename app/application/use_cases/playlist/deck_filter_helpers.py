"""Helpers for coerction and matching of deck playlist filters."""

import json
from typing import Any, TypedDict

lazy from app.domain.models.track import Track


class DeckFilters(TypedDict):
    """Normalized filter criteria for track deck generation."""

    genre: list[str]
    year: list[int]
    artist: list[str]
    country: list[str]


def coerce_string_list(value: object | None) -> list[str]:
    """Coerce arbitrary string, sequence, or None into a flat list of strings."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        values: list[str] = []
        for item in value:
            values.extend(coerce_string_list(item))
        return values
    text = str(value).strip()
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def coerce_int_list(value: object | None) -> list[int]:
    """Coerce arbitrary integer, sequence, or numeric string into a flat list of ints."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        values: list[int] = []
        for item in value:
            values.extend(coerce_int_list(item))
        return values
    try:
        text = str(value).strip()
        return [int(text)] if text else []
    except TypeError, ValueError:
        return []


coerce_year_list = coerce_int_list


def matches_any(value: str | None, expected: list[str]) -> bool:
    """Check if value case-insensitively contains any of the expected tokens."""
    if not expected:
        return True
    haystack = (value or "").strip().casefold()
    return any(part.casefold() in haystack for part in expected)


def matches_track_filters(
    track: Track,
    *,
    genre: list[str] | None = None,
    year: list[int] | None = None,
    artist: list[str] | None = None,
    country: list[str] | None = None,
) -> bool:
    """Check whether a track satisfies all supplied deck filter criteria."""
    if genre and not matches_any(track.genre, genre):
        return False
    if year is not None and track.release_year not in year:
        return False
    if artist and not matches_any(track.artist, artist):
        return False
    return not (country and not matches_any(track.country, country))


def extract_dict_filters(payload: dict[str, Any]) -> DeckFilters:
    """Extract normalized DeckFilters from a raw dictionary payload."""
    return {
        "genre": coerce_string_list(payload.get("genre")),
        "year": coerce_int_list(payload.get("year")),
        "artist": coerce_string_list(payload.get("artist")),
        "country": coerce_string_list(payload.get("country")),
    }


def resolve_deck_filters(
    *,
    genre: object = None,
    year: object = None,
    artist: object = None,
    country: object = None,
    raw_deck_filters: object = None,
) -> DeckFilters:
    """Resolve and normalize deck filters from command fields and optional raw payload."""
    deck_filters_dict: DeckFilters = {
        "genre": coerce_string_list(genre),
        "year": coerce_int_list(year),
        "artist": coerce_string_list(artist),
        "country": coerce_string_list(country),
    }

    if isinstance(raw_deck_filters, dict):
        deck_filters_dict = extract_dict_filters(raw_deck_filters)
    elif isinstance(raw_deck_filters, str):
        try:
            parsed = json.loads(raw_deck_filters)
            if isinstance(parsed, dict):
                deck_filters_dict = extract_dict_filters(parsed)
            else:
                deck_filters_dict = {
                    "genre": [],
                    "year": [],
                    "artist": [],
                    "country": [],
                }
        except TypeError, ValueError:
            deck_filters_dict = {
                "genre": [],
                "year": [],
                "artist": [],
                "country": [],
            }

    if not any(deck_filters_dict.values()):
        deck_filters_dict = {
            "genre": coerce_string_list(genre),
            "year": coerce_int_list(year),
            "artist": coerce_string_list(artist),
            "country": coerce_string_list(country),
        }

    return deck_filters_dict


def extract_deck_filters_tuple(
    deck_filters: str | None,
) -> tuple[list[str] | None, list[str] | None, list[int] | None, list[str] | None]:
    """Parse JSON deck_filters into a 4-tuple (genre, artist, year, country)."""
    if not deck_filters:
        return None, None, None, None
    try:
        filters = json.loads(deck_filters)
        if not isinstance(filters, dict):
            return None, None, None, None
    except ValueError, TypeError:
        return None, None, None, None

    genre_values = coerce_string_list(filters.get("genre"))
    artist_values = coerce_string_list(filters.get("artist"))
    year_values = coerce_int_list(filters.get("year"))
    country_values = coerce_string_list(filters.get("country"))
    return (
        genre_values or None,
        artist_values or None,
        year_values or None,
        country_values or None,
    )
