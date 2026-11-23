"""Portuguese country name dictionary and alias matching helpers."""

import unicodedata
lazy from collections.abc import Sequence


def _fold(value: str) -> str:
    ascii_folded = "".join(
        ch
        for ch in unicodedata.normalize("NFKD", value.strip())
        if not unicodedata.combining(ch)
    )
    return " ".join(ascii_folded.casefold().split())


_COUNTRY_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Brasil", ("br", "bra", "brazil", "brasil")),
    (
        "Estados Unidos",
        (
            "us",
            "usa",
            "eua",
            "united states",
            "united states of america",
            "estados unidos",
        ),
    ),
    (
        "Reino Unido",
        (
            "gb",
            "gbr",
            "uk",
            "united kingdom",
            "great britain",
            "england",
            "reino unido",
        ),
    ),
    ("Canadá", ("ca", "can", "canada")),
    ("Japão", ("jp", "jpn", "japan", "japao")),
    ("França", ("fr", "fra", "france", "franca")),
    ("Alemanha", ("de", "deu", "ger", "germany", "alemanha")),
    ("Coreia do Sul", ("kr", "kor", "south korea", "korea", "coreia do sul")),
    ("Portugal", ("pt", "prt", "portugal")),
    ("Espanha", ("es", "esp", "spain", "espanha")),
    ("Itália", ("it", "ita", "italy", "italia")),
    ("México", ("mx", "mex", "mexico")),
    ("Argentina", ("ar", "arg", "argentina")),
    ("Austrália", ("au", "aus", "australia")),
    ("Suécia", ("se", "swe", "sweden", "suecia")),
    ("Noruega", ("no", "nor", "norway", "noruega")),
    (
        "Países Baixos",
        ("nl", "nld", "netherlands", "holland", "holanda", "paises baixos"),
    ),
    ("Irlanda", ("ie", "irl", "ireland", "irlanda")),
    ("Colômbia", ("co", "col", "colombia")),
    ("Chile", ("cl", "chl", "chile")),
    ("Peru", ("pe", "per", "peru")),
    ("Uruguai", ("uy", "ury", "uruguay", "uruguai")),
    ("Bélgica", ("be", "bel", "belgium", "belgica")),
    ("Suíça", ("ch", "che", "switzerland", "suica")),
    ("Áustria", ("at", "aut", "austria")),
    ("Nova Zelândia", ("nz", "nzl", "new zealand", "nova zelandia")),
    ("África do Sul", ("za", "zaf", "south africa", "africa do sul")),
    ("Índia", ("in", "ind", "india")),
    ("China", ("cn", "chn", "china")),
    ("Rússia", ("ru", "rus", "russia")),
    ("Polônia", ("pl", "pol", "poland", "polonia")),
    ("Turquia", ("tr", "tur", "turkey", "turquia")),
    ("Nigéria", ("ng", "nga", "nigeria")),
    ("Jamaica", ("jm", "jam", "jamaica")),
    ("Porto Rico", ("pr", "pri", "puerto rico", "porto rico")),
    ("Cuba", ("cu", "cub", "cuba")),
    ("Finlândia", ("fi", "fin", "finland", "finlandia")),
    ("Dinamarca", ("dk", "dnk", "denmark", "dinamarca")),
    ("Grécia", ("gr", "grc", "greece", "grecia")),
    ("Israel", ("il", "isr", "israel")),
    ("Venezuela", ("ve", "ven", "venezuela")),
    ("Equador", ("ec", "ecu", "ecuador", "equador")),
    ("Paraguai", ("py", "pry", "paraguay", "paraguai")),
    ("Bolívia", ("bo", "bol", "bolivia")),
    (
        "República Dominicana",
        ("do", "dom", "dominican republic", "republica dominicana"),
    ),
    ("Filipinas", ("ph", "phl", "philippines", "filipinas")),
    ("Indonésia", ("id", "idn", "indonesia")),
    ("Tailândia", ("th", "tha", "thailand", "tailandia")),
    ("Taiwan", ("tw", "twn", "taiwan")),
    ("Hong Kong", ("hk", "hkg", "hong kong")),
    ("Singapura", ("sg", "sgp", "singapore", "singapura")),
    ("Egito", ("eg", "egy", "egypt", "egito")),
    ("Marrocos", ("ma", "mar", "morocco", "marrocos")),
    ("Ucrânia", ("ua", "ukr", "ukraine", "ucrania")),
    (
        "República Tcheca",
        ("cz", "cze", "czechia", "czech republic", "republica tcheca"),
    ),
    ("Hungria", ("hu", "hun", "hungary", "hungria")),
    ("Romênia", ("ro", "rou", "romania", "romenia")),
    ("Croácia", ("hr", "hrv", "croatia", "croacia")),
    ("Sérvia", ("rs", "srb", "serbia", "servia")),
    ("Islândia", ("is", "isl", "iceland", "islandia")),
)

COUNTRY_CODE_TO_PT: dict[str, str] = {
    _fold(alias): canonical
    for canonical, aliases in _COUNTRY_GROUPS
    for alias in (canonical, *aliases)
}

_PT_TO_ALIASES: dict[str, tuple[str, ...]] = {
    canonical: tuple(dict.fromkeys((canonical, *aliases)))
    for canonical, aliases in _COUNTRY_GROUPS
}


def translate_country_to_pt(value: str | None) -> str | None:
    """Translates an ISO code or country alias to its canonical Portuguese name."""
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return COUNTRY_CODE_TO_PT.get(_fold(cleaned), cleaned)


def expand_country_terms(values: Sequence[str]) -> tuple[list[str], list[str]]:
    """Expands country filter inputs into (exact_short_codes, name_like_terms)."""
    exact_codes: list[str] = []
    name_terms: list[str] = []
    seen_codes: set[str] = set()
    seen_names: set[str] = set()
    for raw in values:
        cleaned = raw.strip()
        if not cleaned:
            continue
        canonical = COUNTRY_CODE_TO_PT.get(_fold(cleaned))
        expanded = _PT_TO_ALIASES[canonical] if canonical is not None else (cleaned,)
        for term in expanded:
            low = term.casefold()
            if len(low) <= 3:
                if low not in seen_codes:
                    seen_codes.add(low)
                    exact_codes.append(low)
            elif low not in seen_names:
                seen_names.add(low)
                name_terms.append(term)
    return exact_codes, name_terms


def country_matches(track_country: str | None, expected: Sequence[str]) -> bool:
    """Checks whether a track's country matches any expected name or ISO code."""
    if not expected:
        return True
    if not track_country or not track_country.strip():
        return False
    track_pt = translate_country_to_pt(track_country)
    track_folded = _fold(track_country)
    for raw in expected:
        cleaned = raw.strip()
        if not cleaned:
            continue
        exp_pt = translate_country_to_pt(cleaned)
        if track_pt is not None and exp_pt is not None and track_pt == exp_pt:
            return True
        exp_folded = _fold(cleaned)
        if len(exp_folded) > 3 and exp_folded in track_folded:
            return True
    return False


__all__ = [
    "COUNTRY_CODE_TO_PT",
    "country_matches",
    "expand_country_terms",
    "translate_country_to_pt",
]
