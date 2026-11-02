"""Infrastructure layer package providing external I/O adapters and repositories."""

from app.infrastructure.adapters import (
    ITunesAdapter,
    SpotifyAdapter,
)
from app.infrastructure.repositories import (
    DEFAULT_DATABASE_PATH,
    SCHEMA_PATH,
    SQLiteAuditLogRepository,
    SQLiteInteractionRepository,
    SQLiteJamRepository,
    SQLitePlanRepository,
    SQLitePlaylistRepository,
    SQLiteReviewRepository,
    SQLiteTrackRepository,
    SQLiteUserRepository,
    create_connection,
    transaction,
)
from app.infrastructure.security import PBKDF2PasswordHasher
from app.infrastructure.telemetry import (
    CorrelationIdMiddleware,
    JSONLogFormatter,
    configure_logging,
    log_operational_event,
)

__all__ = [
    "CorrelationIdMiddleware",
    "DEFAULT_DATABASE_PATH",
    "ITunesAdapter",
    "JSONLogFormatter",
    "PBKDF2PasswordHasher",
    "SCHEMA_PATH",
    "SQLiteAuditLogRepository",
    "SQLiteInteractionRepository",
    "SQLiteJamRepository",
    "SQLitePlanRepository",
    "SQLitePlaylistRepository",
    "SQLiteReviewRepository",
    "SQLiteTrackRepository",
    "SQLiteUserRepository",
    "SpotifyAdapter",
    "configure_logging",
    "create_connection",
    "log_operational_event",
    "transaction",
]
