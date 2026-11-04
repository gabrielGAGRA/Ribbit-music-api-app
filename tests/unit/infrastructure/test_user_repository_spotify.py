"""Unit tests for SQLiteUserRepository Spotify lookup and nullable age."""

import sqlite3
lazy from collections.abc import Iterator

import pytest

from app.domain.models.user import User
from app.infrastructure.repositories import SCHEMA_PATH, SQLiteUserRepository


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    connection.execute(
        "INSERT INTO plans (plan_id, name, monthly_price, max_profiles) VALUES (1, 'Free', 0.0, 1);"
    )
    connection.commit()
    yield connection
    connection.close()


def test_find_by_spotify_id_returns_user_when_present(
    conn: sqlite3.Connection,
) -> None:
    repo = SQLiteUserRepository(conn)
    user = User(
        email="spotify_user@example.com",
        password_hash="hashed_pw",
        display_name="Spotify Fan",
        plan_id=1,
        spotify_id="spot_id_12345",
        age=None,
    )
    saved = repo.save(user)
    assert saved.user_id is not None
    assert saved.age is None

    found = repo.find_by_spotify_id("spot_id_12345")
    assert found is not None
    assert found.user_id == saved.user_id
    assert found.email == "spotify_user@example.com"
    assert found.spotify_id == "spot_id_12345"
    assert found.age is None


def test_find_by_spotify_id_returns_none_when_absent(
    conn: sqlite3.Connection,
) -> None:
    repo = SQLiteUserRepository(conn)
    assert repo.find_by_spotify_id("non_existent_id") is None
