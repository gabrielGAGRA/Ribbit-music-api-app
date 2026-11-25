"""SQLite implementation of the track persistence port."""

import random
import re
from datetime import UTC, datetime
lazy import sqlite3
lazy from collections.abc import Sequence

from app.application.dtos.admin_dtos import AdminCatalogTrackResult
from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.track import Track, TrackId
from app.domain.services.genre_names import (
    expand_genre_aliases,
    expand_genre_db_values,
    genre_matches_preference,
)
from app.infrastructure.repositories.connection import transaction

_GENRE_TOKEN_TRANSLATION = str.maketrans("-/&,.;:()[]!", "            ")
_RANDOM_ORDER_MAX_ROWS = 250_000


def _normalize_genre_tokens(value: str) -> str:
    return f" {value.translate(_GENRE_TOKEN_TRANSLATION).casefold()} "


def _sqlite_translate(value: str | None, from_chars: str, to_chars: str) -> str | None:
    if value is None:
        return None

    translation_table = {
        ord(char): to_chars[index] if index < len(to_chars) else None
        for index, char in enumerate(from_chars)
    }
    return value.translate(translation_table)


def _row_to_track(row: sqlite3.Row) -> Track:
    created_at = (
        datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
    )
    keys = row.keys() if hasattr(row, "keys") else ()
    average_rating = (
        float(row["avg_rating"])
        if "avg_rating" in keys and row["avg_rating"] is not None
        else None
    )
    review_count = (
        int(row["review_count"])
        if "review_count" in keys and row["review_count"] is not None
        else 0
    )
    return Track(
        track_id=row["track_id"],
        title=row["title"],
        artist=row["artist"],
        duration_seconds=row["duration_seconds"],
        genre=row["genre"],
        spotify_id=row["spotify_id"],
        album=None,
        country=row["country"],
        release_year=row["release_year"],
        cover_url=row["cover_url"],
        itunes_preview_url=row["itunes_preview_url"],
        explicit=bool(row["explicit"]),
        is_deleted=bool(row["is_deleted"]),
        created_at=created_at,
        average_rating=average_rating,
        review_count=review_count,
    )


