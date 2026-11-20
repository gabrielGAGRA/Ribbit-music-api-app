"""Persistence ports for domain aggregates and entities."""

from app.application.ports.repositories.audit_log_repository import (
    AuditLogRepositoryPort,
)
from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
from app.application.ports.repositories.jam_repository import JamRepositoryPort
from app.application.ports.repositories.plan_repository import PlanRepositoryPort
from app.application.ports.repositories.platform_cost_repository import (
    PlatformCostRepositoryPort,
)
from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
from app.application.ports.repositories.review_repository import (
    ReviewRepositoryPort,
)
from app.application.ports.repositories.track_access_repository import (
    TrackAccessRepositoryPort,
)
from app.application.ports.repositories.track_repository import (
    TrackRepositoryPort,
)
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.ports.repositories.user_stats_repository import (
    UserStatsRepositoryPort,
)

__all__ = [
    "AuditLogRepositoryPort",
    "InteractionRepositoryPort",
    "JamRepositoryPort",
    "PlanRepositoryPort",
    "PlatformCostRepositoryPort",
    "PlaylistRepositoryPort",
    "ReviewRepositoryPort",
    "TrackAccessRepositoryPort",
    "TrackRepositoryPort",
    "UserRepositoryPort",
    "UserStatsRepositoryPort",
]
