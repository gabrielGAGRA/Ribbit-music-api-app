"""SQLite implementation of the playlist persistence port."""

from datetime import UTC, datetime
from typing import Any
lazy import sqlite3

from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.playlist import Playlist
from app.infrastructure.repositories.connection import transaction
from app.infrastructure.repositories.track_repository import _row_to_track
lazy from app.domain.models.track import Track


def _row_to_playlist(row: sqlite3.Row, tracks: list[Track]) -> Playlist:
    created_at = (
        datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
    )
    keys = row.keys()
    max_duration = (
        row["max_duration_seconds"] if "max_duration_seconds" in keys else None
    )
    deck_filters = row["deck_filters"] if "deck_filters" in keys else None
    source_playlist_id = (
        row["source_playlist_id"] if "source_playlist_id" in keys else None
    )
    return Playlist(
        playlist_id=row["playlist_id"],
        user_id=row["user_id"],
        name=row["name"],
        description=row["description"],
        spotify_playlist_id=row["spotify_playlist_id"],
        cover_image_url=(row["cover_image_url"] if "cover_image_url" in keys else None),
        is_exported=bool(row["is_exported"]),
        created_at=created_at,
        max_duration_seconds=max_duration,
        deck_filters=deck_filters,
        source_playlist_id=source_playlist_id,
        initial_tracks=tracks,
    )


