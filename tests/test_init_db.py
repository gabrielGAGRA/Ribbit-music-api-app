"""Integration tests for database/dump.sql and scripts/init_db.py."""

import sqlite3
lazy from pathlib import Path

import pytest

from app.composition import create_app
from app.config import Settings
from scripts.init_db import DEFAULT_DUMP_PATH, init_database
from scripts.prepare_e2e_db import E2E_DUMP_PATH


@pytest.mark.integration
def test_init_database_from_dump_and_app_startup(tmp_path: Path) -> None:
    """Loading clean database/dump.sql initializes schema/plans/costs and boots FastAPI cleanly."""
    db_path = tmp_path / "clean_install.db"

    rc = init_database(db_path=str(db_path), dump_path=DEFAULT_DUMP_PATH)
    assert rc == 0
    assert db_path.is_file()

    # Second run without --force is a no-op
    rc_second = init_database(db_path=str(db_path), dump_path=DEFAULT_DUMP_PATH)
    assert rc_second == 0

    conn = sqlite3.connect(db_path)
    try:
        tracks_count = conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
        users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        plans_count = conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0]
        reviews_count = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
        jams_count = conn.execute("SELECT COUNT(*) FROM jams").fetchone()[0]
    finally:
        conn.close()

    assert tracks_count == 0
    assert users_count == 0
    assert plans_count == 3
    assert reviews_count == 0
    assert jams_count == 0

    # Verify FastAPI composition + seed_database boots cleanly on top of dump.sql
    settings = Settings(database_path=str(db_path))
    app = create_app(settings=settings)
    assert app is not None


@pytest.mark.integration
def test_e2e_dump_fixture_populates_demo_data(tmp_path: Path) -> None:
    """Loading the dedicated E2E dump fixture populates full demo entities for Playwright."""
    db_path = tmp_path / "e2e_install.db"

    rc = init_database(db_path=str(db_path), dump_path=E2E_DUMP_PATH)
    assert rc == 0
    assert db_path.is_file()

    conn = sqlite3.connect(db_path)
    try:
        tracks_count = conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
        users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        plans_count = conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0]
        reviews_count = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
        jams_count = conn.execute("SELECT COUNT(*) FROM jams").fetchone()[0]
        example_urls = conn.execute(
            "SELECT COUNT(*) FROM tracks WHERE cover_url LIKE '%example.com%' OR itunes_preview_url LIKE '%example.com%'"
        ).fetchone()[0]
    finally:
        conn.close()

    assert tracks_count >= 500
    assert users_count >= 6
    assert plans_count == 3
    assert reviews_count >= 3
    assert jams_count >= 1
    assert example_urls == 0
