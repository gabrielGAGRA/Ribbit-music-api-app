"""Unit tests for database connection management, configuration settings, and composition root."""

import logging
import sqlite3

import pytest

from app.composition import build_container, create_app
from app.config import Settings, load_settings
from app.infrastructure.repositories.connection import (
    SCHEMA_PATH,
    create_connection,
    transaction,
)


def test_create_connection_enables_foreign_keys_and_row_factory() -> None:
    conn = create_connection(":memory:")
    try:
        assert conn.row_factory is sqlite3.Row
        fk_status = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
        assert fk_status == 1
    finally:
        conn.close()


def test_transaction_context_manager_commits_on_success() -> None:
    conn = create_connection(":memory:")
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        with transaction(conn) as cursor:
            cursor.execute(
                "INSERT INTO plans (name, monthly_price, max_profiles) VALUES (?, ?, ?)",
                ("Pro", 19.99, 2),
            )
        row = conn.execute("SELECT * FROM plans WHERE name = 'Pro'").fetchone()
        assert row is not None
        assert float(row["monthly_price"]) == 19.99
    finally:
        conn.close()


def test_transaction_context_manager_rolls_back_on_error() -> None:
    conn = create_connection(":memory:")
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        with pytest.raises(RuntimeError, match="Simulated failure"):
            with transaction(conn) as cursor:
                cursor.execute(
                    "INSERT INTO plans (name, monthly_price, max_profiles) VALUES (?, ?, ?)",
                    ("RollbackPlan", 9.99, 1),
                )
                raise RuntimeError("Simulated failure")

        row = conn.execute("SELECT * FROM plans WHERE name = 'RollbackPlan'").fetchone()
        assert row is None
    finally:
        conn.close()


def test_nested_transaction_rollback_preserves_outer_transaction() -> None:
    conn = create_connection(":memory:")
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        with transaction(conn) as cursor:
            cursor.execute(
                "INSERT INTO plans (name, monthly_price, max_profiles) VALUES (?, ?, ?)",
                ("OuterPlan", 1.0, 1),
            )
            with pytest.raises(RuntimeError, match="Nested failure"):
                with transaction(conn) as nested_cursor:
                    nested_cursor.execute(
                        "INSERT INTO plans (name, monthly_price, max_profiles) VALUES (?, ?, ?)",
                        ("NestedPlan", 2.0, 1),
                    )
                    raise RuntimeError("Nested failure")
            cursor.execute(
                "INSERT INTO plans (name, monthly_price, max_profiles) VALUES (?, ?, ?)",
                ("OuterPlanTwo", 3.0, 1),
            )

        names = [
            row["name"]
            for row in conn.execute(
                "SELECT name FROM plans WHERE name LIKE 'OuterPlan%' ORDER BY name"
            ).fetchall()
        ]
        assert names == ["OuterPlan", "OuterPlanTwo"]
        assert (
            conn.execute("SELECT 1 FROM plans WHERE name = 'NestedPlan'").fetchone()
            is None
        )
    finally:
        conn.close()


def test_load_settings_defaults_and_env_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)
    for key in (
        "PASSWORD_HASH_ITERATIONS",
        "DATABASE_PATH",
        "SPOTIFY_CLIENT_ID",
        "APP_TITLE",
        "APP_VERSION",
        "ENVIRONMENT",
        "LOG_LEVEL",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "FIRESTORE_ENABLED",
        "GCP_PROJECT_ID",
        "GOOGLE_CLOUD_PROJECT",
    ):
        monkeypatch.delenv(key, raising=False)

    default_settings = load_settings()
    assert default_settings.database_path == "local.db"
    assert default_settings.password_hash_iterations == 600_000
    assert default_settings.spotify_client_id is None
    assert default_settings.app_title == "Ribbit Platform API"
    assert default_settings.environment == "development"
    assert default_settings.firestore_enabled is False

    monkeypatch.setenv("DATABASE_PATH", "custom_test.db")
    monkeypatch.setenv("PASSWORD_HASH_ITERATIONS", "15000")
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "sp_client")
    monkeypatch.setenv("APP_TITLE", "Custom Ribbit")
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    custom_settings = load_settings()
    assert custom_settings.database_path == "custom_test.db"
    assert custom_settings.password_hash_iterations == 15_000
    assert custom_settings.spotify_client_id == "sp_client"
    assert custom_settings.app_title == "Custom Ribbit"
    assert custom_settings.environment == "staging"
    assert custom_settings.log_level == "DEBUG"


