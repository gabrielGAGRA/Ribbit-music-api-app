"""DB-backed genre dictionary and token-aware matching for discovery and filtering."""

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


_GENRE_CATALOG_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Rock",
        (
            "rock",
            "hard rock",
            "rock-n-roll",
            "rockabilly",
            "psych-rock",
            "prog-rock/art rock",
            "rock y alternativo",
            "jam bands",
            "indie rock",
            "garage",
            "new wave",
            "classic rock",
            "soft rock",
            "pop rock",
            "punk rock",
            "psychedelic rock",
            "progressive rock",
            "garage rock",
            "roc",
        ),
    ),
    (
        "Pop",
        (
            "pop",
            "power-pop",
            "synth-pop",
            "french pop",
            "arabic pop",
            "indian pop",
            "bollywood",
            "indie pop",
            "afro-pop",
            "christmas: pop",
            "dance pop",
            "electropop",
            "dream pop",
            "art pop",
            "chamber pop",
            "synthpop",
        ),
    ),
    (
        "Hip Hop",
        (
            "hip-hop",
            "hip hop",
            "hiphop",
            "rap",
            "alternative rap",
            "hardcore rap",
            "west coast rap",
            "hip-hop in russian",
            "trap",
            "boom bap",
            "gangsta rap",
        ),
    ),
    (
        "Funk",
        ("funk", "baile funk", "funk carioca", "funk brasileiro", "p-funk", "g-funk"),
    ),
    (
        "Alternative",
        (
            "alternative",
            "alternativo",
            "adult alternative",
            "alternative rock",
            "emo",
            "rock y alternativo",
        ),
    ),
    (
        "R&B",
        (
            "r&b",
            "r b",
            "rnb",
            "contemporary r&b",
            "christmas: r&b",
            "soul",
            "neo-soul",
            "motown",
        ),
    ),
    ("Sertanejo", ("sertanejo", "sertanejo universitario")),
    (
        "Dance",
        (
            "dance",
            "disco",
            "club",
            "house",
            "deep-house",
            "chicago-house",
            "progressive-house",
            "afro house",
            "groove",
            "amapiano",
        ),
    ),
    ("MPB", ("mpb", "brazilian", "musica popular brasileira")),
    (
        "Country",
        (
            "country",
            "honky-tonk",
            "bluegrass",
            "traditional country",
            "americana",
            "christmas: country",
        ),
    ),
    (
        "Latin",
        (
            "latin",
            "latina",
            "música tropical",
            "musica tropical",
            "música mexicana",
            "musica mexicana",
            "reggaeton",
            "salsa",
            "bachata",
        ),
    ),
    ("Pagode", ("pagode",)),
    (
        "Soundtrack",
        (
            "soundtrack",
            "tv soundtrack",
            "disney",
            "anime",
            "show-tunes",
            "musicals",
            "trilha sonora",
            "ost",
            "score",
        ),
    ),
    (
        "Electronic",
        (
            "electronic",
            "eletrônica",
            "eletronica",
            "electronica",
            "detroit-techno",
            "techno",
            "electro",
            "edm",
            "idm",
            "idm/experimental",
            "ambient",
            "industrial",
            "breakbeat",
            "dubstep",
            "trip-hop",
            "downtempo",
            "drum-and-bass",
            "jungle/drum'n'bass",
            "dnb",
            "trance",
            "chill",
            "new-age",
            "new age",
            "synthwave",
            "house",
            "deep-house",
            "chicago-house",
            "progressive-house",
            "afro house",
            "lo-fi",
            "lofi",
        ),
    ),
    ("Indie", ("indie", "indie pop", "indie rock", "indie folk")),
    ("Folk", ("folk", "acoustic", "singer/songwriter", "afro-folk", "indie folk")),
    ("Reggae", ("reggae", "dub", "dancehall", "modern dancehall", "ska")),
    (
        "Metal",
        (
            "metal",
            "grindcore",
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
    ("K-Pop", ("k-pop", "k pop", "j-pop", "j pop")),
    ("Forró", ("forro", "forró", "piseiro", "xote")),
    ("Samba", ("samba",)),
    (
        "Punk",
        (
            "punk",
            "punk rock",
            "pop punk",
            "post-punk",
            "hardcore",
            "hardcore punk",
            "emo",
        ),
    ),
    ("Jazz", ("jazz", "contemporary jazz", "smooth jazz", "bebop", "swing", "lounge")),
    ("Axé", ("axe", "axé")),
    ("Bossa Nova", ("bossa nova",)),
    ("Soul", ("soul", "neo-soul", "motown")),
    ("Blues", ("blues", "delta blues", "electric blues", "blues rock")),
    ("Gospel", ("gospel", "praise & worship")),
    ("Grunge", ("grunge", "post-grunge")),
    (
        "Classical",
        (
            "classical",
            "clássica",
            "classica",
            "erudita",
            "classical crossover",
            "opera",
            "piano",
            "instrumental",
            "orchestral",
            "symphony",
            "baroque",
        ),
    ),
)

CATALOG_GENRES: tuple[str, ...] = tuple(
    canonical for canonical, _ in _GENRE_CATALOG_GROUPS
)

GENRE_CATALOG_DICT: dict[str, tuple[str, ...]] = dict(_GENRE_CATALOG_GROUPS)

_CANONICAL_TO_DB_VALUES: dict[str, tuple[str, ...]] = {
    _fold_genre(canonical): tuple(
        dict.fromkeys([canonical.casefold(), *(a.casefold() for a in aliases)])
    )
    for canonical, aliases in _GENRE_CATALOG_GROUPS
}

_CANONICAL_TO_FOLDED_ALIASES: dict[str, tuple[str, ...]] = {
    _fold_genre(canonical): tuple(
        dict.fromkeys(folded for a in aliases if (folded := _fold_genre(a)))
    )
    for canonical, aliases in _GENRE_CATALOG_GROUPS
}

GENRE_DB_TO_CANONICAL: dict[str, str] = {}
for _canonical, _aliases in _GENRE_CATALOG_GROUPS:
    GENRE_DB_TO_CANONICAL.setdefault(_canonical.casefold(), _canonical)
    GENRE_DB_TO_CANONICAL.setdefault(_fold_genre(_canonical), _canonical)
for _canonical, _aliases in _GENRE_CATALOG_GROUPS:
    for _alias in _aliases:
        GENRE_DB_TO_CANONICAL.setdefault(_alias.casefold(), _canonical)
        _folded_alias = _fold_genre(_alias)
        if _folded_alias:
            GENRE_DB_TO_CANONICAL.setdefault(_folded_alias, _canonical)

_PORTUGUESE_AND_SHORTHAND_MAP: dict[str, str] = {
    "eletronica": "electronic",
    "alternativo": "alternative",
    "classica": "classical",
    "erudita": "classical",
    "latina": "latin",
    "hiphop": "hip hop",
    "rnb": "r b",
    "lofi": "electronic",
    "trilha sonora": "soundtrack",
    "rap": "hip hop",
    "mpb": "mpb",
    "brazilian": "mpb",
    "detroit techno": "electronic",
}


def _resolve_group_key(folded: str) -> str | None:
    if folded in _CANONICAL_TO_FOLDED_ALIASES:
        return folded
    return _PORTUGUESE_AND_SHORTHAND_MAP.get(folded)


def expand_genre_aliases(genre: str) -> tuple[str, ...]:
    """Expands a user genre preference into folded token-safe aliases."""
    folded = _fold_genre(genre)
    if not folded:
        return ()
    group_key = _resolve_group_key(folded)
    if group_key is not None:
        return _CANONICAL_TO_FOLDED_ALIASES[group_key]
    return (folded,)


def expand_genre_db_values(genre: str) -> tuple[str, ...]:
    """Expands a user genre preference into exact lowercase raw DB genre values."""
    cleaned = genre.strip().casefold()
    folded = _fold_genre(genre)
    if not cleaned and not folded:
        return ()
    group_key = _resolve_group_key(folded)
    if group_key is not None:
        return _CANONICAL_TO_DB_VALUES[group_key]
    return (cleaned,) if cleaned else (folded,)


def _token_subsequence_match(haystack_tokens: tuple[str, ...], needle: str) -> bool:
    needle_tokens = tuple(needle.split())
    if not needle_tokens or len(needle_tokens) > len(haystack_tokens):
        return False
    return any(
        haystack_tokens[i : i + len(needle_tokens)] == needle_tokens
        for i in range(len(haystack_tokens) - len(needle_tokens) + 1)
    )


def genre_matches_preference(track_genre: str, preference: str) -> bool:
    """Checks whether track_genre matches preference directly, by DB value, or by token."""
    raw_lower = track_genre.strip().casefold()
    if not raw_lower:
        return False
    if raw_lower in expand_genre_db_values(preference):
        return True
    track_folded = _fold_genre(track_genre)
    if not track_folded:
        return False
    track_tokens = tuple(track_folded.split())
    for alias in expand_genre_aliases(preference):
        if track_folded == alias or _token_subsequence_match(track_tokens, alias):
            return True
    return False


__all__ = [
    "CATALOG_GENRES",
    "GENRE_CATALOG_DICT",
    "GENRE_DB_TO_CANONICAL",
    "expand_genre_aliases",
    "expand_genre_db_values",
    "genre_matches_preference",
]
