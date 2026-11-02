"""Use case for ingesting music catalog tracks from an external file source."""

from dataclasses import dataclass

from app.domain.models.track import Track
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.services.catalog_source import (
    CatalogSourceTrack,
    TrackCatalogFilePort,
)


@dataclass(slots=True, frozen=True, kw_only=True)
class IngestTracksResult:
    """Summary of tracks ingestion execution."""

    total_processed: int
    inserted: int
    updated: int


@dataclass(slots=True, frozen=True)
class IngestTracksFromCatalogUseCase:
    """Coordinates fetching and upserting catalog tracks from external file storage."""

    track_repo: TrackRepositoryPort
    catalog_file_port: TrackCatalogFilePort

    def execute(self) -> IngestTracksResult:
        source_tracks = self.catalog_file_port.fetch_tracks()
        inserted_count = 0
        updated_count = 0

        for item in source_tracks:
            existing = self._find_existing(item)
            if existing is None:
                self._insert_new_track(item)
                inserted_count += 1
            elif self._update_track_metadata(existing, item):
                self.track_repo.save(existing)
                updated_count += 1

        return IngestTracksResult(
            total_processed=len(source_tracks),
            inserted=inserted_count,
            updated=updated_count,
        )

    def _find_existing(self, item: CatalogSourceTrack) -> Track | None:
        if item.spotify_id:
            found = self.track_repo.find_by_spotify_id(item.spotify_id)
            if found is not None:
                return found
        return self.track_repo.find_by_title_and_artist(item.title, item.artist)

    def _insert_new_track(self, item: CatalogSourceTrack) -> Track:
        new_track = Track(
            title=item.title,
            artist=item.artist,
            duration_seconds=item.duration_seconds,
            genre=item.genre or "",
            album=item.album,
            country=item.country,
            release_year=item.release_year,
            cover_url=item.cover_url,
            spotify_id=item.spotify_id,
            itunes_preview_url=item.itunes_preview_url,
            explicit=item.explicit,
        )
        return self.track_repo.save(new_track)

    def _update_track_metadata(self, existing: Track, item: CatalogSourceTrack) -> bool:
        changed = False
        if not existing.cover_url and item.cover_url:
            existing.cover_url = item.cover_url
            changed = True
        if not existing.album and item.album:
            existing.album = item.album
            changed = True
        if existing.release_year is None and item.release_year is not None:
            existing.release_year = item.release_year
            changed = True
        if not existing.country and item.country:
            existing.country = item.country
            changed = True
        if not existing.itunes_preview_url and item.itunes_preview_url:
            existing.itunes_preview_url = item.itunes_preview_url
            changed = True
        if not existing.genre and item.genre:
            existing.genre = item.genre
            changed = True
        if not existing.spotify_id and item.spotify_id:
            existing.spotify_id = item.spotify_id
            changed = True
        return changed


__all__ = ["IngestTracksFromCatalogUseCase", "IngestTracksResult"]
