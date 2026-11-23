"""Genre alias dictionary and token-aware matching for discovery and filtering."""

import re
import unicodedata

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _fold_genre(value: str) -> str:
    ascii_folded = "".join(
        ch
        for ch in unicodedata.normalize("NFKD", value.strip())
        if not unicodedata.combining(ch)
    )
    return " ".join(_NON_ALNUM_RE.sub(" ", ascii_folded.casefold()).split())


_GENRE_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "rock",
        (
            "rock",
            "roc",
            "alternative rock",
            "hard rock",
            "indie rock",
            "classic rock",
            "punk rock",
            "soft rock",
            "pop rock",
            "psychedelic rock",
            "progressive rock",
            "garage rock",
            "grunge",
        ),
    ),
    (
        "pop",
        (
            "pop",
            "synthpop",
            "electropop",
            "indie pop",
            "k pop",
            "j pop",
            "dance pop",
            "art pop",
            "dream pop",
            "chamber pop",
        ),
    ),
    (
        "hip hop",
        ("hip hop", "hiphop", "rap", "trap", "boom bap", "gangsta rap"),
    ),
    (
        "electronic",
        (
            "electronic",
            "eletronica",
            "edm",
            "house",
            "techno",
            "trance",
            "dubstep",
            "drum and bass",
            "dnb",
            "ambient",
            "synthwave",
            "electro",
            "dance",
            "idm",
            "lo fi",
            "lofi",
        ),
    ),
    (
        "metal",
        (
            "metal",
            "heavy metal",
            "black metal",
            "death metal",
            "thrash metal",
            "power metal",
            "doom metal",
            "metalcore",
            "nu metal",
            "progressive metal",
        ),
    ),
    (
        "jazz",
        ("jazz", "contemporary jazz", "smooth jazz", "bebop", "swing", "bossa nova"),
    ),
    (
        "indie",
        (
            "indie",
            "indie rock",
            "indie pop",
            "indie folk",
            "alternative",
            "alternative rock",
        ),
    ),
    (
        "classical",
        (
            "classical",
            "classica",
            "erudita",
            "orchestral",
            "symphony",
            "baroque",
            "opera",
        ),
    ),
    (
        "country",
        ("country", "sertanejo", "americana", "bluegrass"),
    ),
    (
        "funk",
        ("funk", "baile funk", "funk carioca", "funk brasileiro", "p funk", "g funk"),
    ),
    (
        "r b",
        ("r b", "rnb", "contemporary r b", "soul", "neo soul", "motown"),
    ),
    (
        "blues",
        ("blues", "delta blues", "electric blues", "blues rock"),
    ),
    (
        "folk",
        ("folk", "indie folk", "acoustic", "singer songwriter", "mpb"),
    ),
    (
        "punk",
        ("punk", "punk rock", "pop punk", "post punk", "hardcore punk"),
    ),
    (
        "latin",
        (
            "latin",
            "latina",
            "reggaeton",
            "salsa",
            "bachata",
            "samba",
            "pagode",
            "forro",
            "mpb",
            "bossa nova",
            "axe",
        ),
    ),
    ("lo fi", ("lo fi", "lofi", "chillhop")),
    ("ambient", ("ambient", "downtempo", "new age", "chillout")),
    ("techno", ("techno", "minimal techno", "detroit techno", "acid techno")),
    ("grunge", ("grunge", "post grunge")),
    ("reggae", ("reggae", "dub", "ska", "dancehall")),
    ("soundtrack", ("soundtrack", "trilha sonora", "ost", "score")),
    ("sertanejo", ("sertanejo", "sertanejo universitario")),
    ("mpb", ("mpb", "bossa nova", "musica popular brasileira")),
    ("samba", ("samba", "pagode")),
    ("forro", ("forro", "piseiro", "xote")),
)

_CANONICAL_TO_ALIASES: dict[str, tuple[str, ...]] = {
    canonical: tuple(dict.fromkeys(aliases)) for canonical, aliases in _GENRE_GROUPS
}

_ALIAS_TO_CANONICAL: dict[str, str] = {}
for _canonical, _aliases in _GENRE_GROUPS:
    _ALIAS_TO_CANONICAL.setdefault(_canonical, _canonical)
    for _alias in _aliases:
        _ALIAS_TO_CANONICAL.setdefault(_alias, _canonical)


def expand_genre_aliases(genre: str) -> tuple[str, ...]:
    """Expands a user genre preference into normalized aliases/subgenres."""
    folded = _fold_genre(genre)
    if not folded:
        return ()
    if folded in _CANONICAL_TO_ALIASES:
        return _CANONICAL_TO_ALIASES[folded]
    canonical = _ALIAS_TO_CANONICAL.get(folded)
    if canonical is not None and folded in (
        "eletronica",
        "classica",
        "erudita",
        "latina",
        "hiphop",
        "rnb",
        "lofi",
        "trilha sonora",
    ):
        return _CANONICAL_TO_ALIASES[canonical]
    return (folded,)


def _token_subsequence_match(haystack_tokens: tuple[str, ...], needle: str) -> bool:
    needle_tokens = tuple(needle.split())
    if not needle_tokens or len(needle_tokens) > len(haystack_tokens):
        return False
    return any(
        haystack_tokens[i : i + len(needle_tokens)] == needle_tokens
        for i in range(len(haystack_tokens) - len(needle_tokens) + 1)
    )


def genre_matches_preference(track_genre: str, preference: str) -> bool:
    """Checks whether track_genre matches preference directly, by alias, or by token."""
    track_folded = _fold_genre(track_genre)
    if not track_folded:
        return False
    track_tokens = tuple(track_folded.split())
    for alias in expand_genre_aliases(preference):
        if track_folded == alias or _token_subsequence_match(track_tokens, alias):
            return True
    return False


__all__ = [
    "expand_genre_aliases",
    "genre_matches_preference",
]
