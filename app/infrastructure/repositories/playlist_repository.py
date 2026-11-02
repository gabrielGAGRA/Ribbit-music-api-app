"""SQLite implementation of the playlist persistence port."""

from datetime import UTC, datetime
lazy import sqlite3

from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.playlist import Playlist
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
    return Playlist(
        playlist_id=row["playlist_id"],
        user_id=row["user_id"],
        name=row["name"],
        description=row["description"],
        spotify_playlist_id=row["spotify_playlist_id"],
        is_exported=bool(row["is_exported"]),
        created_at=created_at,
        max_duration_seconds=max_duration,
        deck_filters=deck_filters,
        initial_tracks=tracks,
    )


class SQLitePlaylistRepository(PlaylistRepositoryPort):
    """SQLite adapter implementing PlaylistRepositoryPort."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

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

    def find_by_id(self, playlist_id: int) -> Playlist | None:
        cursor = self.conn.execute(
            "SELECT * FROM playlists WHERE playlist_id = ?",
            (playlist_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        tracks = self._get_tracks_for_playlist(playlist_id)
        return _row_to_playlist(row, tracks)

    def list_by_user(self, user_id: int) -> list[Playlist]:
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

    def delete(self, playlist_id: int) -> bool:
        cursor = self.conn.execute(
            "DELETE FROM playlists WHERE playlist_id = ?",
            (playlist_id,),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def remove_track(self, playlist_id: int, track_id: int) -> bool:
        cursor = self.conn.execute(
            "DELETE FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
            (playlist_id, track_id),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def save(self, playlist: Playlist) -> Playlist:
        now_str = datetime.now(UTC).isoformat()
        if playlist.playlist_id is not None:
            cursor = self.conn.execute(
                "SELECT playlist_id FROM playlists WHERE playlist_id = ?",
                (playlist.playlist_id,),
            )
            if cursor.fetchone():
                self.conn.execute(
                    """
                    UPDATE playlists
                    SET name = ?,
                        description = ?,
                        spotify_playlist_id = ?,
                        is_exported = ?,
                        max_duration_seconds = ?,
                        deck_filters = ?
                    WHERE playlist_id = ?
                    """,
                    (
                        playlist.name,
                        playlist.description,
                        playlist.spotify_playlist_id,
                        1 if playlist.is_exported else 0,
                        playlist.max_duration_seconds,
                        playlist.deck_filters,
                        playlist.playlist_id,
                    ),
                )
                self.conn.execute(
                    "DELETE FROM playlist_tracks WHERE playlist_id = ?",
                    (playlist.playlist_id,),
                )
                for track in playlist.tracks:
                    if track.track_id is not None:
                        self.conn.execute(
                            """
                            INSERT INTO playlist_tracks (playlist_id, track_id, added_at)
                            VALUES (?, ?, ?)
                            """,
                            (playlist.playlist_id, track.track_id, now_str),
                        )
                self.conn.commit()
                return self.find_by_id(playlist.playlist_id) or playlist
            raise EntityNotFoundError(
                entity_name="Playlist", entity_id=playlist.playlist_id
            )

        created_at_str = (playlist.created_at or datetime.now(UTC)).isoformat()
        cursor = self.conn.execute(
            """
            INSERT INTO playlists (
                user_id, name, description, spotify_playlist_id, is_exported,
                created_at, max_duration_seconds, deck_filters
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )
        new_id = cursor.lastrowid
        if new_id is not None:
            for track in playlist.tracks:
                if track.track_id is not None:
                    self.conn.execute(
                        """
                        INSERT INTO playlist_tracks (playlist_id, track_id, added_at)
                        VALUES (?, ?, ?)
                        """,
                        (new_id, track.track_id, now_str),
                    )
            self.conn.commit()
            return self.find_by_id(new_id) or playlist
        self.conn.commit()
        return playlist


__all__ = ["SQLitePlaylistRepository"]