class SQLitePlaylistRepository(PlaylistRepositoryPort):
    """SQLite adapter implementing PlaylistRepositoryPort."""

    def __init__(
        self, conn: sqlite3.Connection, sync_service: Any | None = None
    ) -> None:
        self.conn = conn
        self._sync = sync_service

    def _pull_deltas(self) -> None:
        if self._sync is not None:
            self._sync.pull_deltas()

    def _push_playlist(self, playlist_id: int) -> None:
        if self._sync is not None:
            self._sync.push_playlist_by_id(playlist_id)

    def _get_tracks_for_playlist(self, playlist_id: int) -> list[Track]:
        cursor = self.conn.execute(
            """
            SELECT t.* FROM tracks t
            JOIN playlist_tracks pt ON t.track_id = pt.track_id
            WHERE pt.playlist_id = ? AND t.is_deleted = 0
            ORDER BY pt.playlist_track_id ASC
            """,
            (playlist_id,),
        )
        rows = cursor.fetchall()
        return [_row_to_track(r) for r in rows]

    def _find_by_id_local(self, playlist_id: int) -> Playlist | None:
        cursor = self.conn.execute(
            "SELECT * FROM playlists WHERE playlist_id = ?",
            (playlist_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        tracks = self._get_tracks_for_playlist(playlist_id)
        return _row_to_playlist(row, tracks)

    def find_by_id(self, playlist_id: int) -> Playlist | None:
        self._pull_deltas()
        return self._find_by_id_local(playlist_id)

    def list_by_user(self, user_id: int) -> list[Playlist]:
        self._pull_deltas()
        cursor = self.conn.execute(
            "SELECT * FROM playlists WHERE user_id = ? ORDER BY playlist_id ASC",
            (user_id,),
        )
        rows = cursor.fetchall()
        playlists: list[Playlist] = []
        for r in rows:
            tracks = self._get_tracks_for_playlist(r["playlist_id"])
            playlists.append(_row_to_playlist(r, tracks))
        return playlists

    def _replace_tracks_in_tx(
        self,
        cursor: sqlite3.Cursor,
        playlist_id: int,
        tracks: tuple[Track, ...],
        now_str: str,
    ) -> list[int]:
        old_track_ids = [
            int(r["track_id"])
            for r in cursor.execute(
                "SELECT track_id FROM playlist_tracks WHERE playlist_id = ?",
                (playlist_id,),
            ).fetchall()
        ]
        new_track_ids = {t.track_id for t in tracks if t.track_id is not None}
        removed_track_ids = [tid for tid in old_track_ids if tid not in new_track_ids]
        cursor.execute(
            "DELETE FROM playlist_tracks WHERE playlist_id = ?",
            (playlist_id,),
        )
        for track in tracks:
            if track.track_id is not None:
                cursor.execute(
                    """
                    INSERT INTO playlist_tracks (playlist_id, track_id, added_at)
                    VALUES (?, ?, ?)
                    """,
                    (playlist_id, track.track_id, now_str),
                )
        return removed_track_ids

    def delete(self, playlist_id: int) -> bool:
        with transaction(self.conn) as cursor:
            meta = cursor.execute(
                """
                SELECT u.email AS user_email, p.created_at AS created_at
                FROM playlists p
                LEFT JOIN users u ON u.user_id = p.user_id
                WHERE p.playlist_id = ?
                """,
                (playlist_id,),
            ).fetchone()
            user_email = (
                str(meta["user_email"]) if meta and meta["user_email"] else None
            )
            created_at = (
                str(meta["created_at"]) if meta and meta["created_at"] else None
            )
            cursor.execute(
                "DELETE FROM playlists WHERE playlist_id = ?",
                (playlist_id,),
            )
            deleted = cursor.rowcount > 0
        if deleted and user_email and created_at and self._sync is not None:
            self._sync.push_playlist_deleted(user_email, created_at)
        return deleted

    def remove_track(self, playlist_id: int, track_id: int) -> bool:
        with transaction(self.conn) as cursor:
            cursor.execute(
                "DELETE FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
                (playlist_id, track_id),
            )
            removed = cursor.rowcount > 0
        if removed and self._sync is not None:
            self._sync.push_playlist_track_removed(playlist_id, track_id)
        return removed

    def save(self, playlist: Playlist) -> Playlist:
        now_str = datetime.now(UTC).isoformat()
        if playlist.playlist_id is not None:
            with transaction(self.conn) as cursor:
                cursor.execute(
                    "SELECT playlist_id FROM playlists WHERE playlist_id = ?",
                    (playlist.playlist_id,),
                )
                if not cursor.fetchone():
                    raise EntityNotFoundError(
                        entity_name="Playlist", entity_id=playlist.playlist_id
                    )
                cursor.execute(
                    """
                    UPDATE playlists
                    SET name = ?,
                        description = ?,
                        spotify_playlist_id = ?,
                        cover_image_url = ?,
                        is_exported = ?,
                        max_duration_seconds = ?,
                        deck_filters = ?,
                        source_playlist_id = ?
                    WHERE playlist_id = ?
                    """,
                    (
                        playlist.name,
                        playlist.description,
                        playlist.spotify_playlist_id,
                        playlist.cover_image_url,
                        1 if playlist.is_exported else 0,
                        playlist.max_duration_seconds,
                        playlist.deck_filters,
                        playlist.source_playlist_id,
                        playlist.playlist_id,
                    ),
                )
                removed_track_ids = self._replace_tracks_in_tx(
                    cursor, playlist.playlist_id, playlist.tracks, now_str
                )
            self._push_playlist(playlist.playlist_id)
            if self._sync is not None:
                for tid in removed_track_ids:
                    self._sync.push_playlist_track_removed(playlist.playlist_id, tid)
            return self._find_by_id_local(playlist.playlist_id) or playlist

        created_at_str = (playlist.created_at or datetime.now(UTC)).isoformat()
        with transaction(self.conn) as cursor:
            cursor.execute(
                """
                INSERT INTO playlists (
                    user_id, name, description, spotify_playlist_id, is_exported,
                    created_at, max_duration_seconds, deck_filters, cover_image_url,
                    source_playlist_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    playlist.user_id,
                    playlist.name,
                    playlist.description,
                    playlist.spotify_playlist_id,
                    1 if playlist.is_exported else 0,
                    created_at_str,
                    playlist.max_duration_seconds,
                    playlist.deck_filters,
                    playlist.cover_image_url,
                    playlist.source_playlist_id,
                ),
            )
            new_id = cursor.lastrowid
            if new_id is not None:
                self._replace_tracks_in_tx(cursor, new_id, playlist.tracks, now_str)
        if new_id is not None:
            self._push_playlist(new_id)
            return self._find_by_id_local(new_id) or playlist
        return playlist

    def save_cover_image(
        self,
        playlist_id: int,
        content_type: str,
        image_data: bytes,
        cover_image_url: str,
    ) -> bool:
        with transaction(self.conn) as cursor:
            exists = cursor.execute(
                "SELECT 1 FROM playlists WHERE playlist_id = ?",
                (playlist_id,),
            ).fetchone()
            if exists is None:
                return False

            updated_at = datetime.now(UTC).isoformat()
            cursor.execute(
                """
                INSERT INTO playlist_images (playlist_id, content_type, image_data, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(playlist_id) DO UPDATE SET
                    content_type = excluded.content_type,
                    image_data = excluded.image_data,
                    updated_at = excluded.updated_at
                """,
                (playlist_id, content_type, image_data, updated_at),
            )
            cursor.execute(
                "UPDATE playlists SET cover_image_url = ? WHERE playlist_id = ?",
                (cover_image_url, playlist_id),
            )
        if self._sync is not None:
            self._sync.push_playlist_image(playlist_id)
            self._sync.push_playlist_by_id(playlist_id)
        return True

    def get_cover_image(self, playlist_id: int) -> tuple[str, bytes] | None:
        self._pull_deltas()
        row = self.conn.execute(
            """
            SELECT content_type, image_data
            FROM playlist_images
            WHERE playlist_id = ?
            """,
            (playlist_id,),
        ).fetchone()
        if row is None:
            return None
        return row["content_type"], bytes(row["image_data"])


__all__ = ["SQLitePlaylistRepository"]
