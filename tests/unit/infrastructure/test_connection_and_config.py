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


def test_load_settings_defaults_and_env_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in (
        "PASSWORD_HASH_ITERATIONS",
        "DATABASE_PATH",
        "DATABASE_URL",
        "SPOTIFY_CLIENT_ID",
        "APP_TITLE",
        "APP_VERSION",
        "ENVIRONMENT",
        "LOG_LEVEL",
    ):
        monkeypatch.delenv(key, raising=False)

    default_settings = load_settings()
    assert default_settings.database_path == "local.db"
    assert default_settings.password_hash_iterations == 600_000
    assert default_settings.spotify_client_id is None
    assert default_settings.app_title == "Ribbit Platform API"
    assert default_settings.environment == "development"

    monkeypatch.setenv("DATABASE_URL", "sqlite:///custom_test.db")
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


def test_load_settings_invalid_iterations_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PASSWORD_HASH_ITERATIONS", "not_a_number")
    settings = load_settings()
    assert settings.password_hash_iterations == 600_000


def test_build_container_wires_all_use_cases_and_supports_getattr_shorthand() -> None:
    conn = create_connection(":memory:")
    try:
        settings = Settings(database_path=":memory:", password_hash_iterations=1_000)
        container = build_container(settings=settings, connection=conn)

        assert container.connection is conn
        assert container.register_user is container.register_user_use_case
        assert container.authenticate_user is container.authenticate_user_use_case
        assert container.get_jam_state is container.get_jam_state_use_case

        with pytest.raises(AttributeError):
            _ = container.non_existent_component
    finally:
        conn.close()


def test_build_container_creates_connection_when_not_provided() -> None:
    settings = Settings(database_path=":memory:", password_hash_iterations=1_000)
    container = build_container(settings=settings, connection=None)
    try:
        assert container.connection is not None
        fk_status = container.connection.execute("PRAGMA foreign_keys;").fetchone()[0]
        assert fk_status == 1
    finally:
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
        settings = Settings(database_path=":memory:", app_title="Ribbit External Conn")
        app = create_app(settings=settings, connection=conn)

        async with app.router.lifespan_context(app):
            assert app.state.connection is conn

        # Connection must still be usable after lifespan exits when passed externally
        cursor = conn.execute("SELECT 1")
        assert cursor.fetchone()[0] == 1
    finally:
        app_logger.setLevel(prev_level)
        app_logger.propagate = prev_propagate
        app_logger.handlers = prev_handlers
        conn.close()
