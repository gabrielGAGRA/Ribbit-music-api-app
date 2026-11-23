"""SQLite implementation of the review and comment persistence port."""

from datetime import UTC, datetime, timedelta
lazy import sqlite3

from app.application.ports.repositories.review_repository import ReviewRepositoryPort
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.review import ReviewComment
from app.infrastructure.repositories.connection import transaction

_REVIEW_SORT_ORDERS: dict[str, str] = {
    "recent": "r.created_at DESC, r.review_id DESC",
    "oldest": "r.created_at ASC, r.review_id ASC",
    "likes": "r.likes_count DESC, r.created_at DESC",
    "rating_desc": "r.rating DESC, r.likes_count DESC, r.created_at DESC",
    "rating_asc": "r.rating ASC, r.likes_count DESC, r.created_at DESC",
}


def _row_to_review(row: sqlite3.Row) -> ReviewComment:
    created_at = (
        datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
    )
    keys = row.keys() if hasattr(row, "keys") else ()
    author_name = row["author_name"] if "author_name" in keys else None
    track_title = row["track_title"] if "track_title" in keys else None
    track_artist = row["track_artist"] if "track_artist" in keys else None
    track_image = row["track_image"] if "track_image" in keys else None
    return ReviewComment(
        review_id=row["review_id"],
        user_id=row["user_id"],
        track_id=row["track_id"],
        initial_rating=int(row["rating"]),
        text=row["text"],
        initial_likes_count=int(row["likes_count"]),
        is_deleted=bool(row["is_deleted"]),
        created_at=created_at,
        author_name=author_name,
        track_title=track_title,
        track_artist=track_artist,
        track_image=track_image,
    )


