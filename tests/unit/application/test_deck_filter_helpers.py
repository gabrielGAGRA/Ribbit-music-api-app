"""Unit tests for deck filter helper functions."""

from app.application.use_cases.playlist.deck_filter_helpers import (
    coerce_int_list,
    coerce_string_list,
    extract_deck_filters_tuple,
    extract_dict_filters,
    matches_any,
    matches_track_filters,
    resolve_deck_filters,
)
from app.domain.models.track import Track


def test_coerce_string_list_handles_none_empty_single_and_collections() -> None:
    assert coerce_string_list(None) == []
    assert coerce_string_list("") == []
    assert coerce_string_list("  ") == []
    assert coerce_string_list("rock") == ["rock"]
    assert coerce_string_list("rock, pop , indie") == ["rock", "pop", "indie"]
    assert coerce_string_list(["rock", ["pop", "jazz"]]) == ["rock", "pop", "jazz"]
    assert coerce_string_list({"indie", ""}) == ["indie"]


def test_coerce_int_list_handles_none_empty_and_conversions() -> None:
    assert coerce_int_list(None) == []
    assert coerce_int_list("") == []
    assert coerce_int_list("invalid") == []
    assert coerce_int_list(2020) == [2020]
    assert coerce_int_list(" 1999 ") == [1999]
    assert coerce_int_list([1990, "2000", ["2010"]]) == [1990, 2000, 2010]
    assert coerce_int_list([1990, "not_int"]) == [1990]


def test_matches_any_case_insensitivity() -> None:
    assert matches_any(None, []) is True
    assert matches_any("Rock Music", ["rock"]) is True
    assert matches_any("Pop", ["rock", "jazz"]) is False
    assert matches_any(None, ["rock"]) is False


def test_matches_track_filters_all_criteria() -> None:
    track = Track(
        track_id=1,
        title="Test Track",
        artist="Queen",
        duration_seconds=180,
        genre="Classic Rock",
        release_year=1975,
        country="United Kingdom",
    )

    assert (
        matches_track_filters(
            track, genre=["rock"], year=[1975], artist=["queen"], country=["kingdom"]
        )
        is True
    )
    assert matches_track_filters(track, genre=["pop"]) is False
    assert matches_track_filters(track, year=[1980]) is False
    assert matches_track_filters(track, artist=["Beatles"]) is False
    assert matches_track_filters(track, country=["Brazil"]) is False


def test_extract_dict_filters_and_resolve_deck_filters() -> None:
    extracted = extract_dict_filters(
        {
            "genre": "Rock, Jazz",
            "year": "1990",
            "artist": ["Queen"],
            "country": "UK",
        }
    )
    assert extracted["genre"] == ["Rock", "Jazz"]
    assert extracted["year"] == [1990]
    assert extracted["artist"] == ["Queen"]
    assert extracted["country"] == ["UK"]

    resolved = resolve_deck_filters(
        genre="Pop",
        year=2000,
        artist="Artist",
        country="US",
        raw_deck_filters=None,
    )
    assert resolved["genre"] == ["Pop"]
    assert resolved["year"] == [2000]

    # Valid JSON payload takes precedence
    resolved_json = resolve_deck_filters(
        raw_deck_filters='{"genre": "Electronic", "year": [2020]}',
    )
    assert resolved_json["genre"] == ["Electronic"]
    assert resolved_json["year"] == [2020]


def test_extract_deck_filters_tuple() -> None:
    assert extract_deck_filters_tuple(None) == (None, None, None, None)
    assert extract_deck_filters_tuple("invalid json") == (None, None, None, None)
    assert extract_deck_filters_tuple('["not", "a", "dict"]') == (
        None,
        None,
        None,
        None,
    )

    genres, artists, years, countries = extract_deck_filters_tuple(
        '{"genre": "rock, pop", "year": "1990", "artist": ["Queen"], "country": "UK"}'
    )
    assert genres == ["rock", "pop"]
    assert artists == ["Queen"]
    assert years == [1990]
    assert countries == ["UK"]
