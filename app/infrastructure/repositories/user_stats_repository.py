"""SQLite implementation of the read-only user statistics query port."""

lazy import sqlite3

from app.application.dtos.user_dtos import (
    AnnualStatsResult,
    ArtistStat,
    GenreStat,
    MonthlyInteractionStat,
    ReleaseYearStat,
    SourceStat,
    YearlyInteractionStat,
)
from app.application.ports.repositories.user_stats_repository import (
    UserStatsRepositoryPort,
)

_TOP_RANKING_LIMIT = 10


class SQLiteUserStatsRepository(UserStatsRepositoryPort):
    """SQLite adapter executing analytical aggregations for user dashboards."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def get_user_stats(
        self, user_id: int, year: int | None = None
    ) -> AnnualStatsResult:
        total_interactions, total_likes, total_superlikes, total_dislikes = (
            self._fetch_action_counts(user_id, year)
        )
        positive_total = total_likes + total_superlikes
        positive_rate = (
            round(positive_total / total_interactions, 4)
            if total_interactions > 0
            else 0.0
        )

        by_interaction_year = self._fetch_by_interaction_year(user_id)
        available_years = [item.year for item in by_interaction_year]
        total_reviews, average_rating = self._fetch_review_summary(user_id, year)

        return AnnualStatsResult(
            user_id=user_id,
            year=year,
            available_years=available_years,
            total_interactions=total_interactions,
            total_likes=total_likes,
            total_superlikes=total_superlikes,
            total_dislikes=total_dislikes,
            positive_rate=positive_rate,
            top_genres=self._fetch_top_genres(user_id, year),
            top_artists=self._fetch_top_artists(user_id, year),
            by_interaction_year=by_interaction_year,
            by_month=self._fetch_by_month(user_id, year),
            by_release_year=self._fetch_by_release_year(user_id, year),
            by_source=self._fetch_by_source(user_id, year),
            total_reviews=total_reviews,
            average_rating=average_rating,
            total_playlists=self._fetch_playlist_count(user_id, year),
            total_jams_participated=self._fetch_jam_participation_count(user_id, year),
        )

    def _fetch_action_counts(
        self, user_id: int, year: int | None
    ) -> tuple[int, int, int, int]:
        row = self.conn.execute(
            """
            SELECT
                COUNT(*) AS total_interactions,
                COALESCE(SUM(CASE WHEN action = 'like' THEN 1 ELSE 0 END), 0) AS total_likes,
                COALESCE(SUM(CASE WHEN action = 'superlike' THEN 1 ELSE 0 END), 0) AS total_superlikes,
                COALESCE(SUM(CASE WHEN action = 'dislike' THEN 1 ELSE 0 END), 0) AS total_dislikes
            FROM interactions
            WHERE user_id = ?
              AND (? IS NULL OR CAST(strftime('%Y', created_at) AS INTEGER) = ?)
            """,
            (user_id, year, year),
        ).fetchone()
        if row is None:
            return 0, 0, 0, 0
        return (
            int(row["total_interactions"]),
            int(row["total_likes"]),
            int(row["total_superlikes"]),
            int(row["total_dislikes"]),
        )

    def _fetch_top_genres(self, user_id: int, year: int | None) -> list[GenreStat]:
        rows = self.conn.execute(
            """
            SELECT
                LOWER(TRIM(t.genre)) AS genre,
                COALESCE(SUM(CASE WHEN i.action = 'like' THEN 1 ELSE 0 END), 0) AS likes,
                COALESCE(SUM(CASE WHEN i.action = 'superlike' THEN 1 ELSE 0 END), 0) AS superlikes,
                COALESCE(SUM(CASE WHEN i.action = 'dislike' THEN 1 ELSE 0 END), 0) AS dislikes,
                COALESCE(SUM(CASE WHEN i.action IN ('like', 'superlike') THEN 1 ELSE 0 END), 0) AS total_positive
            FROM interactions i
            JOIN tracks t ON t.track_id = i.track_id
            WHERE i.user_id = ?
              AND t.is_deleted = 0
              AND t.genre IS NOT NULL
              AND TRIM(t.genre) != ''
              AND LOWER(TRIM(t.genre)) != 'unknown'
              AND (? IS NULL OR CAST(strftime('%Y', i.created_at) AS INTEGER) = ?)
            GROUP BY LOWER(TRIM(t.genre))
            ORDER BY total_positive DESC, superlikes DESC, likes DESC, genre ASC
            LIMIT ?
            """,
            (user_id, year, year, _TOP_RANKING_LIMIT),
        ).fetchall()
        return [
            GenreStat(
                genre=str(row["genre"]),
                likes=int(row["likes"]),
                superlikes=int(row["superlikes"]),
                dislikes=int(row["dislikes"]),
                total_positive=int(row["total_positive"]),
            )
            for row in rows
        ]

    def _fetch_top_artists(self, user_id: int, year: int | None) -> list[ArtistStat]:
        rows = self.conn.execute(
            """
            SELECT
                TRIM(t.artist) AS artist,
                COALESCE(SUM(CASE WHEN i.action = 'like' THEN 1 ELSE 0 END), 0) AS likes,
                COALESCE(SUM(CASE WHEN i.action = 'superlike' THEN 1 ELSE 0 END), 0) AS superlikes,
                COALESCE(SUM(CASE WHEN i.action = 'dislike' THEN 1 ELSE 0 END), 0) AS dislikes,
                COALESCE(SUM(CASE WHEN i.action IN ('like', 'superlike') THEN 1 ELSE 0 END), 0) AS total_positive
            FROM interactions i
            JOIN tracks t ON t.track_id = i.track_id
            WHERE i.user_id = ?
              AND t.is_deleted = 0
              AND t.artist IS NOT NULL
              AND TRIM(t.artist) != ''
              AND (? IS NULL OR CAST(strftime('%Y', i.created_at) AS INTEGER) = ?)
            GROUP BY TRIM(t.artist)
            ORDER BY total_positive DESC, superlikes DESC, likes DESC, artist ASC
            LIMIT ?
            """,
            (user_id, year, year, _TOP_RANKING_LIMIT),
        ).fetchall()
        return [
            ArtistStat(
                artist=str(row["artist"]),
                likes=int(row["likes"]),
                superlikes=int(row["superlikes"]),
                dislikes=int(row["dislikes"]),
                total_positive=int(row["total_positive"]),
            )
            for row in rows
        ]

    def _fetch_by_interaction_year(self, user_id: int) -> list[YearlyInteractionStat]:
        rows = self.conn.execute(
            """
            SELECT
                CAST(strftime('%Y', created_at) AS INTEGER) AS year,
                COALESCE(SUM(CASE WHEN action = 'like' THEN 1 ELSE 0 END), 0) AS likes,
                COALESCE(SUM(CASE WHEN action = 'superlike' THEN 1 ELSE 0 END), 0) AS superlikes,
                COALESCE(SUM(CASE WHEN action = 'dislike' THEN 1 ELSE 0 END), 0) AS dislikes,
                COUNT(*) AS total
            FROM interactions
            WHERE user_id = ? AND created_at IS NOT NULL
            GROUP BY year
            HAVING year IS NOT NULL
            ORDER BY year DESC
            """,
            (user_id,),
        ).fetchall()
        return [
            YearlyInteractionStat(
                year=int(row["year"]),
                likes=int(row["likes"]),
                superlikes=int(row["superlikes"]),
                dislikes=int(row["dislikes"]),
                total=int(row["total"]),
            )
            for row in rows
        ]

    def _fetch_by_month(
        self, user_id: int, year: int | None
    ) -> list[MonthlyInteractionStat]:
        rows = self.conn.execute(
            """
            SELECT
                CAST(strftime('%m', created_at) AS INTEGER) AS month,
                COALESCE(SUM(CASE WHEN action = 'like' THEN 1 ELSE 0 END), 0) AS likes,
                COALESCE(SUM(CASE WHEN action = 'superlike' THEN 1 ELSE 0 END), 0) AS superlikes,
                COALESCE(SUM(CASE WHEN action = 'dislike' THEN 1 ELSE 0 END), 0) AS dislikes,
                COUNT(*) AS total
            FROM interactions
            WHERE user_id = ?
              AND created_at IS NOT NULL
              AND (? IS NULL OR CAST(strftime('%Y', created_at) AS INTEGER) = ?)
            GROUP BY month
            HAVING month IS NOT NULL
            ORDER BY month ASC
            """,
            (user_id, year, year),
        ).fetchall()
        return [
            MonthlyInteractionStat(
                month=int(row["month"]),
                likes=int(row["likes"]),
                superlikes=int(row["superlikes"]),
                dislikes=int(row["dislikes"]),
                total=int(row["total"]),
            )
            for row in rows
        ]

    def _fetch_by_release_year(
        self, user_id: int, year: int | None
    ) -> list[ReleaseYearStat]:
        rows = self.conn.execute(
            """
            SELECT
                t.release_year AS release_year,
                COALESCE(SUM(CASE WHEN i.action = 'like' THEN 1 ELSE 0 END), 0) AS likes,
                COALESCE(SUM(CASE WHEN i.action = 'superlike' THEN 1 ELSE 0 END), 0) AS superlikes,
                COUNT(*) AS total_positive
            FROM interactions i
            JOIN tracks t ON t.track_id = i.track_id
            WHERE i.user_id = ?
              AND t.is_deleted = 0
              AND t.release_year IS NOT NULL
              AND i.action IN ('like', 'superlike')
              AND (? IS NULL OR CAST(strftime('%Y', i.created_at) AS INTEGER) = ?)
            GROUP BY t.release_year
            ORDER BY t.release_year DESC
            """,
            (user_id, year, year),
        ).fetchall()
        return [
            ReleaseYearStat(
                release_year=int(row["release_year"]),
                likes=int(row["likes"]),
                superlikes=int(row["superlikes"]),
                total_positive=int(row["total_positive"]),
            )
            for row in rows
        ]

    def _fetch_by_source(self, user_id: int, year: int | None) -> list[SourceStat]:
        rows = self.conn.execute(
            """
            SELECT
                COALESCE(NULLIF(TRIM(source), ''), 'unknown') AS source,
                COALESCE(SUM(CASE WHEN action = 'like' THEN 1 ELSE 0 END), 0) AS likes,
                COALESCE(SUM(CASE WHEN action = 'superlike' THEN 1 ELSE 0 END), 0) AS superlikes,
                COALESCE(SUM(CASE WHEN action = 'dislike' THEN 1 ELSE 0 END), 0) AS dislikes,
                COUNT(*) AS total
            FROM interactions
            WHERE user_id = ?
              AND (? IS NULL OR CAST(strftime('%Y', created_at) AS INTEGER) = ?)
            GROUP BY COALESCE(NULLIF(TRIM(source), ''), 'unknown')
            ORDER BY total DESC, source ASC
            """,
            (user_id, year, year),
        ).fetchall()
        return [
            SourceStat(
                source=str(row["source"]),
                likes=int(row["likes"]),
                superlikes=int(row["superlikes"]),
                dislikes=int(row["dislikes"]),
                total=int(row["total"]),
            )
            for row in rows
        ]

    def _fetch_review_summary(
        self, user_id: int, year: int | None
    ) -> tuple[int, float]:
        row = self.conn.execute(
            """
            SELECT
                COUNT(*) AS total_reviews,
                COALESCE(ROUND(AVG(rating), 2), 0.0) AS average_rating
            FROM reviews
            WHERE user_id = ?
              AND is_deleted = 0
              AND (? IS NULL OR CAST(strftime('%Y', created_at) AS INTEGER) = ?)
            """,
            (user_id, year, year),
        ).fetchone()
        if row is None:
            return 0, 0.0
        return int(row["total_reviews"]), float(row["average_rating"])

    def _fetch_playlist_count(self, user_id: int, year: int | None) -> int:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM playlists
            WHERE user_id = ?
              AND (? IS NULL OR CAST(strftime('%Y', created_at) AS INTEGER) = ?)
            """,
            (user_id, year, year),
        ).fetchone()
        return int(row["total"]) if row is not None else 0

    def _fetch_jam_participation_count(self, user_id: int, year: int | None) -> int:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM jam_participants
            WHERE user_id = ?
              AND (? IS NULL OR CAST(strftime('%Y', joined_at) AS INTEGER) = ?)
            """,
            (user_id, year, year),
        ).fetchone()
        return int(row["total"]) if row is not None else 0
