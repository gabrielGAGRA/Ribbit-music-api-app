"""Initializes an isolated SQLite database for Playwright browser E2E runs."""

import argparse
import sqlite3
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.init_db import init_database  # noqa: E402


def prepare_e2e_database(db_path: Path) -> int:
    """Creates a clean E2E SQLite database seeded from database/dump.sql."""
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(f"{db_path}{suffix}")
        if candidate.exists():
            candidate.unlink()

    exit_code = init_database(db_path=str(db_path), force=True)
    if exit_code != 0:
        return exit_code

    conn = sqlite3.connect(str(db_path))
    try:
        # Enable Spotify Premium flag for demo listener so Pond Jam E2E flows run end-to-end.
        conn.execute(
            """
            UPDATE users
            SET spotify_id = COALESCE(spotify_id, 'spotify-demo-premium'),
                spotify_premium = 1
            WHERE email = 'usuario@ribbit.example.com'
            """
        )
        # Populate example.com placeholders on NULL media fields so offline CI
        # never blocks on external iTunes HTTP timeouts.
        conn.execute(
            """
            UPDATE tracks
            SET cover_url = COALESCE(cover_url, 'https://example.com/cover/' || track_id || '.jpg'),
                itunes_preview_url = COALESCE(itunes_preview_url, 'https://example.com/preview/' || track_id || '.mp3')
            """
        )
        conn.commit()
    finally:
        conn.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for preparing the isolated E2E SQLite database."""
    parser = argparse.ArgumentParser(
        description="Prepare an isolated SQLite database for Playwright E2E tests."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=_REPO_ROOT / "e2e.db",
        help="Target SQLite path (defaults to <repo>/e2e.db).",
    )
    args = parser.parse_args(argv)
    return prepare_e2e_database(args.db_path)


if __name__ == "__main__":
    sys.exit(main())