def test_load_settings_enables_firestore_only_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FIRESTORE_ENABLED", "true")
    monkeypatch.setenv("GCP_PROJECT_ID", "ribbit-test-project")

    settings = load_settings()

    assert settings.firestore_enabled is True
    assert settings.gcp_project_id == "ribbit-test-project"
    assert settings.firestore_database == "(default)"


def test_production_settings_require_firestore_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("RIBBIT_SECRET_KEY", "p" * 40)
    monkeypatch.delenv("FIRESTORE_ENABLED", raising=False)
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

    with pytest.raises(RuntimeError, match="FIRESTORE_ENABLED"):
        load_settings()


def test_firestore_enabled_requires_project_id() -> None:
    with pytest.raises(RuntimeError, match="GCP_PROJECT_ID"):
        Settings(firestore_enabled=True)


def test_load_settings_invalid_iterations_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PASSWORD_HASH_ITERATIONS", "not_a_number")
    settings = load_settings()
    assert settings.password_hash_iterations == 600_000


def test_build_container_wires_all_use_cases() -> None:
    conn = create_connection(":memory:")
    try:
        settings = Settings(database_path=":memory:", password_hash_iterations=1_000)
        container = build_container(settings=settings, connection=conn)

        assert container.connection is conn
        assert container.http_session is not None
        assert container.register_user_use_case is not None
        assert container.authenticate_user_use_case is not None
        assert container.get_jam_state_use_case is not None

        with pytest.raises(AttributeError):
            _ = container.register_user  # type: ignore[attr-defined]
        with pytest.raises(AttributeError):
            _ = container.non_existent_component  # type: ignore[attr-defined]
    finally:
        container.http_session.close()
        conn.close()


def test_build_container_creates_connection_when_not_provided() -> None:
    settings = Settings(database_path=":memory:", password_hash_iterations=1_000)
    container = build_container(settings=settings, connection=None)
    try:
        assert container.connection is not None
        fk_status = container.connection.execute("PRAGMA foreign_keys;").fetchone()[0]
        assert fk_status == 1
    finally:
        container.http_session.close()
        container.connection.close()


@pytest.mark.anyio
async def test_create_app_with_external_connection_does_not_close_it_on_shutdown() -> (
    None
):
    conn = create_connection(":memory:")
    app_logger = logging.getLogger("app")
    prev_level = app_logger.level
    prev_propagate = app_logger.propagate
    prev_handlers = list(app_logger.handlers)
    try:
        settings = Settings(
            database_path=":memory:",
            app_title="Ribbit External Conn",
            password_hash_iterations=1_000,
        )
        app = create_app(settings=settings, connection=conn)

        async with app.router.lifespan_context(app):
            assert app.state.container.connection is conn
            assert not hasattr(app.state, "connection")
            assert not hasattr(app.state, "settings")

        # Connection must still be usable after lifespan exits when passed externally
        cursor = conn.execute("SELECT 1")
        assert cursor.fetchone()[0] == 1
    finally:
        app_logger.setLevel(prev_level)
        app_logger.propagate = prev_propagate
        app_logger.handlers = prev_handlers
        conn.close()


def test_sync_catalog_on_first_startup_runs_only_before_first_sync() -> None:
    from unittest.mock import MagicMock

    from app.application.use_cases.admin.sync_catalog_version import (
        SyncCatalogVersionResult,
    )
    from app.composition.app_factory import sync_catalog_on_first_startup
    from app.infrastructure.repositories import SQLiteAuditLogRepository
    from app.infrastructure.repositories.seed import seed_database

    conn = create_connection(":memory:")
    try:
        seed_database(conn)
        audit_log_repo = SQLiteAuditLogRepository(conn)
        sync_uc = MagicMock()
        sync_uc.execute.return_value = SyncCatalogVersionResult(
            synced=True, version=1, message="Local catalog updated to version 1."
        )
        logger = logging.getLogger("test_startup_sync")

        sync_catalog_on_first_startup(audit_log_repo, sync_uc, logger)
        sync_uc.execute.assert_called_once_with()
        assert audit_log_repo.has_successful_catalog_sync() is False

        audit_log_repo.log_event(
            event="catalog.synced.v1",
            status="success",
        )
        assert audit_log_repo.has_successful_catalog_sync() is True

        sync_uc.reset_mock()
        sync_catalog_on_first_startup(audit_log_repo, sync_uc, logger)
        sync_uc.execute.assert_not_called()
    finally:
        conn.close()


