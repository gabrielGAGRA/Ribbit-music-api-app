"""Database seed and additive migration utilities for SQLite."""

import sqlite3
from datetime import UTC, datetime

from app.config import Settings, load_settings
from app.infrastructure.repositories.connection import SCHEMA_PATH
from app.infrastructure.security.password_hasher import PBKDF2PasswordHasher

_ADDITIVE_COLUMNS: dict[str, dict[str, str]] = {
    "users": {
        "birth_date": "TEXT",
    },
    "playlists": {
        "max_duration_seconds": "INTEGER",
        "deck_filters": "TEXT",
    },
    "jams": {
        "duration_minutes": "INTEGER NOT NULL DEFAULT 60",
        "max_superlikes": "INTEGER NOT NULL DEFAULT 10",
        "superlikes_used": "INTEGER NOT NULL DEFAULT 0",
        "skip_votes_threshold": "INTEGER NOT NULL DEFAULT 3",
        "accumulated_duration_seconds": "INTEGER NOT NULL DEFAULT 0",
        "deck_source": "TEXT NOT NULL DEFAULT 'livre'",
        "source_playlist_id": "INTEGER",
    },
}


def migrate_additive_columns(conn: sqlite3.Connection) -> None:
    """Additive, repeatable migration preserving existing data."""
    for table, columns in _ADDITIVE_COLUMNS.items():
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        if table_exists:
            info = conn.execute(f"PRAGMA table_info({table});").fetchall()
            existing_cols = {
                row["name"] if isinstance(row, sqlite3.Row) else row[1] for row in info
            }
            for col_name, col_def in columns.items():
                if col_name not in existing_cols:
                    conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def};"
                    )

    if SCHEMA_PATH.exists():
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def seed_database(
    conn: sqlite3.Connection,
    settings: Settings | None = None,
    password_hasher: PBKDF2PasswordHasher | None = None,
) -> None:
    """Populates standard plans, default admin user, and sample catalog tracks."""
    migrate_additive_columns(conn)

    standard_plans = [
        {"name": "Free", "monthly_price": 0.00, "max_profiles": 1},
        {"name": "Individual", "monthly_price": 14.90, "max_profiles": 1},
        {"name": "Família", "monthly_price": 27.90, "max_profiles": 6},
    ]

    for p in standard_plans:
        row = conn.execute(
            "SELECT plan_id FROM plans WHERE name = ?",
            (p["name"],),
        ).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO plans (name, monthly_price, max_profiles) VALUES (?, ?, ?)",
                (p["name"], p["monthly_price"], p["max_profiles"]),
            )
    conn.commit()

    resolved_settings = settings or load_settings()
    admin_email = resolved_settings.admin_email.lower().strip()
    admin_password = resolved_settings.admin_password

    row = conn.execute(
        "SELECT user_id, is_admin FROM users WHERE lower(email) = ?",
        (admin_email,),
    ).fetchone()
    if row:
        is_admin = bool(row["is_admin"] if isinstance(row, sqlite3.Row) else row[1])
        if not is_admin:
            raise RuntimeError(
                f"Seed account {admin_email} exists without administrative role."
            )
    else:
        free_plan = conn.execute(
            "SELECT plan_id FROM plans WHERE name = 'Free'"
        ).fetchone()
        if not free_plan:
            raise RuntimeError("Free plan not found for admin seed.")
        free_plan_id = (
            free_plan["plan_id"] if isinstance(free_plan, sqlite3.Row) else free_plan[0]
        )

        hasher = password_hasher or PBKDF2PasswordHasher(
            iterations=resolved_settings.password_hash_iterations
        )
        hashed_pw = hasher.hash_password(admin_password)
        now_str = datetime.now(UTC).isoformat()

        conn.execute(
            """
            INSERT INTO users (
                email, password_hash, display_name, age, plan_id, is_admin, created_at
            ) VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            (
                admin_email,
                hashed_pw,
                "Administrador Local",
                30,
                free_plan_id,
                now_str,
            ),
        )
        conn.commit()

    sample_tracks = [
        {
            "title": "Bohemian Rhapsody",
            "artist": "Queen",
            "album": "A Night at the Opera",
            "duration_seconds": 354,
            "genre": "Rock",
            "country": "Reino Unido",
            "release_year": 1975,
            "cover_url": "https://example.com/bohemian.jpg",
            "itunes_preview_url": "https://example.com/bohemian_preview.mp3",
            "explicit": 0,
        },
        {
            "title": "Shape of You",
            "artist": "Ed Sheeran",
            "album": "÷ (Divide)",
            "duration_seconds": 233,
            "genre": "Pop",
            "country": "Reino Unido",
            "release_year": 2017,
            "cover_url": "https://example.com/shapeofyou.jpg",
            "itunes_preview_url": "https://example.com/shapeofyou_preview.mp3",
            "explicit": 0,
        },
        {
            "title": "Rap God",
            "artist": "Eminem",
            "album": "The Marshall Mathers LP 2",
            "duration_seconds": 363,
            "genre": "Hip Hop",
            "country": "Estados Unidos",
            "release_year": 2013,
            "cover_url": "https://example.com/rapgod.jpg",
            "itunes_preview_url": "https://example.com/rapgod_preview.mp3",
            "explicit": 1,
        },
        {
            "title": "Blinding Lights",
            "artist": "The Weeknd",
            "album": "After Hours",
            "duration_seconds": 200,
            "genre": "Pop",
            "country": "Canadá",
            "release_year": 2020,
            "cover_url": "https://example.com/blindinglights.jpg",
            "itunes_preview_url": "https://example.com/blindinglights_preview.mp3",
            "explicit": 0,
        },
        {
            "title": "Smells Like Teen Spirit",
            "artist": "Nirvana",
            "album": "Nevermind",
            "duration_seconds": 301,
            "genre": "Grunge",
            "country": "Estados Unidos",
            "release_year": 1991,
            "cover_url": "https://example.com/nirvana.jpg",
            "itunes_preview_url": "https://example.com/nirvana_preview.mp3",
            "explicit": 0,
        },
    ]

    now_str = datetime.now(UTC).isoformat()
    for t in sample_tracks:
        existing = conn.execute(
            "SELECT track_id FROM tracks WHERE lower(title) = ? AND lower(artist) = ?",
            (str(t["title"]).lower(), str(t["artist"]).lower()),
        ).fetchone()
        if not existing:
            conn.execute(
                """
                INSERT INTO tracks (
                    title, artist, album, duration_seconds, genre, country,
                    release_year, cover_url, itunes_preview_url, explicit,
                    is_deleted, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    t["title"],
                    t["artist"],
                    t["album"],
                    t["duration_seconds"],
                    t["genre"],
                    t["country"],
                    t["release_year"],
                    t["cover_url"],
                    t["itunes_preview_url"],
                    t["explicit"],
                    now_str,
                ),
            )
    conn.commit()


run_seed = seed_database

__all__ = [
    "migrate_additive_columns",
    "run_seed",
    "seed_database",
]