class SQLiteReviewRepository(ReviewRepositoryPort):
    """SQLite adapter implementing ReviewRepositoryPort."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def _find_by_id_local(self, review_id: int) -> ReviewComment | None:
        cursor = self.conn.execute(
            """
            SELECT
                r.*,
                u.display_name AS author_name,
                t.title AS track_title,
                t.artist AS track_artist,
                t.cover_url AS track_image
            FROM reviews r
            LEFT JOIN users u ON u.user_id = r.user_id
            LEFT JOIN tracks t ON t.track_id = r.track_id
            WHERE r.review_id = ?
            """,
            (review_id,),
        )
        row = cursor.fetchone()
        return _row_to_review(row) if row else None

    def find_by_id(self, review_id: int) -> ReviewComment | None:
        return self._find_by_id_local(review_id)

    def save(self, review: ReviewComment) -> ReviewComment:
        if review.review_id is not None:
            with transaction(self.conn) as cursor:
                cursor.execute(
                    "SELECT review_id FROM reviews WHERE review_id = ?",
                    (review.review_id,),
                )
                if not cursor.fetchone():
                    raise EntityNotFoundError(
                        entity_name="ReviewComment", entity_id=review.review_id
                    )
                cursor.execute(
                    """
                    UPDATE reviews
                    SET rating = ?,
                        text = ?,
                        likes_count = ?,
                        is_deleted = ?
                    WHERE review_id = ?
                    """,
                    (
                        review.rating,
                        review.text,
                        review.likes_count,
                        1 if review.is_deleted else 0,
                        review.review_id,
                    ),
                )
            return self._find_by_id_local(review.review_id) or review

        created_at_str = (review.created_at or datetime.now(UTC)).isoformat()
        with transaction(self.conn) as cursor:
            cursor.execute(
                """
                INSERT INTO reviews (
                    user_id, track_id, rating, text, likes_count, is_deleted, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review.user_id,
                    review.track_id,
                    review.rating,
                    review.text,
                    review.likes_count,
                    1 if review.is_deleted else 0,
                    created_at_str,
                ),
            )
            new_id = cursor.lastrowid
        if new_id is not None:
            return self._find_by_id_local(new_id) or review
        return review

    def list_by_track(
        self, track_id: int, limit: int, sort_by: str = "recent"
    ) -> list[ReviewComment]:
        order_by = _REVIEW_SORT_ORDERS.get(sort_by, _REVIEW_SORT_ORDERS["recent"])
        cursor = self.conn.execute(
            f"""
            SELECT
                r.*,
                u.display_name AS author_name,
                t.title AS track_title,
                t.artist AS track_artist,
                t.cover_url AS track_image
            FROM reviews r
            LEFT JOIN users u ON u.user_id = r.user_id
            LEFT JOIN tracks t ON t.track_id = r.track_id
            WHERE r.track_id = ?
              AND r.is_deleted = 0
              AND COALESCE(t.is_deleted, 0) = 0
            ORDER BY {order_by}
            LIMIT ?
            """,  # noqa: S608
            (track_id, limit),
        )
        rows = cursor.fetchall()
        return [_row_to_review(r) for r in rows]

    def list_top_recent(
        self, days: int | None = None, limit: int = 10, sort_by: str = "likes"
    ) -> list[ReviewComment]:
        order_by = _REVIEW_SORT_ORDERS.get(sort_by, _REVIEW_SORT_ORDERS["likes"])
        conditions = ["r.is_deleted = 0", "COALESCE(t.is_deleted, 0) = 0"]
        params: list[object] = []
        if days is not None:
            min_date_str = (datetime.now(UTC) - timedelta(days=days)).isoformat()
            conditions.append("r.created_at >= ?")
            params.append(min_date_str)
        params.append(limit)
        where_clause = " AND ".join(conditions)
        cursor = self.conn.execute(
            f"""
            SELECT
                r.*,
                u.display_name AS author_name,
                t.title AS track_title,
                t.artist AS track_artist,
                t.cover_url AS track_image
            FROM reviews r
            LEFT JOIN users u ON u.user_id = r.user_id
            LEFT JOIN tracks t ON t.track_id = r.track_id
            WHERE {where_clause}
            ORDER BY {order_by}
            LIMIT ?
            """,  # noqa: S608
            tuple(params),
        )
        rows = cursor.fetchall()
        return [_row_to_review(r) for r in rows]

    def list_by_user(self, user_id: int, limit: int = 50) -> list[ReviewComment]:
        cursor = self.conn.execute(
            """
            SELECT
                r.*,
                u.display_name AS author_name,
                t.title AS track_title,
                t.artist AS track_artist,
                t.cover_url AS track_image
            FROM reviews r
            LEFT JOIN users u ON u.user_id = r.user_id
            LEFT JOIN tracks t ON t.track_id = r.track_id
            WHERE r.user_id = ?
              AND r.is_deleted = 0
              AND COALESCE(t.is_deleted, 0) = 0
            ORDER BY r.created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        rows = cursor.fetchall()
        return [_row_to_review(r) for r in rows]

    def has_user_liked(self, review_id: int, user_id: int) -> bool:
        cursor = self.conn.execute(
            "SELECT 1 FROM review_likes WHERE review_id = ? AND user_id = ?",
            (review_id, user_id),
        )
        return cursor.fetchone() is not None

    def record_like(self, review_id: int, user_id: int) -> None:
        created_at_str = datetime.now(UTC).isoformat()
        with transaction(self.conn) as cursor:
            cursor.execute(
                """
                INSERT OR IGNORE INTO review_likes (review_id, user_id, created_at)
                VALUES (?, ?, ?)
                """,
                (review_id, user_id, created_at_str),
            )

    def find_active_by_user_and_track(
        self, user_id: int, track_id: int
    ) -> ReviewComment | None:
        cursor = self.conn.execute(
            """
            SELECT
                r.*,
                u.display_name AS author_name,
                t.title AS track_title,
                t.artist AS track_artist,
                t.cover_url AS track_image
            FROM reviews r
            LEFT JOIN users u ON u.user_id = r.user_id
            LEFT JOIN tracks t ON t.track_id = r.track_id
            WHERE r.user_id = ? AND r.track_id = ? AND r.is_deleted = 0
            """,
            (user_id, track_id),
        )
        row = cursor.fetchone()
        return _row_to_review(row) if row else None

    def delete(self, review_id: int) -> bool:
        with transaction(self.conn) as cursor:
            cursor.execute(
                "UPDATE reviews SET is_deleted = 1 WHERE review_id = ?",
                (review_id,),
            )
            return cursor.rowcount > 0


__all__ = ["SQLiteReviewRepository"]
