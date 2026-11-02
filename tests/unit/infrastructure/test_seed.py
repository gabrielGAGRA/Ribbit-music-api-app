"""Unit tests for additive column migrations and non-production database seeding."""

import pytest

from app.config import Settings
from app.infrastructure.repositories.connection import create_connection
from app.infrastructure.repositories.seed import (
    migrate_additive_columns,
    seed_database,
)
from app.infrastructure.security.password_hasher import PBKDF2PasswordHasher


def test_migrate_additive_columns_upgrades_legacy_tables() -> None:
    conn = create_connection(":memory:")
    try:
        # Create legacy schema without the new columns
        conn.execute(
            """
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                spotify_id TEXT UNIQUE,
                display_name TEXT NOT NULL,
                age INTEGER NOT NULL,
                plan_id INTEGER NOT NULL,
                primary_account_id INTEGER,
                blocked_genres TEXT,
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE playlists (
                playlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                spotify_playlist_id TEXT,
                is_exported INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE jams (
                jam_id INTEGER PRIMARY KEY AUTOINCREMENT,
                host_user_id INTEGER NOT NULL,
                room_name TEXT NOT NULL,
                room_code TEXT NOT NULL UNIQUE,
                is_active INTEGER NOT NULL DEFAULT 1,
                current_track_id INTEGER,
                created_at TEXT NOT NULL
            );
            """
        )
        # Insert initial data
        conn.execute(
            """
            INSERT INTO users (
                email, password_hash, display_name, age, plan_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy@example.com",
                "hash",
                "Legacy User",
                25,
                1,
                "2026-01-01T00:00:00Z",
            ),
        )
        conn.commit()

        # Run additive migration
        migrate_additive_columns(conn)

        # Verify users has birth_date column and existing data is intact
        row = conn.execute(
            "SELECT * FROM users WHERE email = 'legacy@example.com'"
        ).fetchone()
        assert row is not None
        keys = row.keys()
        assert "birth_date" in keys
        assert row["birth_date"] is None
        assert row["display_name"] == "Legacy User"

        # Verify playlists has max_duration_seconds and deck_filters
        playlist_cols = {
            r["name"] for r in conn.execute("PRAGMA table_info(playlists)").fetchall()
        }
        assert "max_duration_seconds" in playlist_cols
        assert "deck_filters" in playlist_cols

        # Verify jams has the 7 new columns
        jam_cols = {
            r["name"] for r in conn.execute("PRAGMA table_info(jams)").fetchall()
        }
        for expected in (
            "duration_minutes",
            "max_superlikes",
            "superlikes_used",
            "skip_votes_threshold",
            "accumulated_duration_seconds",
            "deck_source",
            "source_playlist_id",
        ):
            assert expected in jam_cols

        # Verify new tables exist
        table_names = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "jam_participants" in table_names
        assert "jam_skip_votes" in table_names
        assert "review_likes" in table_names
    finally:
        conn.close()


def test_seed_database_populates_plans_admin_and_sample_tracks() -> None:
    conn = create_connection(":memory:")
    try:
        settings = Settings(
            admin_email="testadmin@ribbit.example.com",
            admin_password="TestAdminSecret2026!",
        )
        hasher = PBKDF2PasswordHasher(iterations=10_000)

        seed_database(conn, settings=settings, password_hasher=hasher)

        # Check standard plans
        plans = conn.execute(
            "SELECT name, monthly_price, max_profiles FROM plans ORDER BY plan_id ASC"
        ).fetchall()
        assert len(plans) == 3
        plan_names = [p["name"] for p in plans]
        assert "Free" in plan_names
        assert "Individual" in plan_names
        assert "Família" in plan_names

        # Check admin user
        admin = conn.execute(
            "SELECT * FROM users WHERE email = 'testadmin@ribbit.example.com'"
        ).fetchone()
        assert admin is not None
        assert admin["is_admin"] == 1
        assert hasher.verify_password("TestAdminSecret2026!", admin["password_hash"])

        # Check sample tracks
        tracks = conn.execute("SELECT * FROM tracks").fetchall()
        assert len(tracks) == 5
        titles = {t["title"] for t in tracks}
        assert "Bohemian Rhapsody" in titles
        assert "Rap God" in titles
        assert "Blinding Lights" in titles

        # Check explicit track
        rap_god = conn.execute(
            "SELECT explicit FROM tracks WHERE title = 'Rap God'"
        ).fetchone()
        assert rap_god["explicit"] == 1

        # Check idempotency: running seed a second time should not fail or duplicate
        seed_database(conn, settings=settings, password_hasher=hasher)
        plans_after = conn.execute("SELECT * FROM plans").fetchall()
        assert len(plans_after) == 3
        tracks_after = conn.execute("SELECT * FROM tracks").fetchall()
        assert len(tracks_after) == 5
    finally:
        conn.close()


def test_seed_database_raises_if_admin_email_exists_without_admin_role() -> None:
    conn = create_connection(":memory:")
    try:
        settings = Settings(admin_email="conflict@ribbit.example.com")
        migrate_additive_columns(conn)

        # Insert regular user with same email
        conn.execute(
            "INSERT INTO plans (name, monthly_price, max_profiles) VALUES ('Free', 0, 1)"
        )
        conn.execute(
            """
            INSERT INTO users (
                email, password_hash, display_name, age, plan_id, is_admin, created_at
            ) VALUES (?, ?, ?, ?, ?, 0, ?)
            """,
            (
                "conflict@ribbit.example.com",
                "hash",
                "Not Admin",
                20,
                1,
                "2026-01-01T00:00:00Z",
            ),
        )
        conn.commit()

        with pytest.raises(RuntimeError, match="exists without administrative role"):
            seed_database(conn, settings=settings)
    finally:
        conn.close()
