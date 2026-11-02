"""Helpers shared by the Spotify sync use cases."""

from app.domain.models.track import Track
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.services.music_service import CatalogTrack

_MS_PER_SECOND = 1000


def upsert_catalog_track(
    track_repo: TrackRepositoryPort, catalog_track: CatalogTrack, genre: str
) -> Track | None:
    """Saves a provider track, or None when it lacks the data a Track requires.

    Existing tracks only get their provider-owned metadata refreshed, so curated genre
    and explicit flags survive re-syncs. Durations are floored at one second.
    """
    if (
        catalog_track.external_id is None
        or catalog_track.title is None
        or catalog_track.duration_ms is None
    ):
        return None
    spotify_id = str(catalog_track.external_id)
    metadata = {
        "title": catalog_track.title,
        "artist": catalog_track.artist,
        "duration_seconds": max(1, round(catalog_track.duration_ms / _MS_PER_SECOND)),
        "album": catalog_track.album,
        "cover_url": catalog_track.cover_url,
        "release_year": catalog_track.release_year,
    }
    track = track_repo.find_by_spotify_id(spotify_id)
    if track is None:
        track = Track(spotify_id=spotify_id, genre=genre, **metadata)
    else:
        track.refresh_catalog_metadata(**metadata)
    return track_repo.save(track)
