"""CLI script to initialize the SQLite database from database/dump.sql."""

import argparse
import logging
import sys
from pathlib import Path
lazy import sqlite3

_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from app.config import load_settings  # noqa: E402
from app.infrastructure.repositories.connection import create_connection  # noqa: E402

logger = logging.getLogger("scripts.init_db")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

DEFAULT_DUMP_PATH = Path(__file__).resolve().parent.parent / "database" / "dump.sql"


def _has_existing_data(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'tracks'"
    ).fetchone()
    if not row:
        return False
    count_row = conn.execute("SELECT COUNT(*) FROM tracks").fetchone()
    return bool(count_row and count_row[0] > 0)


def init_database(
    db_path: str | None = None,
    dump_path: Path = DEFAULT_DUMP_PATH,
    *,
    force: bool = False,
) -> int:
    """Loads schema and initial seed data from dump.sql if the database is empty."""
    if not dump_path.is_file():
        logger.error("SQL dump file not found at %s", dump_path)
        return 1

    target_db = db_path or load_settings().database_path
    if target_db != ":memory:" and not target_db.startswith("file:"):
        Path(target_db).parent.mkdir(parents=True, exist_ok=True)

    conn = create_connection(target_db)
    try:
        if not force and _has_existing_data(conn):
            logger.info(
                "Database '%s' already initialized; skipping dump load.", target_db
            )
            return 0

        sql_script = dump_path.read_text(encoding="utf-8")
        conn.executescript(sql_script)
        conn.commit()
        logger.info("Database '%s' initialized from '%s'.", target_db, dump_path)
    finally:
        conn.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for database initialization."""
    parser = argparse.ArgumentParser(
        description="Initialize Ribbit SQLite database from SQL dump."
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Target SQLite database path (defaults to DATABASE_PATH setting).",
    )
    parser.add_argument(
        "--dump-path",
        type=Path,
        default=DEFAULT_DUMP_PATH,
        help="Path to the SQL dump file.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Apply the SQL dump even if the database already contains tracks.",
    )
    args = parser.parse_args(argv)
    return init_database(
        db_path=args.db_path, dump_path=args.dump_path, force=args.force
    )


if __name__ == "__main__":
    sys.exit(main())
