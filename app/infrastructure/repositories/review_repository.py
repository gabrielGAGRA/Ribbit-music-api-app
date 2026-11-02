"""SQLite implementation of the review and comment persistence port."""

from datetime import UTC, datetime, timedelta
lazy import sqlite3

from app.application.ports.repositories.review_repository import ReviewRepositoryPort
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.review import ReviewComment


def _row_to_review(row: sqlite3.Row) -> ReviewComment:
    created_at = (
        datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
    )
    return ReviewComment(
        review_id=row["review_id"],
        user_id=row["user_id"],
        track_id=row["track_id"],
        initial_rating=int(row["rating"]),
        text=row["text"],
        initial_likes_count=int(row["likes_count"]),
        is_deleted=bool(row["is_deleted"]),
        created_at=created_at,
    )


class SQLiteReviewRepository(ReviewRepositoryPort):
    """SQLite adapter implementing ReviewRepositoryPort."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def find_by_id(self, review_id: int) -> ReviewComment | None:
        cursor = self.conn.execute(
            "SELECT * FROM reviews WHERE review_id = ?",
            (review_id,),
        )
        row = cursor.fetchone()
        return _row_to_review(row) if row else None

    def save(self, review: ReviewComment) -> ReviewComment:
        if review.review_id is not None:
            cursor = self.conn.execute(
                "SELECT review_id FROM reviews WHERE review_id = ?",
                (review.review_id,),
            )
            if cursor.fetchone():
                self.conn.execute(
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
                self.conn.commit()
                return self.find_by_id(review.review_id) or review
            raise EntityNotFoundError(
                entity_name="ReviewComment", entity_id=review.review_id
            )

        created_at_str = (review.created_at or datetime.now(UTC)).isoformat()
        cursor = self.conn.execute(
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
        self.conn.commit()
        new_id = cursor.lastrowid
        if new_id is not None:
            return self.find_by_id(new_id) or review
        return review

    def list_by_track(self, track_id: int, limit: int) -> list[ReviewComment]:
        cursor = self.conn.execute(
            """
            SELECT * FROM reviews
            WHERE track_id = ? AND is_deleted = 0
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (track_id, limit),
        )
        rows = cursor.fetchall()
        return [_row_to_review(r) for r in rows]

    def list_top_recent(self, days: int, limit: int) -> list[ReviewComment]:
        min_date_str = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        cursor = self.conn.execute(
            """
            SELECT * FROM reviews
            WHERE is_deleted = 0 AND created_at >= ?
            ORDER BY likes_count DESC, created_at DESC
            LIMIT ?
            """,
            (min_date_str, limit),
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
        self.conn.execute(
            """
            INSERT OR IGNORE INTO review_likes (review_id, user_id, created_at)
            VALUES (?, ?, ?)
            """,
            (review_id, user_id, created_at_str),
        )
        self.conn.commit()

    def find_active_by_user_and_track(
        self, user_id: int, track_id: int
    ) -> ReviewComment | None:
        cursor = self.conn.execute(
            """
            SELECT * FROM reviews
            WHERE user_id = ? AND track_id = ? AND is_deleted = 0
            """,
            (user_id, track_id),
        )
        row = cursor.fetchone()
        return _row_to_review(row) if row else None

    def delete(self, review_id: int) -> bool:
        cursor = self.conn.execute(
            "UPDATE reviews SET is_deleted = 1 WHERE review_id = ?",
            (review_id,),
        )
        self.conn.commit()
        return cursor.rowcount > 0


__all__ = ["SQLiteReviewRepository"]
