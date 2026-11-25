"""SQLite implementation of the user persistence port."""

from datetime import UTC, datetime
from typing import Any
lazy import sqlite3

from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.user import User
from app.infrastructure.repositories.connection import transaction


def _row_to_user(row: sqlite3.Row) -> User:
    keys = row.keys()
    blocked_raw = row["blocked_genres"] if "blocked_genres" in keys else None
    blocked_genres = (
        frozenset(g.strip() for g in blocked_raw.split(",") if g.strip())
        if blocked_raw
        else frozenset()
    )
    favorite_raw = row["favorite_genres"] if "favorite_genres" in keys else None
    favorite_genres = (
        frozenset(g.strip() for g in favorite_raw.split(",") if g.strip())
        if favorite_raw
        else frozenset()
    )
    created_at = (
        datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
    )
    birth_date = row["birth_date"] if "birth_date" in keys else None
    preferred_theme = (
        row["preferred_theme"]
        if "preferred_theme" in keys and row["preferred_theme"]
        else "light"
    )
    spotify_premium = (
        bool(row["spotify_premium"]) if "spotify_premium" in keys else False
    )
    spotify_access_token = (
        row["spotify_access_token"] if "spotify_access_token" in keys else None
    )
    spotify_refresh_token = (
        row["spotify_refresh_token"] if "spotify_refresh_token" in keys else None
    )
    raw_token_expiry = (
        row["spotify_token_expires_at"] if "spotify_token_expires_at" in keys else None
    )
    spotify_token_expires_at = (
        datetime.fromisoformat(raw_token_expiry) if raw_token_expiry else None
    )
    return User(
        user_id=row["user_id"],
        email=row["email"],
        password_hash=row["password_hash"],
        display_name=row["display_name"],
        age=row["age"],
        plan_id=row["plan_id"],
        spotify_id=row["spotify_id"],
        spotify_premium=spotify_premium,
        spotify_access_token=spotify_access_token,
        spotify_refresh_token=spotify_refresh_token,
        spotify_token_expires_at=spotify_token_expires_at,
        primary_account_id=row["primary_account_id"],
        blocked_genres=blocked_genres,
        favorite_genres=favorite_genres,
        preferred_theme=preferred_theme,
        is_admin=bool(row["is_admin"]),
        created_at=created_at,
        birth_date=birth_date,
    )


