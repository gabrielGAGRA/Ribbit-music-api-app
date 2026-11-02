"""SQLite implementation of the track persistence port."""

from datetime import UTC, datetime
lazy import sqlite3
lazy from collections.abc import Sequence

from app.application.ports.repositories.track_repository import TrackRepositoryPort
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.track import Track, TrackId


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


class SQLiteTrackRepository(TrackRepositoryPort):
    """SQLite adapter implementing TrackRepositoryPort."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

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

    def save(self, track: Track) -> Track:
        if track.track_id is not None:
            cursor = self.conn.execute(
                "SELECT track_id FROM tracks WHERE track_id = ?",
                (track.track_id,),
            )
            if cursor.fetchone():
                self.conn.execute(
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
                        track.track_id,
                    ),
                )
                self.conn.commit()
                return self.find_by_id(track.track_id) or track
            raise EntityNotFoundError(entity_name="Track", entity_id=track.track_id)

        if track.track_id is None and track.spotify_id:
            existing = self.find_by_spotify_id(track.spotify_id)
            if existing is not None and existing.track_id is not None:
                self.conn.execute(
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
                        existing.track_id,
                    ),
                )
                self.conn.commit()
                return self.find_by_id(existing.track_id) or existing

        created_at_str = (track.created_at or datetime.now(UTC)).isoformat()
        cursor = self.conn.execute(
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
        self.conn.commit()
        new_id = cursor.lastrowid
        if new_id is not None:
            return self.find_by_id(new_id) or track
        return track

    def list_active(
        self,
        *,
        limit: int,
        excluded_genres: Sequence[str] = (),
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

        clean_genres = [g.lower().strip() for g in excluded_genres if g.strip()]
        if clean_genres:
            placeholders = ",".join("?" for _ in clean_genres)
            conditions.append(f"lower(genre) NOT IN ({placeholders})")
            params.extend(clean_genres)

        where_clause = " AND ".join(conditions)
        query = (
            f"SELECT * FROM tracks WHERE {where_clause} ORDER BY track_id ASC LIMIT ?"  # noqa: S608
        )
        params.append(limit)

        cursor = self.conn.execute(query, tuple(params))
        rows = cursor.fetchall()
        return [_row_to_track(r) for r in rows]

    def find_by_filters(
        self,
        *,
        artist: str | None = None,
        album: str | None = None,
        genre: str | None = None,
        year: int | None = None,
        query: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Track]:
        conditions = ["is_deleted = 0"]
        params: list[object] = []

        if query:
            like_term = f"%{query.lower()}%"
            conditions.append(
                "(lower(title) LIKE ? OR lower(artist) LIKE ? OR lower(album) LIKE ?)"
            )
            params.extend([like_term, like_term, like_term])
        if artist:
            conditions.append("lower(artist) LIKE ?")
            params.append(f"%{artist.lower()}%")
        if album:
            conditions.append("lower(album) LIKE ?")
            params.append(f"%{album.lower()}%")
        if genre:
            conditions.append("lower(genre) = ?")
            params.append(genre.lower())
        if year is not None:
            conditions.append("release_year = ?")
            params.append(year)

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


__all__ = ["SQLiteTrackRepository"]
