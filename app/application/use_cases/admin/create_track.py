"""Use case for creating a new catalog track from the admin console."""

import logging
from dataclasses import dataclass

from app.domain.exceptions import (
    BusinessRuleViolationError,
    DuplicateEntityError,
    ExternalServiceError,
)
from app.domain.models.track import Track
lazy from app.application.dtos.admin_dtos import (
    AdminCatalogTrackResult,
    CreateTrackCommand,
)
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.services.catalog_source import TrackCatalogFilePort


def _optional_stripped(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


@dataclass(slots=True, frozen=True)
class CreateTrackUseCase:
    """Validates, persists, and syncs a new catalog track created by an admin."""

    track_repo: TrackRepositoryPort
    catalog_file_port: TrackCatalogFilePort | None = None

    def _validate_command(
        self, command: CreateTrackCommand
    ) -> tuple[str, str, str, str | None]:
        title = command.title.strip()
        artist = command.artist.strip()
        genre = command.genre.strip()
        if not title or not artist or not genre:
            raise BusinessRuleViolationError(
                "Track title, artist, and genre must not be blank."
            )
        if command.duration_seconds <= 0:
            raise BusinessRuleViolationError("Track duration must be positive.")
        return title, artist, genre, _optional_stripped(command.spotify_id)

    def _ensure_unique(self, title: str, artist: str, spotify_id: str | None) -> None:
        if spotify_id and self.track_repo.find_by_spotify_id(spotify_id) is not None:
            raise DuplicateEntityError(
                f"Track with spotify_id '{spotify_id}' already exists."
            )
        if self.track_repo.find_by_title_and_artist(title, artist) is not None:
            raise DuplicateEntityError(f"Track '{title}' by '{artist}' already exists.")

    def _write_delta(self, saved: Track) -> None:
        if self.catalog_file_port is None:
            return
        try:
            self.catalog_file_port.write_track_delta(
                title=saved.title,
                artist=saved.artist,
                preview_url=saved.itunes_preview_url,
                genre=saved.genre,
                cover_url=saved.cover_url,
                spotify_id=saved.spotify_id,
                album=saved.album,
                duration_seconds=saved.duration_seconds,
                country=saved.country,
                release_year=saved.release_year,
                explicit=saved.explicit,
                is_deleted=saved.is_deleted,
                created_at=saved.created_at.isoformat() if saved.created_at else None,
            )
        except ExternalServiceError as exc:
            logging.getLogger(__name__).warning(
                "Failed to write track delta for track %s: %s",
                saved.track_id,
                exc,
                extra={
                    "event": "catalog.delta_write.failed",
                    "status": "warning",
                    "track_id": saved.track_id,
                },
            )

    def execute(self, command: CreateTrackCommand) -> AdminCatalogTrackResult:
        title, artist, genre, spotify_id = self._validate_command(command)
        self._ensure_unique(title, artist, spotify_id)

        track = Track(
            title=title,
            artist=artist,
            genre=genre,
            duration_seconds=command.duration_seconds,
            album=_optional_stripped(command.album),
            country=_optional_stripped(command.country),
            release_year=command.release_year,
            cover_url=_optional_stripped(command.cover_url),
            itunes_preview_url=_optional_stripped(command.itunes_preview_url),
            spotify_id=spotify_id,
            explicit=command.explicit,
        )
        saved = self.track_repo.save(track)
        self._write_delta(saved)

        return AdminCatalogTrackResult(
            track_id=saved.track_id or 0,
            title=saved.title,
            artist=saved.artist,
            duration_seconds=saved.duration_seconds,
            genre=saved.genre,
            spotify_id=saved.spotify_id,
            album=saved.album,
            country=saved.country,
            release_year=saved.release_year,
            cover_url=saved.cover_url,
            itunes_preview_url=saved.itunes_preview_url,
            explicit=saved.explicit,
            is_deleted=saved.is_deleted,
        )


__all__ = ["CreateTrackUseCase"]
