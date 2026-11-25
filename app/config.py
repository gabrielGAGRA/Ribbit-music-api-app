"""Configuration settings for the Ribbit application."""

import contextlib
import json
import os
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

_DEFAULT_DEV_SECRET_KEY = "ribbit-insecure-dev-secret-key-change-me-32chars"  # noqa: S105
_DEFAULT_DEV_ADMIN_PASSWORD = "RibbitLocal2026!"  # noqa: S105
_DEFAULT_ADMIN_ELIGIBLE_EMAILS = ("admin@ribbit.example.com",)
_DEFAULT_GCS_MAX_INGEST_TRACKS: int | None = None


def _extract_client_id_from_payload(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    for section_key in ("web", "installed"):
        section = payload.get(section_key)
        if isinstance(section, dict):
            nested = section.get("client_id")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    key = "oauth_client_id" if payload.get("type") == "service_account" else "client_id"
    direct = payload.get(key)
    return direct.strip() if isinstance(direct, str) and direct.strip() else None


def _load_json_payload(path_raw: str | None) -> dict[str, object] | None:
    if not path_raw or not path_raw.strip():
        return None
    path = Path(path_raw.strip())
    if not path.is_file():
        return None
    with contextlib.suppress(OSError, json.JSONDecodeError, TypeError, ValueError):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    return None


def _extract_oauth_section(payload: dict[str, object] | None) -> dict[str, object]:
    if not payload:
        return {}
    for section_key in ("web", "installed"):
        section = payload.get(section_key)
        if isinstance(section, dict):
            return section
    return payload


def _resolve_oauth_file_payload() -> dict[str, object]:
    explicit_file = os.getenv("GOOGLE_OAUTH_CLIENT_FILE")
    if explicit_file:
        data = _load_json_payload(explicit_file)
        if data:
            return _extract_oauth_section(data)

    sa_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if sa_creds:
        data = _load_json_payload(sa_creds)
        if data and any(k in data for k in ("web", "installed")):
            return _extract_oauth_section(data)

    return {}


def _resolve_google_oauth_settings() -> tuple[
    str | None, str | None, str | None, str, str, str
]:
    oauth_section = _resolve_oauth_file_payload()

    explicit_client_id = (os.getenv("GOOGLE_CLIENT_ID") or "").strip() or None
    file_client_id_raw = oauth_section.get("client_id")
    file_client_id = (
        str(file_client_id_raw).strip()
        if isinstance(file_client_id_raw, str) and file_client_id_raw.strip()
        else None
    )

    sa_client_id: str | None = None
    if not explicit_client_id and not file_client_id:
        creds_raw = (os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or "").strip()
        if creds_raw:
            payload = _load_json_payload(creds_raw)
            sa_client_id = _extract_client_id_from_payload(payload)

    client_id = explicit_client_id or file_client_id or sa_client_id

    explicit_secret = (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip() or None
    file_secret_raw = oauth_section.get("client_secret")
    file_secret = (
        str(file_secret_raw).strip()
        if isinstance(file_secret_raw, str) and file_secret_raw.strip()
        else None
    )
    client_secret = explicit_secret or file_secret

    explicit_redirect = (os.getenv("GOOGLE_REDIRECT_URI") or "").strip() or None
    file_redirects = oauth_section.get("redirect_uris")
    file_redirect = (
        file_redirects[0].strip()
        if isinstance(file_redirects, list)
        and file_redirects
        and isinstance(file_redirects[0], str)
        and file_redirects[0].strip()
        else None
    )
    default_redirect = (
        "http://localhost:4200/api/auth/google/callback"
        if (client_id and client_secret)
        else None
    )
    redirect_uri = explicit_redirect or file_redirect or default_redirect

    explicit_auth_uri = (os.getenv("GOOGLE_AUTH_URI") or "").strip() or None
    file_auth_uri = str(oauth_section.get("auth_uri") or "").strip() or None
    auth_uri = (
        explicit_auth_uri
        or file_auth_uri
        or "https://accounts.google.com/o/oauth2/auth"
    )

    explicit_token_uri = (os.getenv("GOOGLE_TOKEN_URI") or "").strip() or None
    file_token_uri = str(oauth_section.get("token_uri") or "").strip() or None
    token_uri = (
        explicit_token_uri or file_token_uri or "https://oauth2.googleapis.com/token"
    )

    frontend_redirect = (os.getenv("GOOGLE_FRONTEND_REDIRECT_URL") or "").strip() or "/"

    return (
        client_id,
        client_secret,
        redirect_uri,
        auth_uri,
        token_uri,
        frontend_redirect,
    )


def _parse_optional_positive_int(raw: str | None, default: int | None) -> int | None:
    if raw is None or not raw.strip():
        return default
    with contextlib.suppress(ValueError):
        parsed = int(raw.strip())
        return parsed if parsed > 0 else None
    return default


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
    secret_key: str = _DEFAULT_DEV_SECRET_KEY
    token_expiration_seconds: int = 43200
    admin_email: str = "admin@ribbit.example.com"
    admin_password: str = _DEFAULT_DEV_ADMIN_PASSWORD
    admin_eligible_emails: tuple[str, ...] = _DEFAULT_ADMIN_ELIGIBLE_EMAILS
    gcs_bucket_name: str | None = None
    gcs_tracks_file_path: str = "Songs/tracks.parquet"
    gcs_max_ingest_tracks: int | None = _DEFAULT_GCS_MAX_INGEST_TRACKS
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None
    google_auth_uri: str = "https://accounts.google.com/o/oauth2/auth"
    google_token_uri: str = "https://oauth2.googleapis.com/token"  # noqa: S105
    google_frontend_redirect_url: str = "/"
    firestore_enabled: bool = False
    gcp_project_id: str | None = None
    firestore_database: str = "(default)"

    @model_validator(mode="after")
    def _validate_production_secret_key(self) -> Self:  # noqa: N804
        if self.environment.lower() == "production" and (
            not self.secret_key or self.secret_key == _DEFAULT_DEV_SECRET_KEY
        ):
            raise RuntimeError("RIBBIT_SECRET_KEY must be configured in production.")
        if self.firestore_enabled and not self.gcp_project_id:
            raise RuntimeError(
                "GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT must be configured "
                "when Firestore synchronization is enabled."
            )
        return self


def _sanitize_storage_emulator_env() -> None:
    """Clears local STORAGE_EMULATOR_HOST when a real GCP service account file is present."""
    emulator_host = (os.getenv("STORAGE_EMULATOR_HOST") or "").strip()
    creds_raw = (os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or "").strip()
    if not emulator_host or not creds_raw or not Path(creds_raw).is_file():
        return
    if "localhost:4443" in emulator_host or "127.0.0.1:4443" in emulator_host:
        os.environ.pop("STORAGE_EMULATOR_HOST", None)


def load_settings() -> Settings:
    """Loads configuration settings from environment variables with ergonomic defaults."""
    with contextlib.suppress(ImportError):
        from dotenv import load_dotenv  # noqa: PLC0415

        load_dotenv()
    _sanitize_storage_emulator_env()

    raw_iterations = os.getenv("PASSWORD_HASH_ITERATIONS")
    iterations = (
        int(raw_iterations) if raw_iterations and raw_iterations.isdigit() else 600_000
    )

    db_path = os.getenv("DATABASE_PATH") or "local.db"
    if db_path.startswith("sqlite:///"):
        db_path = db_path.removeprefix("sqlite:///")

    environment = os.getenv("ENVIRONMENT") or "development"
    secret_key = os.getenv("RIBBIT_SECRET_KEY") or _DEFAULT_DEV_SECRET_KEY
    raw_firestore_enabled = os.getenv("FIRESTORE_ENABLED", "").strip().lower()
    if raw_firestore_enabled not in (
        "",
        "1",
        "true",
        "yes",
        "on",
        "0",
        "false",
        "no",
        "off",
    ):
        raise ValueError("FIRESTORE_ENABLED must be a boolean value.")
    firestore_enabled = raw_firestore_enabled in ("1", "true", "yes", "on")
    gcp_project_id = (
        os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT") or ""
    ).strip() or None
    if gcp_project_id is None:
        credentials = _load_json_payload(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
        raw_project_id = credentials.get("project_id") if credentials else None
        if isinstance(raw_project_id, str) and raw_project_id.strip():
            gcp_project_id = raw_project_id.strip()

    raw_token_exp = os.getenv("TOKEN_EXPIRATION_SECONDS")
    token_expiration = (
        int(raw_token_exp) if raw_token_exp and raw_token_exp.isdigit() else 43200
    )

    admin_email = os.getenv("RIBBIT_ADMIN_EMAIL") or "admin@ribbit.example.com"
    admin_password = os.getenv("RIBBIT_ADMIN_PASSWORD") or _DEFAULT_DEV_ADMIN_PASSWORD
    raw_eligible = os.getenv("RIBBIT_ADMIN_ELIGIBLE_EMAILS")
    admin_eligible_emails = (
        tuple(e.strip().lower() for e in raw_eligible.split(",") if e.strip())
        if raw_eligible
        else _DEFAULT_ADMIN_ELIGIBLE_EMAILS
    )

    (
        google_client_id,
        google_client_secret,
        google_redirect_uri,
        google_auth_uri,
        google_token_uri,
        google_frontend_redirect_url,
    ) = _resolve_google_oauth_settings()

    settings = Settings(
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
        admin_eligible_emails=admin_eligible_emails,
        gcs_bucket_name=os.getenv("GCS_BUCKET_NAME") or None,
        gcs_tracks_file_path=os.getenv("GCS_TRACKS_FILE_PATH", "Songs/tracks.parquet"),
        gcs_max_ingest_tracks=_parse_optional_positive_int(
            os.getenv("GCS_MAX_INGEST_TRACKS"),
            _DEFAULT_GCS_MAX_INGEST_TRACKS,
        ),
        google_client_id=google_client_id,
        google_client_secret=google_client_secret,
        google_redirect_uri=google_redirect_uri,
        google_auth_uri=google_auth_uri,
        google_token_uri=google_token_uri,
        google_frontend_redirect_url=google_frontend_redirect_url,
        firestore_enabled=firestore_enabled,
        gcp_project_id=gcp_project_id,
        firestore_database=os.getenv("FIRESTORE_DATABASE", "(default)").strip()
        or "(default)",
    )
    if environment.lower() == "production" and not settings.firestore_enabled:
        raise RuntimeError("FIRESTORE_ENABLED must be true in production.")
    return settings


__all__ = ["Settings", "load_settings"]
