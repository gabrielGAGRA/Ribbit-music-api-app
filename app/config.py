"""Configuration settings for the Ribbit application."""

import contextlib
import os
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator


class Settings(BaseModel):
    """Configuration settings data model containing fields only."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    database_path: str = "local.db"
    password_hash_iterations: int = 600_000
    spotify_client_id: str | None = None
    spotify_client_secret: str | None = None
    spotify_redirect_uri: str | None = None
    spotify_refresh_token: str | None = None
    app_title: str = "Ribbit Platform API"
    app_description: str = (
        "Backend V0 with Hexagonal Architecture for Track Discovery and"
        " Collaborative Jams"
    )
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"
    secret_key: str = "ribbit-insecure-dev-secret-key-change-me-32chars"  # noqa: S105
    token_expiration_seconds: int = 43200
    admin_email: str = "admin@ribbit.example.com"
    admin_password: str = "RibbitLocal2026!"  # noqa: S105
    gcs_bucket_name: str | None = None
    gcs_tracks_file_path: str = "Songs/songs_final.parquet"

    @model_validator(mode="after")
    def _validate_production_secret_key(self) -> Self:  # noqa: N804
        if self.environment.lower() == "production" and (
            not self.secret_key
            or self.secret_key == "ribbit-insecure-dev-secret-key-change-me-32chars"  # noqa: S105
        ):
            raise RuntimeError("RIBBIT_SECRET_KEY must be configured in production.")
        return self


def load_settings() -> Settings:
    """Loads configuration settings from environment variables with ergonomic defaults."""
    with contextlib.suppress(ImportError):
        from dotenv import load_dotenv  # noqa: PLC0415

        load_dotenv()

    raw_iterations = os.getenv("PASSWORD_HASH_ITERATIONS")

    iterations = (
        int(raw_iterations) if raw_iterations and raw_iterations.isdigit() else 600_000
    )

    db_path = os.getenv("DATABASE_PATH") or os.getenv("DATABASE_URL") or "local.db"
    if db_path.startswith("sqlite:///"):
        db_path = db_path.removeprefix("sqlite:///")

    environment = os.getenv("ENVIRONMENT") or os.getenv("RIBBIT_ENV") or "development"

    secret_key = (
        os.getenv("RIBBIT_SECRET_KEY")
        or os.getenv("SECRET_KEY")
        or "ribbit-insecure-dev-secret-key-change-me-32chars"  # noqa: S105
    )

    if environment.lower() == "production" and (
        not secret_key
        or secret_key == "ribbit-insecure-dev-secret-key-change-me-32chars"  # noqa: S105
    ):
        raise RuntimeError("RIBBIT_SECRET_KEY must be configured in production.")

    raw_token_exp = os.getenv("TOKEN_EXPIRATION_SECONDS")
    token_expiration = (
        int(raw_token_exp) if raw_token_exp and raw_token_exp.isdigit() else 43200
    )

    admin_email = (
        os.getenv("RIBBIT_ADMIN_EMAIL")
        or os.getenv("ADMIN_EMAIL")
        or "admin@ribbit.example.com"
    )
    admin_password = (
        os.getenv("RIBBIT_ADMIN_PASSWORD")
        or os.getenv("ADMIN_PASSWORD")
        or "RibbitLocal2026!"  # noqa: S105
    )

    return Settings(
        database_path=db_path,
        password_hash_iterations=iterations,
        spotify_client_id=os.getenv("SPOTIFY_CLIENT_ID") or None,
        spotify_client_secret=os.getenv("SPOTIFY_CLIENT_SECRET") or None,
        spotify_redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI") or None,
        spotify_refresh_token=os.getenv("SPOTIFY_REFRESH_TOKEN") or None,
        app_title=os.getenv("APP_TITLE", "Ribbit Platform API"),
        app_description=os.getenv(
            "APP_DESCRIPTION",
            "Backend V0 with Hexagonal Architecture for Track Discovery and"
            " Collaborative Jams",
        ),
        app_version=os.getenv("APP_VERSION", "0.1.0"),
        environment=environment,
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        secret_key=secret_key,
        token_expiration_seconds=token_expiration,
        admin_email=admin_email,
        admin_password=admin_password,
        gcs_bucket_name=os.getenv("GCS_BUCKET_NAME") or None,
        gcs_tracks_file_path=os.getenv(
            "GCS_TRACKS_FILE_PATH", "Songs/songs_final.parquet"
        ),
    )


__all__ = ["Settings", "load_settings"]
