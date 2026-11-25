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

    assert (
        matches_track_filters(
            Track(
                track_id=2,
                title="Rap",
                artist="A",
                duration_seconds=180,
                genre="hip-hop",
            ),
            genre=["Hip Hop"],
        )
        is True
    )
    assert (
        matches_track_filters(
            Track(
                track_id=3, title="Soul", artist="A", duration_seconds=180, genre="r&b"
            ),
            genre=["R&B"],
        )
        is True
    )
    assert (
        matches_track_filters(
            Track(
                track_id=4,
                title="Forro",
                artist="A",
                duration_seconds=180,
                genre="forro",
            ),
            genre=["Forró"],
        )
        is True
    )
    assert (
        matches_track_filters(
            Track(
                track_id=5, title="Axe", artist="A", duration_seconds=180, genre="axe"
            ),
            genre=["Axé"],
        )
        is True
    )
    assert (
        matches_track_filters(
            Track(
                track_id=2,
                title="Rap",
                artist="A",
                duration_seconds=180,
                genre="hip-hop",
            ),
            genre=["Hip Hop"],
        )
        is True
    )
    assert (
        matches_track_filters(
            Track(
                track_id=3, title="Soul", artist="A", duration_seconds=180, genre="r&b"
            ),
            genre=["R&B"],
        )
        is True
    )
    assert (
        matches_track_filters(
            Track(
                track_id=4,
                title="Forro",
                artist="A",
                duration_seconds=180,
                genre="forro",
            ),
            genre=["Forró"],
        )
        is True
    )
    assert (
        matches_track_filters(
            Track(
                track_id=5, title="Axe", artist="A", duration_seconds=180, genre="axe"
            ),
            genre=["Axé"],
        )
        is True
    )


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


def test_portuguese_country_dictionary_translation_and_filter_matching() -> None:
    from app.domain.services.country_names import (
        country_matches,
        expand_country_terms,
        translate_country_to_pt,
    )

    assert translate_country_to_pt("BR") == "Brasil"
    assert translate_country_to_pt("usa") == "Estados Unidos"
    assert translate_country_to_pt("US") == "Estados Unidos"
    assert translate_country_to_pt("GB") == "Reino Unido"
    assert translate_country_to_pt("United Kingdom") == "Reino Unido"
    assert translate_country_to_pt("kr") == "Coreia do Sul"
    assert translate_country_to_pt(None) is None

    assert country_matches("BR", ["Brasil"]) is True
    assert country_matches("USA", ["Estados Unidos"]) is True
    assert country_matches("US", ["Estados Unidos"]) is True
    assert country_matches("GB", ["Reino Unido"]) is True
    assert country_matches("Brasil", ["BR"]) is True
    assert country_matches("Australia", ["Estados Unidos"]) is False

    exact_codes, name_terms = expand_country_terms(["Estados Unidos"])
    assert "us" in exact_codes and "usa" in exact_codes
    assert any(t.lower() == "estados unidos" for t in name_terms)
