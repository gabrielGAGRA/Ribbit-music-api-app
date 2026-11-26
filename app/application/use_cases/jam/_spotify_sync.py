"""Best-effort sync of Pond (Jam) queue actions to the pond owner's Spotify queue."""

import logging
from typing import TYPE_CHECKING

from app.application.use_cases.spotify.premium_guard import execute_with_spotify_premium
from app.domain.exceptions import ExternalServiceError, PermissionDeniedError
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.application.ports.services.music_service import TrackCatalogPort
lazy from app.application.ports.services.spotify import SpotifyHostQueuePort
lazy from app.domain.models.jam import Jam
lazy from app.domain.models.track import Track
lazy from app.domain.models.user import User

if TYPE_CHECKING:
    from collections.abc import Callable

_logger = logging.getLogger(__name__)


def _track_spotify_uri(track: Track | None) -> str | None:
    if track is None or not track.spotify_id:
        return None
    cleaned = track.spotify_id.strip()
    if not cleaned:
        return None
    return (
        cleaned if cleaned.startswith("spotify:track:") else f"spotify:track:{cleaned}"
    )


def _resolve_track_uri(
    track: Track | None,
    track_repo: TrackRepositoryPort | None = None,
    track_catalog: TrackCatalogPort | None = None,
) -> str | None:
    existing = _track_spotify_uri(track)
    if existing is not None:
        return existing
    if track is None or track_catalog is None:
        return None
    query = f"{track.title} {track.artist}".strip()
    if not query:
        return None
    try:
        matches = track_catalog.search_tracks(query, limit=1)
    except ExternalServiceError as exc:
        _logger.warning(
            "Spotify track lookup skipped for track_id=%s (%s): %s",
            track.track_id,
            query,
            exc,
        )
        return None
    if not matches or not matches[0].external_id:
        return None
    resolved_id = str(matches[0].external_id).strip()
    if not resolved_id:
        return None
    if track_repo is not None and track.merge_missing_metadata(spotify_id=resolved_id):
        try:
            track_repo.save(track)
        except Exception:
            _logger.debug(
                "Could not persist resolved spotify_id=%s for track_id=%s",
                resolved_id,
                track.track_id,
                exc_info=True,
            )
    return (
        resolved_id
        if resolved_id.startswith("spotify:track:")
        else f"spotify:track:{resolved_id}"
    )


def _run_for_host(
    spotify_queue: SpotifyHostQueuePort | None,
    user_repo: UserRepositoryPort | None,
    jam: Jam,
    action: Callable[[User], None],
) -> None:
    if spotify_queue is None or user_repo is None:
        return
    host_user = user_repo.find_by_id(jam.host_user_id)
    if host_user is None or not (
        host_user.spotify_refresh_token or host_user.spotify_access_token
    ):
        return
    try:
        execute_with_spotify_premium(
            user_repo,
            host_user,
            lambda: action(host_user),
        )
    except PermissionDeniedError:
        raise
    except ExternalServiceError as exc:
        _logger.warning(
            "Spotify pond queue sync skipped for jam_id=%s: %s",
            jam.jam_id,
            exc,
            extra={
                "event": "spotify.queue_sync.skipped",
                "status": "warning",
                "jam_id": jam.jam_id,
            },
        )


def sync_enqueue_track(
    spotify_queue: SpotifyHostQueuePort | None,
    user_repo: UserRepositoryPort | None,
    jam: Jam,
    track: Track,
    track_repo: TrackRepositoryPort | None = None,
    track_catalog: TrackCatalogPort | None = None,
) -> None:
    """Queues a newly added pond track onto the pond owner's Spotify queue."""
    if spotify_queue is None:
        return
    uri = _resolve_track_uri(
        track,
        track_repo=track_repo,
        track_catalog=track_catalog,
    )
    if uri is None:
        return
    _run_for_host(
        spotify_queue,
        user_repo,
        jam,
        lambda host: spotify_queue.enqueue_track(host, uri),
    )


def sync_advance_track(
    spotify_queue: SpotifyHostQueuePort | None,
    user_repo: UserRepositoryPort | None,
    jam: Jam,
    track_repo: TrackRepositoryPort | None,
    winning_track_id: int | None,
    track_catalog: TrackCatalogPort | None = None,
) -> None:
    """Advances the pond owner's Spotify playback when pond playback moves forward."""
    if spotify_queue is None:
        return
    uri: str | None = None
    if winning_track_id is not None and track_repo is not None:
        uri = _resolve_track_uri(
            track_repo.find_by_id(winning_track_id),
            track_repo=track_repo,
            track_catalog=track_catalog,
        )

    def _advance(host: User) -> None:
        if uri is not None:
            spotify_queue.start_track(host, uri)
        else:
            spotify_queue.skip_to_next(host)

    _run_for_host(spotify_queue, user_repo, jam, _advance)
