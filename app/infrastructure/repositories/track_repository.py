"""SQLite implementation of the track persistence port."""

import random
import re
from datetime import UTC, datetime
lazy import sqlite3
lazy from collections.abc import Sequence

from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.track import Track, TrackId
from app.domain.services.genre_names import expand_genre_aliases
from app.infrastructure.repositories.connection import transaction


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
    return Track(
        track_id=row["track_id"],
        title=row["title"],
        artist=row["artist"],
        duration_seconds=row["duration_seconds"],
        genre=row["genre"],
        spotify_id=row["spotify_id"],
        album=row["album"],
        country=row["country"],
        release_year=row["release_year"],
        cover_url=row["cover_url"],
        itunes_preview_url=row["itunes_preview_url"],
        explicit=bool(row["explicit"]),
        is_deleted=bool(row["is_deleted"]),
        created_at=created_at,
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
) -> None:
    if not values:
        return
    from app.domain.services.country_names import expand_country_terms  # noqa: PLC0415

    exact_codes, name_terms = expand_country_terms(values)
    clauses: list[str] = []
    if exact_codes:
        placeholders = ",".join("?" for _ in exact_codes)
        clauses.append(f"lower(country) IN ({placeholders})")
        params.extend(exact_codes)
    for v in name_terms:
        exact = f"%{v.lower()}%"
        flex = f"%{_to_flexible_like(v)}%"
        if exact == flex:
            clauses.append("lower(country) LIKE ?")
            params.append(exact)
        else:
            clauses.append("(lower(country) LIKE ? OR country LIKE ?)")
            params.extend([exact, flex])
    if clauses:
        conditions.append(f"({' OR '.join(clauses)})")


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
) -> tuple[list[str], list[object]]:
    conditions: list[str] = ["is_deleted = 0"]
    params: list[object] = []

    if query:
        exact_like = f"%{query.lower()}%"
        flex_like = f"%{_to_flexible_like(query)}%"
        if exact_like == flex_like:
            conditions.append(
                "(lower(title) LIKE ? OR lower(artist) LIKE ? OR lower(album) LIKE ?)"
            )
            params.extend([exact_like, exact_like, exact_like])
        else:
            conditions.append(
                "("
                "lower(title) LIKE ? OR lower(artist) LIKE ? OR lower(album) LIKE ?"
                " OR artist LIKE ? OR title LIKE ?"
                ")"
            )
            params.extend([exact_like, exact_like, exact_like, flex_like, flex_like])

    _append_like_clause(
        conditions, params, "artist", _normalize_string_sequence(artist)
    )
    _append_like_clause(conditions, params, "album", _normalize_string_sequence(album))
    expanded_genres = list(
        dict.fromkeys(
            alias
            for g in _normalize_string_sequence(genre)
            for alias in expand_genre_aliases(g)
        )
    )
    _append_like_clause(conditions, params, "genre", expanded_genres)
    _append_country_clause(conditions, params, _normalize_string_sequence(country))
    _append_in_clause(
        conditions, params, "release_year", _normalize_year_sequence(year)
    )

    return conditions, params


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
                album = ?,
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
                track.album,
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
            "SELECT track_id FROM tracks WHERE spotify_id = ?",
            (track.spotify_id,),
        ).fetchone()
        if row is None:
            return None
        existing_id = int(row["track_id"])
        cursor.execute(
            """
            UPDATE tracks
            SET title = ?,
                artist = ?,
                album = ?,
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
                track.album,
                track.duration_seconds,
                track.genre or "",
                track.country,
                track.release_year,
                track.cover_url,
                track.itunes_preview_url,
                1 if track.explicit else 0,
                1 if track.is_deleted else 0,
                existing_id,
            ),
        )
        return existing_id

    def _insert_track(self, cursor: sqlite3.Cursor, track: Track) -> int | None:
        created_at_str = (track.created_at or datetime.now(UTC)).isoformat()
        cursor.execute(
            """
            INSERT INTO tracks (
                spotify_id, title, artist, album, duration_seconds,
                genre, country, release_year, cover_url, itunes_preview_url,
                explicit, is_deleted, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                track.spotify_id,
                track.title,
                track.artist,
                track.album,
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

    def _fetch_random_probes(
        self,
        where_clause: str,
        base_params: list[object],
        *,
        min_id: int,
        max_id: int,
        target: int,
        seen_ids: set[int],
    ) -> list[sqlite3.Row]:
        if target <= 0:
            return []
        collected: list[sqlite3.Row] = []
        probes = min(2, max(1, target))
        per_probe = max(1, (target + probes - 1) // probes)
        for _ in range(probes):
            if len(collected) >= target:
                break
            start_id = random.randint(min_id, max_id)  # noqa: S311
            query = (
                f"SELECT * FROM tracks WHERE track_id >= ? AND {where_clause} "  # noqa: S608
                "ORDER BY track_id ASC LIMIT ?"
            )
            rows = self.conn.execute(
                query, (start_id, *base_params, per_probe)
            ).fetchall()
            self._append_unique_rows(rows, collected, seen_ids, target)
        if len(collected) < target:
            remaining = target - len(collected)
            fallback_q = (
                f"SELECT * FROM tracks WHERE {where_clause} "  # noqa: S608
                "ORDER BY track_id ASC LIMIT ?"
            )
            rows = self.conn.execute(
                fallback_q, (*base_params, remaining + len(seen_ids))
            ).fetchall()
            self._append_unique_rows(rows, collected, seen_ids, target)
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
    ) -> list[Track]:
        conditions = ["is_deleted = 0"]
        params: list[object] = []

        if block_explicit:
            conditions.append("explicit = 0")

        if excluded_ids:
            placeholders = ",".join("?" for _ in excluded_ids)
            conditions.append(f"track_id NOT IN ({placeholders})")
            params.extend(excluded_ids)

        normalized_genre = (
            "' ' || lower(TRANSLATE(genre, '-/&,.;:()[]!', '            ')) || ' '"
        )
        blocked_terms = list(
            dict.fromkeys(
                [
                    *(
                        alias
                        for g in excluded_genres
                        if g.strip()
                        for alias in expand_genre_aliases(g)
                    ),
                    *(t.casefold().strip() for t in excluded_genre_terms if t.strip()),
                ]
            )
        )
        for term in blocked_terms:
            conditions.append(f"instr({normalized_genre}, ?) = 0")
            params.append(f" {term} ")

        where_clause = " AND ".join(conditions)
        min_row = self.conn.execute("SELECT MIN(track_id) FROM tracks").fetchone()
        max_row = self.conn.execute("SELECT MAX(track_id) FROM tracks").fetchone()
        if (
            min_row is None
            or max_row is None
            or min_row[0] is None
            or max_row[0] is None
        ):
            return []
        min_id, max_id = int(min_row[0]), int(max_row[0])

        if (max_id - min_id) <= limit * 2:
            query = f"SELECT * FROM tracks WHERE {where_clause} ORDER BY track_id ASC LIMIT ?"  # noqa: S608
            rows = self.conn.execute(query, (*params, limit)).fetchall()
            return [_row_to_track(r) for r in rows]

        seen_ids: set[int] = set()
        sampled_rows: list[sqlite3.Row] = []

        pref_aliases = list(
            dict.fromkeys(
                alias
                for g in preferred_genres
                if g.strip()
                for alias in expand_genre_aliases(g)
            )
        )
        if pref_aliases:
            pref_clauses = ["lower(genre) LIKE ?" for _ in pref_aliases]
            pref_where = f"{where_clause} AND ({' OR '.join(pref_clauses)})"
            pref_params: list[object] = [*params, *(f"%{a}%" for a in pref_aliases)]
            sampled_rows.extend(
                self._fetch_random_probes(
                    pref_where,
                    pref_params,
                    min_id=min_id,
                    max_id=max_id,
                    target=max(1, limit // 2),
                    seen_ids=seen_ids,
                )
            )

        sampled_rows.extend(
            self._fetch_random_probes(
                where_clause,
                params,
                min_id=min_id,
                max_id=max_id,
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
        )
        where_clause = " AND ".join(conditions)
        sql = f"SELECT * FROM tracks WHERE {where_clause} ORDER BY track_id ASC LIMIT ? OFFSET ?"  # noqa: S608
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

    @staticmethod
    def _track_insert_tuple(t: Track, now_iso: str) -> tuple[object, ...]:
        return (
            t.spotify_id,
            t.title,
            t.artist,
            t.album,
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
                spotify_id, title, artist, album, duration_seconds, genre,
                country, release_year, cover_url, itunes_preview_url,
                explicit, is_deleted, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    album TEXT,
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
                    spotify_id, title, artist, album, duration_seconds, genre,
                    country, release_year, cover_url, itunes_preview_url,
                    explicit, is_deleted, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            cursor.execute(
                """
                INSERT INTO tracks (
                    spotify_id, title, artist, album, duration_seconds, genre,
                    country, release_year, cover_url, itunes_preview_url,
                    explicit, is_deleted, created_at
                )
                SELECT
                    s.spotify_id, s.title, s.artist, s.album, s.duration_seconds, s.genre,
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
