"""Concrete repository implementations conforming to application repository ports."""

from app.infrastructure.repositories.audit_log_repository import (
    SQLiteAuditLogRepository,
)
from app.infrastructure.repositories.connection import (
    DEFAULT_DATABASE_PATH,
    SCHEMA_PATH,
    create_connection,
    transaction,
)
from app.infrastructure.repositories.interaction_repository import (
    SQLiteInteractionRepository,
)
from app.infrastructure.repositories.jam_repository import (
    SQLiteJamRepository,
)
from app.infrastructure.repositories.plan_repository import (
    SQLitePlanRepository,
)
from app.infrastructure.repositories.playlist_repository import (
    SQLitePlaylistRepository,
)
from app.infrastructure.repositories.review_repository import (
    SQLiteReviewRepository,
)
from app.infrastructure.repositories.track_repository import (
    SQLiteTrackRepository,
)
from app.infrastructure.repositories.user_repository import (
    SQLiteUserRepository,
)
from app.infrastructure.repositories.user_stats_repository import (
    SQLiteUserStatsRepository,
)

AuditLogRepository = SQLiteAuditLogRepository
InteractionRepository = SQLiteInteractionRepository
JamRepository = SQLiteJamRepository
PlanRepository = SQLitePlanRepository
PlaylistRepository = SQLitePlaylistRepository
ReviewRepository = SQLiteReviewRepository
TrackRepository = SQLiteTrackRepository
UserRepository = SQLiteUserRepository
UserStatsRepository = SQLiteUserStatsRepository

__all__ = [
    "AuditLogRepository",
    "DEFAULT_DATABASE_PATH",
    "InteractionRepository",
    "JamRepository",
    "PlanRepository",
    "PlaylistRepository",
    "ReviewRepository",
    "SCHEMA_PATH",
    "SQLiteAuditLogRepository",
    "SQLiteInteractionRepository",
    "SQLiteJamRepository",
    "SQLitePlanRepository",
    "SQLitePlaylistRepository",
    "SQLiteReviewRepository",
    "SQLiteTrackRepository",
    "SQLiteUserRepository",
    "SQLiteUserStatsRepository",
    "TrackRepository",
    "UserRepository",
    "UserStatsRepository",
    "create_connection",
    "transaction",
]