class SQLiteUserRepository(UserRepositoryPort):
    """SQLite adapter implementing UserRepositoryPort."""

    def __init__(
        self, conn: sqlite3.Connection, sync_service: Any | None = None
    ) -> None:
        self.conn = conn
        self._sync = sync_service

    def _find_by_id_local(self, user_id: int) -> User | None:
        cursor = self.conn.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        return _row_to_user(row) if row else None

    def find_by_id(self, user_id: int) -> User | None:
        if self._sync is not None:
            self._sync.pull_deltas()
        return self._find_by_id_local(user_id)

    def find_by_email(self, email: str) -> User | None:
        if self._sync is not None:
            self._sync.pull_deltas()
        cursor = self.conn.execute(
            "SELECT * FROM users WHERE lower(email) = ?",
            (email.lower().strip(),),
        )
        row = cursor.fetchone()
        return _row_to_user(row) if row else None

    def find_by_spotify_id(self, spotify_id: str) -> User | None:
        if self._sync is not None:
            self._sync.pull_deltas()
        cursor = self.conn.execute(
            "SELECT * FROM users WHERE spotify_id = ?",
            (spotify_id.strip(),),
        )
        row = cursor.fetchone()
        return _row_to_user(row) if row else None

    def save(self, user: User) -> User:
        if self._sync is not None:
            self._sync.pull_deltas()
        blocked_str = (
            ",".join(sorted(user.blocked_genres)) if user.blocked_genres else None
        )
        favorite_str = (
            ",".join(sorted(user.favorite_genres)) if user.favorite_genres else None
        )
        if user.user_id is not None:
            with transaction(self.conn) as cursor:
                cursor.execute(
                    "SELECT user_id FROM users WHERE user_id = ?",
                    (user.user_id,),
                )
                if not cursor.fetchone():
                    raise EntityNotFoundError(
                        entity_name="User", entity_id=user.user_id
                    )
                cursor.execute(
                    """
                    UPDATE users
                    SET email = ?,
                        password_hash = ?,
                        spotify_id = ?,
                        spotify_premium = ?,
                        spotify_access_token = ?,
                        spotify_refresh_token = ?,
                        spotify_token_expires_at = ?,
                        display_name = ?,
                        age = ?,
                        plan_id = ?,
                        primary_account_id = ?,
                        blocked_genres = ?,
                        favorite_genres = ?,
                        preferred_theme = ?,
                        is_admin = ?,
                        birth_date = ?,
                        created_at = CASE
                            WHEN created_at = '1970-01-01T00:00:00+00:00' THEN ?
                            ELSE created_at
                        END
                    WHERE user_id = ?
                    """,
                    (
                        user.email.lower().strip(),
                        user.password_hash,
                        user.spotify_id,
                        1 if user.spotify_premium else 0,
                        user.spotify_access_token,
                        user.spotify_refresh_token,
                        (
                            user.spotify_token_expires_at.isoformat()
                            if user.spotify_token_expires_at is not None
                            else None
                        ),
                        user.display_name,
                        user.age,
                        user.plan_id,
                        user.primary_account_id,
                        blocked_str,
                        favorite_str,
                        user.preferred_theme,
                        1 if user.is_admin else 0,
                        user.birth_date,
                        datetime.now(UTC).isoformat(),
                        user.user_id,
                    ),
                )
                if self._sync is not None:
                    self._sync.push_user_by_id(user.user_id)
            return self._find_by_id_local(user.user_id) or user

        created_at_str = (user.created_at or datetime.now(UTC)).isoformat()
        with transaction(self.conn) as cursor:
            cursor.execute(
                """
                INSERT INTO users (
                    email, password_hash, spotify_id, spotify_premium,
                    spotify_access_token, spotify_refresh_token, spotify_token_expires_at,
                    display_name, age,
                    plan_id, primary_account_id, blocked_genres, favorite_genres,
                    preferred_theme, is_admin, created_at, birth_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user.email.lower().strip(),
                    user.password_hash,
                    user.spotify_id,
                    1 if user.spotify_premium else 0,
                    user.spotify_access_token,
                    user.spotify_refresh_token,
                    (
                        user.spotify_token_expires_at.isoformat()
                        if user.spotify_token_expires_at is not None
                        else None
                    ),
                    user.display_name,
                    user.age,
                    user.plan_id,
                    user.primary_account_id,
                    blocked_str,
                    favorite_str,
                    user.preferred_theme,
                    1 if user.is_admin else 0,
                    created_at_str,
                    user.birth_date,
                ),
            )
            new_id = cursor.lastrowid
            if new_id is not None and self._sync is not None:
                self._sync.push_user_by_id(new_id)
        if new_id is not None:
            return self._find_by_id_local(new_id) or user
        return user

    def delete(self, user_id: int) -> bool:
        if self._sync is not None:
            self._sync.pull_deltas()
        child_docs: list[tuple[str, str]] = []
        dependent_ids: list[int] = []
        with transaction(self.conn) as cursor:
            row = cursor.execute(
                "SELECT email FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            email = str(row["email"]) if row and row["email"] else None
            dependent_ids = [
                int(r["user_id"])
                for r in cursor.execute(
                    "SELECT user_id FROM users WHERE primary_account_id = ?",
                    (user_id,),
                ).fetchall()
            ]
            if email and self._sync is not None:
                child_docs = self._sync.prepare_user_delete(cursor, user_id, email)
            cursor.execute(
                "DELETE FROM users WHERE user_id = ?",
                (user_id,),
            )
            deleted = cursor.rowcount > 0
            if deleted and email and self._sync is not None:
                for dependent_id in dependent_ids:
                    self._sync.push_user_by_id(dependent_id)
                self._sync.push_user_deleted(email, child_docs)
        return deleted

    def list_dependents(self, primary_account_id: int) -> list[User]:
        if self._sync is not None:
            self._sync.pull_deltas()
        cursor = self.conn.execute(
            "SELECT * FROM users WHERE primary_account_id = ?",
            (primary_account_id,),
        )
        rows = cursor.fetchall()
        return [_row_to_user(r) for r in rows]

    def list_all(self) -> list[User]:
        if self._sync is not None:
            self._sync.pull_deltas()
        cursor = self.conn.execute("SELECT * FROM users ORDER BY user_id ASC")
        rows = cursor.fetchall()
        return [_row_to_user(r) for r in rows]

    def count_all(self) -> int:
        cursor = self.conn.execute("SELECT COUNT(*) FROM users")
        row = cursor.fetchone()
        return int(row[0]) if row else 0


__all__ = ["SQLiteUserRepository"]