def _normalize_string_sequence(value: str | Sequence[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []
    cleaned_items: list[str] = []
    for item in value:
        cleaned = (item if isinstance(item, str) else str(item)).strip()
        if cleaned:
            cleaned_items.append(cleaned)
    return cleaned_items


def _normalize_year_sequence(value: int | Sequence[int] | None) -> list[int]:
    if value is None:
        return []
    if isinstance(value, int):
        return [value]
    results: list[int] = []
    for item in value:
        if isinstance(item, int):
            results.append(item)
        else:
            try:
                results.append(int(str(item).strip()))
            except TypeError, ValueError:
                continue
    return results


_DIACRITIC_CHARS = re.compile(r"[aeioucáàãâäéèêëíìîïóòõôöúùûüçñ]", re.IGNORECASE)


def _to_flexible_like(term: str) -> str:
    cleaned = term.strip()
    if len(cleaned) < 3:
        return cleaned
    return _DIACRITIC_CHARS.sub("_", cleaned)


def _append_like_clause(
    conditions: list[str],
    params: list[object],
    column: str,
    values: list[str],
) -> None:
    if not values:
        return
    clauses: list[str] = []
    for v in values:
        exact = f"%{v.lower()}%"
        flex = f"%{_to_flexible_like(v)}%"
        if exact == flex:
            clauses.append(f"lower({column}) LIKE ?")
            params.append(exact)
        else:
            clauses.append(f"(lower({column}) LIKE ? OR {column} LIKE ?)")
            params.extend([exact, flex])
    conditions.append(f"({' OR '.join(clauses)})")


def _append_country_clause(
    conditions: list[str],
    params: list[object],
    values: list[str],
    *,
    column: str = "t.country",
) -> None:
    if not values:
        return
    from app.domain.services.country_names import expand_country_terms  # noqa: PLC0415

    exact_codes, name_terms = expand_country_terms(values)
    clauses: list[str] = []
    if exact_codes:
        placeholders = ",".join("?" for _ in exact_codes)
        clauses.append(f"lower({column}) IN ({placeholders})")
        params.extend(exact_codes)
    for v in name_terms:
        exact = f"%{v.lower()}%"
        flex = f"%{_to_flexible_like(v)}%"
        if exact == flex:
            clauses.append(f"lower({column}) LIKE ?")
            params.append(exact)
        else:
            clauses.append(f"(lower({column}) LIKE ? OR {column} LIKE ?)")
            params.extend([exact, flex])
    if clauses:
        conditions.append(f"({' OR '.join(clauses)})")


def _normalized_genre_sql(column: str) -> str:
    return f"' ' || lower(TRANSLATE({column}, '-/&,.;:()[]!', '            ')) || ' '"


def _build_genre_match_sql(
    column: str,
    values: Sequence[str],
) -> tuple[list[str], list[object]]:
    db_values = list(
        dict.fromkeys(
            val for v in values if v.strip() for val in expand_genre_db_values(v)
        )
    )
    folded_aliases = list(
        dict.fromkeys(
            alias for v in values if v.strip() for alias in expand_genre_aliases(v)
        )
    )
    clauses: list[str] = []
    clause_params: list[object] = []
    if db_values:
        placeholders = ",".join("?" for _ in db_values)
        clauses.append(f"lower({column}) IN ({placeholders})")
        clause_params.extend(db_values)
    normalized_col = _normalized_genre_sql(column)
    for alias in folded_aliases:
        clauses.append(f"instr({normalized_col}, ?) > 0")
        clause_params.append(f" {alias} ")
    return clauses, clause_params


def _append_genre_clause(
    conditions: list[str],
    params: list[object],
    column: str,
    values: list[str],
) -> None:
    if not values:
        return
    clauses, clause_params = _build_genre_match_sql(column, values)
    if clauses:
        conditions.append(f"({' OR '.join(clauses)})")
        params.extend(clause_params)


def _append_in_clause(
    conditions: list[str],
    params: list[object],
    column: str,
    values: list[int],
) -> None:
    if not values:
        return
    placeholders = ",".join("?" for _ in values)
    conditions.append(f"{column} IN ({placeholders})")
    params.extend(values)


def _build_filter_conditions(
    *,
    artist: str | Sequence[str] | None,
    album: str | Sequence[str] | None,
    genre: str | Sequence[str] | None,
    country: str | Sequence[str] | None,
    year: int | Sequence[int] | None,
    query: str | None,
    include_deleted: bool = False,
    block_explicit: bool = False,
    excluded_genre_terms: Sequence[str] = (),
) -> tuple[list[str], list[object]]:
    conditions: list[str] = [] if include_deleted else ["t.is_deleted = 0"]
    params: list[object] = []

    if block_explicit:
        conditions.append("t.explicit = 0")
    if excluded_genre_terms:
        normalized_col = _normalized_genre_sql("t.genre")
        for term in excluded_genre_terms:
            cleaned_term = " ".join(term.casefold().split())
            if cleaned_term:
                conditions.append(
                    f"(t.genre IS NULL OR instr({normalized_col}, ?) = 0)"
                )
                params.append(f" {cleaned_term} ")

    if query:
        exact_like = f"%{query.lower()}%"
        flex_like = f"%{_to_flexible_like(query)}%"
        if exact_like == flex_like:
            conditions.append("(lower(t.title) LIKE ? OR lower(t.artist) LIKE ?)")
            params.extend([exact_like, exact_like])
        else:
            conditions.append(
                "("
                "lower(t.title) LIKE ? OR lower(t.artist) LIKE ?"
                " OR t.artist LIKE ? OR t.title LIKE ?"
                ")"
            )
            params.extend([exact_like, exact_like, flex_like, flex_like])

    _append_like_clause(
        conditions, params, "t.artist", _normalize_string_sequence(artist)
    )
    _ = album
    _append_genre_clause(
        conditions, params, "t.genre", _normalize_string_sequence(genre)
    )
    _append_country_clause(conditions, params, _normalize_string_sequence(country))
    _append_in_clause(
        conditions, params, "t.release_year", _normalize_year_sequence(year)
    )

    return conditions, params


_TRACK_SORT_ORDERS: dict[str, str] = {
    "rating_desc": (
        "CASE WHEN r_agg.avg_rating IS NULL THEN 1 ELSE 0 END ASC, "
        "r_agg.avg_rating DESC, COALESCE(r_agg.review_count, 0) DESC, t.track_id ASC"
    ),
    "rating_asc": (
        "CASE WHEN r_agg.avg_rating IS NULL THEN 1 ELSE 0 END ASC, "
        "r_agg.avg_rating ASC, COALESCE(r_agg.review_count, 0) DESC, t.track_id ASC"
    ),
}


_ADMIN_TRACK_SORT_ORDERS: dict[str, str] = {
    "id_asc": "t.track_id ASC",
    "dislikes_desc": "dislikes_count DESC, t.track_id ASC",
    "likes_desc": "likes_count DESC, t.track_id ASC",
    "superlikes_desc": "superlikes_count DESC, t.track_id ASC",
    "recent": "t.created_at DESC, t.track_id DESC",
}


def _row_to_admin_catalog_track(row: sqlite3.Row) -> AdminCatalogTrackResult:
    return AdminCatalogTrackResult(
        track_id=int(row["track_id"]),
        title=row["title"],
        artist=row["artist"],
        duration_seconds=int(row["duration_seconds"]),
        genre=row["genre"],
        spotify_id=row["spotify_id"],
        album=None,
        country=row["country"],
        release_year=row["release_year"],
        cover_url=row["cover_url"],
        itunes_preview_url=row["itunes_preview_url"],
        explicit=bool(row["explicit"]),
        is_deleted=bool(row["is_deleted"]),
        likes_count=int(row["likes_count"]),
        dislikes_count=int(row["dislikes_count"]),
        superlikes_count=int(row["superlikes_count"]),
        average_rating=(
            float(row["avg_rating"]) if row["avg_rating"] is not None else None
        ),
        review_count=int(row["review_count"]),
    )


class SQLiteTrackRepository(TrackRepositoryPort):
    """SQLite adapter implementing TrackRepositoryPort."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.create_function("TRANSLATE", 3, _sqlite_translate)

    def find_by_id(self, track_id: int) -> Track | None:
        cursor = self.conn.execute(
            "SELECT * FROM tracks WHERE track_id = ?",
            (track_id,),
        )
        row = cursor.fetchone()
        return _row_to_track(row) if row else None

    def find_by_ids(self, track_ids: Sequence[TrackId | int]) -> dict[int, Track]:
        if not track_ids:
            return {}
        unique_ids = list(dict.fromkeys(int(t) for t in track_ids))
        placeholders = ",".join("?" for _ in unique_ids)
        cursor = self.conn.execute(
            f"SELECT * FROM tracks WHERE track_id IN ({placeholders})",  # noqa: S608
            tuple(unique_ids),
        )
        rows = cursor.fetchall()
        result: dict[int, Track] = {}
        for r in rows:
            track = _row_to_track(r)
            if track.track_id is not None:
                result[track.track_id] = track
        return result

    def _update_track_by_id(
        self, cursor: sqlite3.Cursor, track_id: int, track: Track
    ) -> int:
        row = cursor.execute(
            "SELECT track_id FROM tracks WHERE track_id = ?",
            (track_id,),
        ).fetchone()
        if not row:
            raise EntityNotFoundError(entity_name="Track", entity_id=track_id)
        cursor.execute(
            """
            UPDATE tracks
            SET spotify_id = ?,
                title = ?,
                artist = ?,
                duration_seconds = ?,
                genre = ?,
                country = ?,
                release_year = ?,
                cover_url = ?,
                itunes_preview_url = ?,
                explicit = ?,
                is_deleted = ?
            WHERE track_id = ?
            """,
            (
                track.spotify_id,
                track.title,
                track.artist,
                track.duration_seconds,
                track.genre or "",
                track.country,
                track.release_year,
                track.cover_url,
                track.itunes_preview_url,
                1 if track.explicit else 0,
                1 if track.is_deleted else 0,
                track_id,
            ),
        )
        return track_id

    def _update_track_by_spotify_id(
        self, cursor: sqlite3.Cursor, track: Track
    ) -> int | None:
        if not track.spotify_id:
            return None
        row = cursor.execute(
            "SELECT track_id, is_deleted FROM tracks WHERE spotify_id = ?",
            (track.spotify_id,),
        ).fetchone()
        if row is None:
            return None
        existing_id = int(row["track_id"])
        preserved_deleted = bool(row["is_deleted"]) or track.is_deleted
        track.is_deleted = preserved_deleted
        cursor.execute(
            """
            UPDATE tracks
            SET title = ?,
                artist = ?,
                duration_seconds = ?,
                genre = ?,
                country = ?,
                release_year = ?,
                cover_url = ?,
                itunes_preview_url = coalesce(?, itunes_preview_url),
                explicit = ?,
                is_deleted = ?
            WHERE track_id = ?
            """,
            (
                track.title,
                track.artist,
                track.duration_seconds,
                track.genre or "",
                track.country,
                track.release_year,
                track.cover_url,
                track.itunes_preview_url,
                1 if track.explicit else 0,
                1 if preserved_deleted else 0,
                existing_id,
            ),
        )
        return existing_id

    def _insert_track(self, cursor: sqlite3.Cursor, track: Track) -> int | None:
        created_at_str = (track.created_at or datetime.now(UTC)).isoformat()
        cursor.execute(
            """
            INSERT INTO tracks (
                spotify_id, title, artist, duration_seconds,
                genre, country, release_year, cover_url, itunes_preview_url,
                explicit, is_deleted, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                track.spotify_id,
                track.title,
                track.artist,
                track.duration_seconds,
                track.genre or "",
                track.country,
                track.release_year,
                track.cover_url,
                track.itunes_preview_url,
                1 if track.explicit else 0,
                1 if track.is_deleted else 0,
                created_at_str,
            ),
        )
        return cursor.lastrowid

    def save(self, track: Track) -> Track:
        target_id: int | None = None
        with transaction(self.conn) as cursor:
            if track.track_id is not None:
                target_id = self._update_track_by_id(cursor, track.track_id, track)
            else:
                target_id = self._update_track_by_spotify_id(cursor, track)
                if target_id is None:
                    target_id = self._insert_track(cursor, track)
        if target_id is not None:
            return self.find_by_id(target_id) or track
        return track

    @staticmethod
    def _append_unique_rows(
        rows: Sequence[sqlite3.Row],
        collected: list[sqlite3.Row],
        seen_ids: set[int],
        target: int,
    ) -> None:
        for row in rows:
            tid = int(row["track_id"])
            if tid not in seen_ids:
                seen_ids.add(tid)
                collected.append(row)
                if len(collected) >= target:
                    break

    def _resolve_genre_sets(
        self,
        *,
        excluded_genres: Sequence[str],
        excluded_genre_terms: Sequence[str],
        preferred_genres: Sequence[str],
        included_genres: Sequence[str] = (),
    ) -> tuple[list[str], list[str] | None, list[str] | None]:
        clean_excluded = [g.strip() for g in excluded_genres if g and g.strip()]
        clean_terms = [
            t.casefold().strip() for t in excluded_genre_terms if t and t.strip()
        ]
        clean_preferred = [g.strip() for g in preferred_genres if g and g.strip()]
        clean_included = [g.strip() for g in included_genres if g and g.strip()]
        if (
            not clean_excluded
            and not clean_terms
            and not clean_preferred
            and not clean_included
        ):
            return [], None, None

        distinct_genres = [
            str(r[0])
            for r in self.conn.execute("SELECT DISTINCT genre FROM tracks").fetchall()
            if r[0] is not None
        ]
        blocked_raw = [
            g
            for g in distinct_genres
            if any(genre_matches_preference(g, exc) for exc in clean_excluded)
            or (
                clean_terms
                and any(
                    f" {term} " in _normalize_genre_tokens(g) for term in clean_terms
                )
            )
        ]
        blocked_set = set(blocked_raw)
        allowed_genres = [g for g in distinct_genres if g not in blocked_set]
        included_raw = (
            [
                g
                for g in allowed_genres
                if any(genre_matches_preference(g, inc) for inc in clean_included)
            ]
            if clean_included
            else None
        )
        if not clean_preferred:
            return blocked_raw, None, included_raw
        candidate_genres = allowed_genres if included_raw is None else included_raw
        preferred_raw = [
            g
            for g in candidate_genres
            if any(genre_matches_preference(g, pref) for pref in clean_preferred)
        ]
        return blocked_raw, preferred_raw, included_raw

    def _fetch_random_rows(
        self,
        where_clause: str,
        base_params: list[object],
        *,
        target: int,
        seen_ids: set[int],
    ) -> list[sqlite3.Row]:
        if target <= 0:
            return []
        effective_where = where_clause
        effective_params = list(base_params)
        if seen_ids:
            placeholders = ",".join("?" for _ in seen_ids)
            effective_where = f"{where_clause} AND track_id NOT IN ({placeholders})"
            effective_params.extend(seen_ids)
        id_query = (
            f"SELECT track_id FROM tracks WHERE {effective_where} "  # noqa: S608
            "ORDER BY RANDOM() LIMIT ?"
        )
        picked_ids = [
            int(r[0])
            for r in self.conn.execute(id_query, (*effective_params, target)).fetchall()
            if int(r[0]) not in seen_ids
        ]
        if not picked_ids:
            return []
        id_placeholders = ",".join("?" for _ in picked_ids)
        rows = self.conn.execute(
            f"SELECT * FROM tracks WHERE track_id IN ({id_placeholders})",  # noqa: S608
            tuple(picked_ids),
        ).fetchall()
        rows_by_id = {int(r["track_id"]): r for r in rows}
        ordered_rows = [rows_by_id[tid] for tid in picked_ids if tid in rows_by_id]
        collected: list[sqlite3.Row] = []
        self._append_unique_rows(ordered_rows, collected, seen_ids, target)
        return collected

    def _fetch_random_probes(
        self,
        where_clause: str,
        base_params: list[object],
        *,
        target: int,
        seen_ids: set[int],
    ) -> list[sqlite3.Row]:
        if target <= 0:
            return []
        bounds = self.conn.execute(
            f"SELECT MIN(track_id), MAX(track_id) FROM tracks WHERE {where_clause}",  # noqa: S608
            tuple(base_params),
        ).fetchone()
        if bounds is None or bounds[0] is None or bounds[1] is None:
            return []
        scoped_min, scoped_max = int(bounds[0]), int(bounds[1])
        collected: list[sqlite3.Row] = []
        probes = min(target, 16)
        per_probe = max(1, (target + probes - 1) // probes)
        for _ in range(probes):
            if len(collected) >= target:
                break
            start_id = random.randint(scoped_min, scoped_max)  # noqa: S311
            query = (
                f"SELECT * FROM tracks WHERE track_id >= ? AND {where_clause} "  # noqa: S608
                "ORDER BY track_id ASC LIMIT ?"
            )
            rows = self.conn.execute(
                query, (start_id, *base_params, per_probe)
            ).fetchall()
            self._append_unique_rows(rows, collected, seen_ids, target)
            if len(rows) < per_probe and len(collected) < target:
                wrap_limit = per_probe - len(rows)
                wrap_query = (
                    f"SELECT * FROM tracks WHERE track_id < ? AND {where_clause} "  # noqa: S608
                    "ORDER BY track_id DESC LIMIT ?"
                )
                wrap_rows = self.conn.execute(
                    wrap_query, (start_id, *base_params, wrap_limit)
                ).fetchall()
                self._append_unique_rows(wrap_rows, collected, seen_ids, target)
        random.shuffle(collected)
        return collected

    def list_active(
        self,
        *,
        limit: int,
        excluded_genres: Sequence[str] = (),
        excluded_genre_terms: Sequence[str] = (),
        preferred_genres: Sequence[str] = (),
        block_explicit: bool = False,
        excluded_ids: Sequence[int] = (),
        artist: str | Sequence[str] | None = None,
        genre: str | Sequence[str] | None = None,
        country: str | Sequence[str] | None = None,
        year: int | Sequence[int] | None = None,
        max_duration_seconds: int | None = None,
    ) -> list[Track]:
        conditions = ["is_deleted = 0"]
        params: list[object] = []

        if block_explicit:
            conditions.append("explicit = 0")

        if excluded_ids:
            placeholders = ",".join("?" for _ in excluded_ids)
            conditions.append(f"track_id NOT IN ({placeholders})")
            params.extend(excluded_ids)

        blocked_raw, preferred_raw, included_raw = self._resolve_genre_sets(
            excluded_genres=excluded_genres,
            excluded_genre_terms=excluded_genre_terms,
            preferred_genres=preferred_genres,
            included_genres=_normalize_string_sequence(genre),
        )
        if included_raw is not None:
            if not included_raw:
                return []
            placeholders = ",".join("?" for _ in included_raw)
            conditions.append(f"genre IN ({placeholders})")
            params.extend(included_raw)
        elif blocked_raw:
            placeholders = ",".join("?" for _ in blocked_raw)
            conditions.append(f"(genre IS NULL OR genre NOT IN ({placeholders}))")
            params.extend(blocked_raw)

        _append_like_clause(
            conditions, params, "artist", _normalize_string_sequence(artist)
        )
        _append_country_clause(
            conditions,
            params,
            _normalize_string_sequence(country),
            column="country",
        )
        _append_in_clause(
            conditions, params, "release_year", _normalize_year_sequence(year)
        )
        if max_duration_seconds is not None:
            conditions.append("duration_seconds <= ?")
            params.append(max_duration_seconds)

        where_clause = " AND ".join(conditions)
        total_row = self.conn.execute("SELECT COUNT(*) FROM tracks").fetchone()
        if total_row is None or int(total_row[0]) == 0:
            return []
        total_tracks = int(total_row[0])

        if total_tracks <= limit * 2:
            query = f"SELECT * FROM tracks WHERE {where_clause} ORDER BY track_id ASC LIMIT ?"  # noqa: S608
            rows = self.conn.execute(query, (*params, limit)).fetchall()
            return [_row_to_track(r) for r in rows]

        seen_ids: set[int] = set()
        sampled_rows: list[sqlite3.Row] = []
        fetcher = (
            self._fetch_random_rows
            if total_tracks <= _RANDOM_ORDER_MAX_ROWS
            else self._fetch_random_probes
        )

        if preferred_raw and (
            included_raw is None or len(preferred_raw) < len(included_raw)
        ):
            placeholders = ",".join("?" for _ in preferred_raw)
            pref_where = f"{where_clause} AND genre IN ({placeholders})"
            pref_params: list[object] = [*params, *preferred_raw]
            sampled_rows.extend(
                fetcher(
                    pref_where,
                    pref_params,
                    target=max(1, limit // 2),
                    seen_ids=seen_ids,
                )
            )

        sampled_rows.extend(
            fetcher(
                where_clause,
                params,
                target=limit - len(sampled_rows),
                seen_ids=seen_ids,
            )
        )
        return [_row_to_track(r) for r in sampled_rows]

    def find_by_filters(
        self,
        *,
        artist: str | Sequence[str] | None = None,
        album: str | Sequence[str] | None = None,
        genre: str | Sequence[str] | None = None,
        country: str | Sequence[str] | None = None,
        year: int | Sequence[int] | None = None,
        query: str | None = None,
        min_rating: float | None = None,
        sort_by: str | None = None,
        include_deleted: bool = False,
        block_explicit: bool = False,
        excluded_genre_terms: Sequence[str] = (),
        limit: int = 50,
        offset: int = 0,
    ) -> list[Track]:
        conditions, params = _build_filter_conditions(
            artist=artist,
            album=album,
            genre=genre,
            country=country,
            year=year,
            query=query,
            include_deleted=include_deleted,
            block_explicit=block_explicit,
            excluded_genre_terms=excluded_genre_terms,
        )
        if min_rating is not None:
            conditions.append("r_agg.avg_rating >= ?")
            params.append(min_rating)
        where_clause = " AND ".join(conditions) if conditions else "1 = 1"
        order_by = _TRACK_SORT_ORDERS.get(sort_by or "", "t.track_id ASC")
        sql = (
            "SELECT t.*, r_agg.avg_rating AS avg_rating, "  # noqa: S608
            "COALESCE(r_agg.review_count, 0) AS review_count "
            "FROM tracks t "
            "LEFT JOIN ("
            "SELECT track_id, ROUND(AVG(rating), 2) AS avg_rating, "
            "COUNT(*) AS review_count "
            "FROM reviews WHERE is_deleted = 0 GROUP BY track_id"
            ") r_agg ON r_agg.track_id = t.track_id "
            f"WHERE {where_clause} ORDER BY {order_by} LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])
        cursor = self.conn.execute(sql, tuple(params))
        rows = cursor.fetchall()
        return [_row_to_track(r) for r in rows]

    def count_all(self) -> int:
        cursor = self.conn.execute("SELECT count(*) FROM tracks")
        row = cursor.fetchone()
        return int(row[0]) if row else 0

    def count_active(self) -> int:
        cursor = self.conn.execute("SELECT COUNT(*) FROM tracks WHERE is_deleted = 0")
        row = cursor.fetchone()
        return int(row[0]) if row else 0

    def find_by_spotify_id(self, spotify_id: str) -> Track | None:
        cursor = self.conn.execute(
            "SELECT * FROM tracks WHERE spotify_id = ?",
            (spotify_id,),
        )
        row = cursor.fetchone()
        return _row_to_track(row) if row else None

    def find_by_title_and_artist(self, title: str, artist: str) -> Track | None:
        cursor = self.conn.execute(
            "SELECT * FROM tracks WHERE lower(title) = ? AND lower(artist) = ? LIMIT 1",
            (title.strip().lower(), artist.strip().lower()),
        )
        row = cursor.fetchone()
        return _row_to_track(row) if row else None

    def list_blocked(self) -> list[Track]:
        cursor = self.conn.execute(
            "SELECT * FROM tracks WHERE is_deleted = 1 ORDER BY track_id ASC"
        )
        rows = cursor.fetchall()
        return [_row_to_track(r) for r in rows]

    def _query_admin_catalog(
        self,
        *,
        where_clause: str,
        params: list[object],
        order_by: str,
        limit: int | None,
        offset: int,
    ) -> list[AdminCatalogTrackResult]:
        limit_clause = "LIMIT ? OFFSET ?" if limit is not None else ""
        if limit is not None:
            params.extend([limit, offset])
        sql = (
            "SELECT t.*, "  # noqa: S608
            "COALESCE(i_agg.likes_count, 0) AS likes_count, "
            "COALESCE(i_agg.dislikes_count, 0) AS dislikes_count, "
            "COALESCE(i_agg.superlikes_count, 0) AS superlikes_count, "
            "r_agg.avg_rating AS avg_rating, "
            "COALESCE(r_agg.review_count, 0) AS review_count "
            "FROM tracks t "
            "LEFT JOIN ("
            "SELECT track_id, "
            "SUM(CASE WHEN action = 'like' THEN 1 ELSE 0 END) AS likes_count, "
            "SUM(CASE WHEN action = 'dislike' THEN 1 ELSE 0 END) AS dislikes_count, "
            "SUM(CASE WHEN action = 'superlike' THEN 1 ELSE 0 END) AS superlikes_count "
            "FROM interactions GROUP BY track_id"
            ") i_agg ON i_agg.track_id = t.track_id "
            "LEFT JOIN ("
            "SELECT track_id, ROUND(AVG(rating), 2) AS avg_rating, "
            "COUNT(*) AS review_count "
            "FROM reviews WHERE is_deleted = 0 GROUP BY track_id"
            ") r_agg ON r_agg.track_id = t.track_id "
            f"WHERE {where_clause} ORDER BY {order_by} {limit_clause}"
        )
        rows = self.conn.execute(sql, tuple(params)).fetchall()
        return [_row_to_admin_catalog_track(r) for r in rows]

    def list_blocked_with_metrics(self) -> list[AdminCatalogTrackResult]:
        return self._query_admin_catalog(
            where_clause="t.is_deleted = 1",
            params=[],
            order_by="t.track_id ASC",
            limit=None,
            offset=0,
        )

    def list_admin_catalog(
        self,
        *,
        query: str | None = None,
        include_deleted: bool = False,
        min_dislikes: int | None = None,
        sort_by: str = "id_asc",
        limit: int = 100,
        offset: int = 0,
    ) -> list[AdminCatalogTrackResult]:
        conditions: list[str] = []
        params: list[object] = []
        if not include_deleted:
            conditions.append("t.is_deleted = 0")
        if query and query.strip():
            like = f"%{query.strip().lower()}%"
            conditions.append(
                "(lower(t.title) LIKE ? OR lower(t.artist) LIKE ? OR lower(t.genre) LIKE ?)"
            )
            params.extend([like, like, like])
        if min_dislikes is not None:
            conditions.append("COALESCE(i_agg.dislikes_count, 0) >= ?")
            params.append(min_dislikes)
        where_clause = " AND ".join(conditions) if conditions else "1 = 1"
        order_by = _ADMIN_TRACK_SORT_ORDERS.get(
            sort_by, _ADMIN_TRACK_SORT_ORDERS["id_asc"]
        )
        return self._query_admin_catalog(
            where_clause=where_clause,
            params=params,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )

    @staticmethod
    def _track_insert_tuple(t: Track, now_iso: str) -> tuple[object, ...]:
        return (
            t.spotify_id,
            t.title,
            t.artist,
            t.duration_seconds,
            t.genre,
            t.country,
            t.release_year,
            t.cover_url,
            t.itunes_preview_url,
            int(t.explicit),
            int(t.is_deleted),
            t.created_at.isoformat() if t.created_at else now_iso,
        )

    def _insert_track_rows(self, rows: list[tuple[object, ...]]) -> None:
        if not rows:
            return
        self.conn.executemany(
            """
            INSERT INTO tracks (
                spotify_id, title, artist, duration_seconds, genre,
                country, release_year, cover_url, itunes_preview_url,
                explicit, is_deleted, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    def bulk_upsert_tracks(self, tracks: Sequence[Track]) -> tuple[int, int]:
        """Inserts a batch of tracks in a single transaction using a temp staging table."""
        if not tracks:
            return 0, 0

        now_iso = datetime.now(UTC).isoformat()
        rows = [self._track_insert_tuple(t, now_iso) for t in tracks]
        with transaction(self.conn) as cursor:
            cursor.execute(
                """
                CREATE TEMP TABLE IF NOT EXISTS _stage_tracks (
                    spotify_id TEXT,
                    title TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    duration_seconds INTEGER NOT NULL,
                    genre TEXT NOT NULL,
                    country TEXT,
                    release_year INTEGER,
                    cover_url TEXT,
                    itunes_preview_url TEXT,
                    explicit INTEGER NOT NULL,
                    is_deleted INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute("DELETE FROM _stage_tracks")
            cursor.executemany(
                """
                INSERT INTO _stage_tracks (
                    spotify_id, title, artist, duration_seconds, genre,
                    country, release_year, cover_url, itunes_preview_url,
                    explicit, is_deleted, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            cursor.execute(
                """
                INSERT INTO tracks (
                    spotify_id, title, artist, duration_seconds, genre,
                    country, release_year, cover_url, itunes_preview_url,
                    explicit, is_deleted, created_at
                )
                SELECT
                    s.spotify_id, s.title, s.artist, s.duration_seconds, s.genre,
                    s.country, s.release_year, s.cover_url, s.itunes_preview_url,
                    s.explicit, s.is_deleted, s.created_at
                FROM _stage_tracks s
                WHERE NOT (
                    s.spotify_id IS NOT NULL
                    AND EXISTS (
                        SELECT 1 FROM tracks t WHERE t.spotify_id = s.spotify_id
                    )
                )
                AND NOT EXISTS (
                    SELECT 1 FROM tracks t
                    WHERE lower(t.title) = lower(s.title)
                      AND lower(t.artist) = lower(s.artist)
                )
                """
            )
            inserted = max(cursor.rowcount, 0)
            cursor.execute("DELETE FROM _stage_tracks")
        return inserted, 0


__all__ = ["SQLiteTrackRepository"]
