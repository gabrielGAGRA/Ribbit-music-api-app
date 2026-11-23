"""Property-based tests for playlist deck filter coercion and matching helpers."""

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from app.application.use_cases.playlist.deck_filter_helpers import (
    coerce_int_list,
    coerce_string_list,
    extract_deck_filters_tuple,
    matches_any,
    resolve_deck_filters,
)

_LEAF_VALUES = (
    st.none() | st.text(max_size=30) | st.integers(min_value=-(10**6), max_value=10**6)
)
_RECURSIVE_VALUES = st.recursive(
    _LEAF_VALUES,
    lambda children: (
        st.lists(children, max_size=5)
        | st.lists(children, max_size=5).map(tuple)
        | st.sets(_LEAF_VALUES, max_size=5)
    ),
    max_leaves=15,
)
_JSON_SCALARS = (
    st.none() | st.booleans() | st.integers(-(10**6), 10**6) | st.text(max_size=20)
)
_JSON_VALUES = st.recursive(
    _JSON_SCALARS,
    lambda children: (
        st.lists(children, max_size=4)
        | st.dictionaries(st.text(max_size=10), children, max_size=4)
    ),
    max_leaves=10,
)
_FILTER_DICT = st.fixed_dictionaries(
    {},
    optional={
        "genre": _JSON_VALUES,
        "year": _JSON_VALUES,
        "artist": _JSON_VALUES,
        "country": _JSON_VALUES,
    },
)
_RAW_DECK_FILTERS = st.one_of(
    st.none(),
    st.text(max_size=60),
    _FILTER_DICT,
    _FILTER_DICT.map(json.dumps),
    _JSON_VALUES.map(json.dumps),
)


@given(value=_RECURSIVE_VALUES)
@settings(max_examples=50, deadline=None)
def test_coerce_string_list_invariants(value: object) -> None:
    result = coerce_string_list(value)

    assert isinstance(result, list)
    for item in result:
        assert isinstance(item, str)
        assert item != ""
        assert item == item.strip()
        assert "," not in item
    assert coerce_string_list(result) == result


@given(value=_RECURSIVE_VALUES)
@settings(max_examples=50, deadline=None)
def test_coerce_int_list_invariants(value: object) -> None:
    result = coerce_int_list(value)

    assert isinstance(result, list)
    assert all(isinstance(item, int) and not isinstance(item, bool) for item in result)
    assert coerce_int_list(result) == result


@given(
    genre=_RECURSIVE_VALUES,
    year=_RECURSIVE_VALUES,
    artist=_RECURSIVE_VALUES,
    country=_RECURSIVE_VALUES,
    raw_deck_filters=_RAW_DECK_FILTERS,
)
@settings(max_examples=50, deadline=None)
def test_resolve_deck_filters_always_returns_normalized_keys(
    genre: object,
    year: object,
    artist: object,
    country: object,
    raw_deck_filters: object,
) -> None:
    result = resolve_deck_filters(
        genre=genre,
        year=year,
        artist=artist,
        country=country,
        raw_deck_filters=raw_deck_filters,
    )

    assert set(result.keys()) == {"genre", "year", "artist", "country"}
    for key in ("genre", "artist", "country"):
        assert isinstance(result[key], list)
        assert all(
            isinstance(item, str) and item == item.strip() and item
            for item in result[key]
        )
    assert isinstance(result["year"], list)
    assert all(
        isinstance(item, int) and not isinstance(item, bool) for item in result["year"]
    )


@given(
    raw_deck_filters=st.one_of(
        st.none(),
        st.text(max_size=60),
        _FILTER_DICT.map(json.dumps),
        _JSON_VALUES.map(json.dumps),
    )
)
@settings(max_examples=50, deadline=None)
def test_extract_deck_filters_tuple_never_raises_and_normalizes(
    raw_deck_filters: str | None,
) -> None:
    result = extract_deck_filters_tuple(raw_deck_filters)

    assert isinstance(result, tuple)
    assert len(result) == 4
    genre, artist, year, country = result
    for str_list in (genre, artist, country):
        assert str_list is None or (
            isinstance(str_list, list)
            and len(str_list) > 0
            and all(
                isinstance(item, str) and item == item.strip() and item
                for item in str_list
            )
        )
    assert year is None or (
        isinstance(year, list)
        and len(year) > 0
        and all(isinstance(item, int) and not isinstance(item, bool) for item in year)
    )


@given(value=st.text(max_size=40), expected=st.lists(st.text(max_size=20), max_size=10))
@settings(max_examples=50, deadline=None)
def test_matches_any_is_case_insensitive(value: str, expected: list[str]) -> None:
    swapped_expected = [item.swapcase() for item in expected]
    assert matches_any(value, expected) == matches_any(
        value.swapcase(), swapped_expected
    )
