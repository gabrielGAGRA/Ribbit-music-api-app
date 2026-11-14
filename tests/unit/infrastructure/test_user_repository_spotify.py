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
    assert found.spotify_premium is False
    assert found.age is None


def test_save_persists_and_updates_spotify_premium_flag(
    conn: sqlite3.Connection,
) -> None:
    repo = SQLiteUserRepository(conn)
    user = repo.save(
        User(
            email="prem@example.com",
            password_hash="hashed_pw",
            display_name="Prem Fan",
            plan_id=1,
            spotify_id="spot_prem_1",
            spotify_premium=True,
        )
    )
    raw = conn.execute(
        "SELECT spotify_premium FROM users WHERE user_id = ?",
        (user.user_id,),
    ).fetchone()
    assert raw["spotify_premium"] == 1
    assert user.spotify_premium is True

    user.update_spotify_premium(False)
    updated = repo.save(user)
    raw_after = conn.execute(
        "SELECT spotify_premium FROM users WHERE user_id = ?",
        (user.user_id,),
    ).fetchone()
    assert raw_after["spotify_premium"] == 0
    assert updated.spotify_premium is False


def test_find_by_spotify_id_returns_none_when_absent(
    conn: sqlite3.Connection,
) -> None:
    repo = SQLiteUserRepository(conn)
    assert repo.find_by_spotify_id("non_existent_id") is None


def test_save_persists_spotify_tokens_and_clears_on_id_change(
    conn: sqlite3.Connection,
) -> None:
    from datetime import UTC, datetime

    repo = SQLiteUserRepository(conn)
    expiry = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
    user = repo.save(
        User(
            email="tokens@example.com",
            password_hash="hashed_pw",
            display_name="Token User",
            plan_id=1,
            spotify_id="spot_tok_1",
            spotify_premium=True,
            spotify_access_token="acc_1",
            spotify_refresh_token="ref_1",
            spotify_token_expires_at=expiry,
        )
    )
    assert user.spotify_access_token == "acc_1"
    assert user.spotify_refresh_token == "ref_1"
    assert user.spotify_token_expires_at == expiry

    user.link_spotify("spot_tok_2")
    updated = repo.save(user)
    assert updated.spotify_id == "spot_tok_2"
    assert updated.spotify_premium is False
    assert updated.spotify_access_token is None
    assert updated.spotify_refresh_token is None
    assert updated.spotify_token_expires_at is None
