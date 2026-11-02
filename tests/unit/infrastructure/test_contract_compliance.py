"""Contract compliance tests verifying all concrete adapters implement their ports."""

import sqlite3

from app.application.ports.repositories import (
    AuditLogRepositoryPort,
    InteractionRepositoryPort,
    JamRepositoryPort,
    PlanRepositoryPort,
    PlaylistRepositoryPort,
    ReviewRepositoryPort,
    TrackRepositoryPort,
    UserRepositoryPort,
)
from app.application.ports.services import (
    PasswordHasherPort,
    PlaylistExportPort,
    TrackCatalogPort,
    TrackPreviewPort,
)
from app.infrastructure.adapters import ITunesAdapter, SpotifyAdapter
from app.infrastructure.repositories import (
    AuditLogRepository,
    InteractionRepository,
    JamRepository,
    PlanRepository,
    PlaylistRepository,
    ReviewRepository,
    SQLiteAuditLogRepository,
    SQLiteInteractionRepository,
    SQLiteJamRepository,
    SQLitePlanRepository,
    SQLitePlaylistRepository,
    SQLiteReviewRepository,
    SQLiteTrackRepository,
    SQLiteUserRepository,
    TrackRepository,
    UserRepository,
)
from app.infrastructure.security import PBKDF2PasswordHasher


def test_repository_contract_compliance() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        user_repo = UserRepository(conn)
        assert isinstance(user_repo, UserRepositoryPort)
        assert isinstance(SQLiteUserRepository(conn), UserRepositoryPort)

        plan_repo = PlanRepository(conn)
        assert isinstance(plan_repo, PlanRepositoryPort)
        assert isinstance(SQLitePlanRepository(conn), PlanRepositoryPort)

        track_repo = TrackRepository(conn)
        assert isinstance(track_repo, TrackRepositoryPort)
        assert isinstance(SQLiteTrackRepository(conn), TrackRepositoryPort)

        jam_repo = JamRepository(conn)
        assert isinstance(jam_repo, JamRepositoryPort)
        assert isinstance(SQLiteJamRepository(conn), JamRepositoryPort)

        playlist_repo = PlaylistRepository(conn)
        assert isinstance(playlist_repo, PlaylistRepositoryPort)
        assert isinstance(SQLitePlaylistRepository(conn), PlaylistRepositoryPort)

        interaction_repo = InteractionRepository(conn)
        assert isinstance(interaction_repo, InteractionRepositoryPort)
        assert isinstance(SQLiteInteractionRepository(conn), InteractionRepositoryPort)

        review_repo = ReviewRepository(conn)
        assert isinstance(review_repo, ReviewRepositoryPort)
        assert isinstance(SQLiteReviewRepository(conn), ReviewRepositoryPort)

        audit_repo = AuditLogRepository(conn)
        assert isinstance(audit_repo, AuditLogRepositoryPort)
        assert isinstance(SQLiteAuditLogRepository(conn), AuditLogRepositoryPort)
    finally:
        conn.close()


def test_service_contract_compliance() -> None:
    hasher = PBKDF2PasswordHasher()
    assert isinstance(hasher, PasswordHasherPort)

    spotify = SpotifyAdapter()
    assert isinstance(spotify, TrackCatalogPort)
    assert isinstance(spotify, PlaylistExportPort)

    itunes = ITunesAdapter()
    assert isinstance(itunes, TrackPreviewPort)
