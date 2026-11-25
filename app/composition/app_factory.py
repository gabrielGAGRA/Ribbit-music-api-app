"""FastAPI application factory, lifespan management, and startup sync helpers."""

import logging
import threading
from contextlib import asynccontextmanager
lazy import sqlite3
lazy from collections.abc import AsyncGenerator

from fastapi import FastAPI

from app.application.use_cases.admin import (
    IngestTracksFromCatalogUseCase,
    SyncCatalogVersionUseCase,
)
from app.composition.container import Container, build_container
from app.config import Settings, load_settings
from app.domain.exceptions import ExternalServiceError
from app.infrastructure.repositories import (
    SQLiteAuditLogRepository,
    SQLiteTrackRepository,
    create_connection,
)
from app.infrastructure.repositories.seed import seed_database
from app.infrastructure.telemetry import configure_logging, log_operational_event
from app.presentation.exception_handlers import register_exception_handlers
from app.presentation.middleware import CorrelationIdMiddleware
from app.presentation.routers.admin import router as admin_router
from app.presentation.routers.auth import router as auth_router
from app.presentation.routers.discovery import router as discovery_router
from app.presentation.routers.jams import router as jams_router
from app.presentation.routers.playlists import router as playlists_router
from app.presentation.routers.profile import router as profile_router
from app.presentation.routers.spotify import router as spotify_router
from app.presentation.routers.tracks_reviews import router as tracks_reviews_router
lazy from app.application.ports.repositories import AuditLogRepositoryPort


def _mount_presentation_routers(app: FastAPI) -> None:
    """Mounts all presentation-layer routers individually."""
    for router in [
        auth_router,
        discovery_router,
        playlists_router,
        profile_router,
        jams_router,
        tracks_reviews_router,
        admin_router,
        spotify_router,
    ]:
        app.include_router(router)


def sync_catalog_on_first_startup(
    audit_log_repo: AuditLogRepositoryPort,
    sync_use_case: SyncCatalogVersionUseCase | None,
    logger: logging.Logger,
) -> None:
    """Ingests GCS catalog once on initial startup if no catalog sync has succeeded yet."""
    if sync_use_case is None or audit_log_repo.has_successful_catalog_sync():
        return
    try:
        result = sync_use_case.execute()
    except ExternalServiceError as exc:
        log_operational_event(
            logger,
            event="catalog.startup_sync.skipped",
            status="warning",
            message=f"Initial catalog sync skipped: {exc}",
        )
        return
    log_operational_event(
        logger,
        event="catalog.startup_sync.completed",
        status="success",
        message=result.message,
        synced=result.synced,
        version=result.version,
    )


def _start_background_catalog_sync(
    settings: Settings, container: Container, logger: logging.Logger
) -> threading.Thread | None:
    """Runs initial catalog sync in a background daemon thread so startup stays instant."""
    if (
        container.sync_catalog_version_use_case is None
        or container.catalog_file_port is None
        or container.audit_log_repo.has_successful_catalog_sync()
    ):
        return None

    catalog_adapter = container.catalog_file_port

    def _worker() -> None:
        conn = create_connection(settings.database_path)
        try:
            audit_log_repo = SQLiteAuditLogRepository(conn)
            sync_uc = SyncCatalogVersionUseCase(
                catalog_file_port=catalog_adapter,
                ingest_use_case=IngestTracksFromCatalogUseCase(
                    track_repo=SQLiteTrackRepository(conn),
                    catalog_file_port=catalog_adapter,
                ),
                audit_log_repo=audit_log_repo,
            )
            sync_catalog_on_first_startup(audit_log_repo, sync_uc, logger)
        finally:
            conn.close()

    thread = threading.Thread(
        target=_worker, name="gcs-initial-catalog-sync", daemon=True
    )
    thread.start()
    return thread


def create_app(
    settings: Settings | None = None,
    connection: sqlite3.Connection | None = None,
) -> FastAPI:
    """Application factory building FastAPI app with Hexagonal composition root."""
    resolved_settings = settings or load_settings()
    configure_logging(level=resolved_settings.log_level)
    owns_connection = connection is None
    container = build_container(resolved_settings, connection=connection)
    seed_database(
        container.connection,
        settings=resolved_settings,
        password_hasher=container.password_hasher,
    )
    catalog_sync_thread: threading.Thread | None = None

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        nonlocal catalog_sync_thread
        logger = logging.getLogger("app")
        log_operational_event(
            logger,
            event="service.startup",
            status="success",
            message=(
                f"Starting service: {resolved_settings.app_title} "
                f"v{resolved_settings.app_version}"
            ),
            app_title=resolved_settings.app_title,
            app_version=resolved_settings.app_version,
            environment=resolved_settings.environment,
        )
        if container.firestore_sync_service is not None:
            container.firestore_sync_service.sync_all()
        if owns_connection:
            catalog_sync_thread = _start_background_catalog_sync(
                resolved_settings, container, logger
            )
        try:
            yield
        finally:
            log_operational_event(
                logger,
                event="service.shutdown",
                status="success",
                message=f"Shutting down service: {resolved_settings.app_title}",
            )
            if owns_connection:
                if catalog_sync_thread is not None and catalog_sync_thread.is_alive():
                    catalog_sync_thread.join(timeout=5.0)
                container.connection.close()
            container.http_session.close()

    app = FastAPI(
        title=resolved_settings.app_title,
        description=resolved_settings.app_description,
        version=resolved_settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(CorrelationIdMiddleware)
    app.state.container = container

    register_exception_handlers(app)
    _mount_presentation_routers(app)

    @app.get("/", tags=["Status"])
    def root() -> dict[str, str]:
        return {"status": "online", "app": resolved_settings.app_title}

    @app.get("/health", tags=["Status"])
    def health() -> dict[str, str]:
        return {"status": "healthy"}

    return app


__all__ = ["create_app", "sync_catalog_on_first_startup"]
