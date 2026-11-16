"""Configuration settings for the Ribbit application."""

import contextlib
import json
import os
import ssl
import tempfile
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

_DEFAULT_DEV_SECRET_KEY = "ribbit-insecure-dev-secret-key-change-me-32chars"  # noqa: S105
_DEFAULT_DEV_ADMIN_PASSWORD = "RibbitLocal2026!"  # noqa: S105
_DEFAULT_GCS_MAX_INGEST_TRACKS = 50_000


def _atomic_write_ca_bundle(bundle_path: Path, combined: str) -> None:
    existing: str | None = None
    with contextlib.suppress(OSError, UnicodeError, ValueError):
        existing = bundle_path.read_text(encoding="utf-8")
    if existing == combined:
        return
    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=bundle_path.parent,
            prefix="ca_",
            suffix=".tmp",
            delete=False,
        ) as tmp_file:
            tmp_name = tmp_file.name
            tmp_file.write(combined)
        Path(tmp_name).replace(bundle_path)
        tmp_name = None
    finally:
        if tmp_name is not None:
            with contextlib.suppress(OSError):
                Path(tmp_name).unlink(missing_ok=True)


def _configure_system_ca_bundle() -> None:
    """Combines certifi and OS trust-store CAs so requests/google-auth verify HTTPS."""
    if os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE"):
        return
    with contextlib.suppress(
        ImportError, OSError, ssl.SSLError, UnicodeError, ValueError
    ):
        import certifi  # noqa: PLC0415

        ctx = ssl.create_default_context()
        os_certs = sorted(
            {
                ssl.DER_cert_to_PEM_cert(der)
                for der in ctx.get_ca_certs(binary_form=True)
            }
        )
        if not os_certs:
            return
        base_dir = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / ".cache"))
        bundle_dir = base_dir / "ribbit"
        bundle_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        bundle_path = bundle_dir / "ribbit_combined_ca.pem"
        certifi_pem = Path(certifi.where()).read_text(encoding="utf-8")
        combined = certifi_pem.rstrip() + "\n" + "".join(os_certs)
        _atomic_write_ca_bundle(bundle_path, combined)
        os.environ["REQUESTS_CA_BUNDLE"] = str(bundle_path)


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


def _resolve_google_client_id() -> str | None:
    explicit = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
    if explicit:
        return explicit
    creds_raw = (os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or "").strip()
    if not creds_raw:
        return None
    creds_path = Path(creds_raw)
    if not creds_path.is_file():
        return None
    with contextlib.suppress(OSError, json.JSONDecodeError, TypeError, ValueError):
        payload = json.loads(creds_path.read_text(encoding="utf-8"))
        return _extract_client_id_from_payload(payload)
    return None


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
    admin_eligible_emails: tuple[str, ...] = (
        "admin@ribbit.example.com",
        "gabriel.agra@usp.br",
        "fernando.seraco@usp.br",
    )
    gcs_bucket_name: str | None = None
    gcs_tracks_file_path: str = "Songs/songs_final.parquet"
    gcs_max_ingest_tracks: int | None = _DEFAULT_GCS_MAX_INGEST_TRACKS
    google_client_id: str | None = None
    gcp_project_id: str | None = None
    firestore_enabled: bool = False
    firestore_database: str = "(default)"

    @model_validator(mode="after")
    def _validate_production_secret_key(self) -> Self:  # noqa: N804
        if self.environment.lower() == "production" and (
            not self.secret_key or self.secret_key == _DEFAULT_DEV_SECRET_KEY
        ):
            raise RuntimeError("RIBBIT_SECRET_KEY must be configured in production.")
        return self


def _resolve_gcp_project_id() -> str | None:
    env_project = (
        os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT") or ""
    ).strip()
    if env_project:
        return env_project
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_path:
        path = Path(creds_path)
        if path.is_file():
            with contextlib.suppress(Exception):
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("project_id"):
                    return str(data["project_id"]).strip() or None
    return None


def _resolve_firestore_enabled(gcp_project_id: str | None) -> bool:
    raw_fs = os.getenv("FIRESTORE_ENABLED")
    if raw_fs is not None:
        return raw_fs.strip().lower() in ("1", "true", "yes", "on")
    return bool(gcp_project_id)


def load_settings() -> Settings:
    """Loads configuration settings from environment variables with ergonomic defaults."""
    with contextlib.suppress(ImportError):
        from dotenv import load_dotenv  # noqa: PLC0415

        load_dotenv()

    _configure_system_ca_bundle()

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
        or _DEFAULT_DEV_SECRET_KEY
    )

    if environment.lower() == "production" and (
        not secret_key or secret_key == _DEFAULT_DEV_SECRET_KEY
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
        or _DEFAULT_DEV_ADMIN_PASSWORD
    )
    raw_eligible = os.getenv("RIBBIT_ADMIN_ELIGIBLE_EMAILS") or os.getenv(
        "ADMIN_ELIGIBLE_EMAILS"
    )
    if raw_eligible:
        admin_eligible_emails = tuple(
            e.strip().lower() for e in raw_eligible.split(",") if e.strip()
        )
    else:
        admin_eligible_emails = (
            "admin@ribbit.example.com",
            "gabriel.agra@usp.br",
            "fernando.seraco@usp.br",
        )

    gcp_project_id = _resolve_gcp_project_id()

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
        admin_eligible_emails=admin_eligible_emails,
        gcs_bucket_name=os.getenv("GCS_BUCKET_NAME") or None,
        gcs_tracks_file_path=os.getenv(
            "GCS_TRACKS_FILE_PATH", "Songs/songs_final.parquet"
        ),
        gcs_max_ingest_tracks=_parse_optional_positive_int(
            os.getenv("GCS_MAX_INGEST_TRACKS"),
            _DEFAULT_GCS_MAX_INGEST_TRACKS,
        ),
        google_client_id=_resolve_google_client_id(),
        gcp_project_id=gcp_project_id,
        firestore_enabled=_resolve_firestore_enabled(gcp_project_id),
        firestore_database=os.getenv("FIRESTORE_DATABASE", "(default)"),
    )


__all__ = ["Settings", "load_settings"]