def test_sync_catalog_on_first_startup_skips_gracefully_on_external_error() -> None:
    from unittest.mock import MagicMock

    from app.composition.app_factory import sync_catalog_on_first_startup
    from app.domain.exceptions import ExternalServiceError
    from app.infrastructure.repositories import SQLiteAuditLogRepository
    from app.infrastructure.repositories.seed import seed_database

    conn = create_connection(":memory:")
    try:
        seed_database(conn)
        audit_log_repo = SQLiteAuditLogRepository(conn)
        sync_uc = MagicMock()
        sync_uc.execute.side_effect = ExternalServiceError(
            "No GCS credentials", service_name="GCP_GCS"
        )
        logger = logging.getLogger("test_startup_sync")

        sync_catalog_on_first_startup(audit_log_repo, sync_uc, logger)
        sync_uc.execute.assert_called_once_with()
    finally:
        conn.close()


def test_load_settings_resolves_google_client_id_from_credentials_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    import json
    from pathlib import Path

    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_FILE", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GOOGLE_REDIRECT_URI", raising=False)
    monkeypatch.delenv("GCS_MAX_INGEST_TRACKS", raising=False)

    sa_creds_path = Path(str(tmp_path)) / "sa_creds.json"
    sa_creds_path.write_text(
        json.dumps(
            {
                "type": "service_account",
                "client_id": "108921521849256271018",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(sa_creds_path))

    sa_settings = load_settings()
    assert sa_settings.google_client_id is None
    assert sa_settings.gcs_max_ingest_tracks == 50_000

    oauth_creds_path = Path(str(tmp_path)) / "oauth_creds.json"
    oauth_creds_path.write_text(
        json.dumps({"web": {"client_id": "web-id.apps.googleusercontent.com"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(oauth_creds_path))
    oauth_settings = load_settings()
    assert oauth_settings.google_client_id == "web-id.apps.googleusercontent.com"

    monkeypatch.setenv(
        "GOOGLE_CLIENT_ID", "explicit-oauth-id.apps.googleusercontent.com"
    )
    monkeypatch.setenv("GCS_MAX_INGEST_TRACKS", "0")
    override = load_settings()
    assert override.google_client_id == "explicit-oauth-id.apps.googleusercontent.com"
    assert override.gcs_max_ingest_tracks is None


def test_load_settings_resolves_google_oauth_from_client_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    import json
    from pathlib import Path

    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GOOGLE_REDIRECT_URI", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

    oauth_file = Path(str(tmp_path)) / "client_secret.json"
    oauth_file.write_text(
        json.dumps(
            {
                "web": {
                    "client_id": "test-oauth-id.apps.googleusercontent.com",
                    "client_secret": "test-oauth-secret",
                    "project_id": "test-project-123",
                    "auth_uri": "https://accounts.google.com/o/oauth2/custom-auth",
                    "token_uri": "https://oauth2.googleapis.com/custom-token",
                    "redirect_uris": ["http://localhost:4200/custom/callback"],
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_FILE", str(oauth_file))

    settings = load_settings()
    assert settings.google_client_id == "test-oauth-id.apps.googleusercontent.com"
    assert settings.google_client_secret == "test-oauth-secret"
    assert settings.google_redirect_uri == "http://localhost:4200/custom/callback"
    assert (
        settings.google_auth_uri == "https://accounts.google.com/o/oauth2/custom-auth"
    )
    assert settings.google_token_uri == "https://oauth2.googleapis.com/custom-token"

    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost:4200/override/callback")
    override_settings = load_settings()
    assert (
        override_settings.google_redirect_uri
        == "http://localhost:4200/override/callback"
    )


def test_load_settings_clears_localhost_emulator_when_service_account_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    import os
    from pathlib import Path

    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)
    creds_file = Path(str(tmp_path)) / "gcp_credentials.json"
    creds_file.write_text('{"type": "service_account"}', encoding="utf-8")

    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(creds_file))
    monkeypatch.setenv("STORAGE_EMULATOR_HOST", "http://localhost:4443")

    load_settings()
    assert os.getenv("STORAGE_EMULATOR_HOST") is None

    monkeypatch.setenv("STORAGE_EMULATOR_HOST", "http://gcs-emulator:4443")
    load_settings()
    assert os.getenv("STORAGE_EMULATOR_HOST") == "http://gcs-emulator:4443"
