"""SQLite implementation of the user persistence port."""

from datetime import UTC, datetime
lazy import sqlite3

from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.user import User


def _row_to_user(row: sqlite3.Row) -> User:
    blocked_raw = row["blocked_genres"]
    blocked_genres = (
        frozenset(g.strip() for g in blocked_raw.split(",") if g.strip())
        if blocked_raw
        else frozenset()
    )
    created_at = (
        datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
    )
    keys = row.keys()
    birth_date = row["birth_date"] if "birth_date" in keys else None
    return User(
        user_id=row["user_id"],
        email=row["email"],
        password_hash=row["password_hash"],
        display_name=row["display_name"],
        age=row["age"],
        plan_id=row["plan_id"],
        spotify_id=row["spotify_id"],
        primary_account_id=row["primary_account_id"],
        blocked_genres=blocked_genres,
        is_admin=bool(row["is_admin"]),
        created_at=created_at,
        birth_date=birth_date,
    )


class SQLiteUserRepository(UserRepositoryPort):
    """SQLite adapter implementing UserRepositoryPort."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def find_by_id(self, user_id: int) -> User | None:
        cursor = self.conn.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        return _row_to_user(row) if row else None

    def find_by_email(self, email: str) -> User | None:
        cursor = self.conn.execute(
            "SELECT * FROM users WHERE lower(email) = ?",
            (email.lower().strip(),),
        )
        row = cursor.fetchone()
        return _row_to_user(row) if row else None

    def save(self, user: User) -> User:
        blocked_str = (
            ",".join(sorted(user.blocked_genres)) if user.blocked_genres else None
        )
        if user.user_id is not None:
            cursor = self.conn.execute(
                "SELECT user_id FROM users WHERE user_id = ?",
                (user.user_id,),
            )
            if cursor.fetchone():
                self.conn.execute(
                    """
                    UPDATE users
                    SET email = ?,
                        password_hash = ?,
                        spotify_id = ?,
                        display_name = ?,
                        age = ?,
                        plan_id = ?,
                        primary_account_id = ?,
                        blocked_genres = ?,
                        is_admin = ?,
                        birth_date = ?
                    WHERE user_id = ?
                    """,
                    (
                        user.email.lower().strip(),
                        user.password_hash,
                        user.spotify_id,
                        user.display_name,
                        user.age,
                        user.plan_id,
                        user.primary_account_id,
                        blocked_str,
                        1 if user.is_admin else 0,
                        user.birth_date,
                        user.user_id,
                    ),
                )
                self.conn.commit()
                return self.find_by_id(user.user_id) or user
            raise EntityNotFoundError(entity_name="User", entity_id=user.user_id)

        created_at_str = (user.created_at or datetime.now(UTC)).isoformat()
        cursor = self.conn.execute(
            """
            INSERT INTO users (
                email, password_hash, spotify_id, display_name, age,
                plan_id, primary_account_id, blocked_genres, is_admin, created_at, birth_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user.email.lower().strip(),
                user.password_hash,
                user.spotify_id,
                user.display_name,
                user.age,
                user.plan_id,
                user.primary_account_id,
                blocked_str,
                1 if user.is_admin else 0,
                created_at_str,
                user.birth_date,
            ),
        )
        self.conn.commit()
        new_id = cursor.lastrowid
        if new_id is not None:
            return self.find_by_id(new_id) or user
        return user

    def delete(self, user_id: int) -> bool:
        cursor = self.conn.execute(
            "DELETE FROM users WHERE user_id = ?",
            (user_id,),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def list_dependents(self, primary_account_id: int) -> list[User]:
        cursor = self.conn.execute(
            "SELECT * FROM users WHERE primary_account_id = ?",
            (primary_account_id,),
        )
        rows = cursor.fetchall()
        return [_row_to_user(r) for r in rows]

    def list_all(self) -> list[User]:
        cursor = self.conn.execute("SELECT * FROM users ORDER BY user_id ASC")
        rows = cursor.fetchall()
        return [_row_to_user(r) for r in rows]

    def count_all(self) -> int:
        cursor = self.conn.execute("SELECT COUNT(*) FROM users")
        row = cursor.fetchone()
        return int(row[0]) if row else 0


__all__ = ["SQLiteUserRepository"]
