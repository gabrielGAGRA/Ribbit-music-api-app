"""Best-effort sync of Pond (Jam) queue actions to the pond owner's Spotify queue."""

import logging
from typing import TYPE_CHECKING

from app.application.use_cases.spotify.premium_guard import execute_with_spotify_premium
from app.domain.exceptions import SpotifyError, SpotifyPremiumRequiredError
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
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
    except SpotifyPremiumRequiredError:
        raise
    except SpotifyError as exc:
        _logger.warning(
            "Spotify pond queue sync skipped for jam_id=%s: %s",
            jam.jam_id,
            exc,
        )


def sync_enqueue_track(
    spotify_queue: SpotifyHostQueuePort | None,
    user_repo: UserRepositoryPort | None,
    jam: Jam,
    track: Track,
) -> None:
    """Queues a newly added pond track onto the pond owner's Spotify queue."""
    uri = _track_spotify_uri(track)
    if uri is None or spotify_queue is None:
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
) -> None:
    """Advances the pond owner's Spotify playback when pond playback moves forward."""
    if spotify_queue is None:
        return
    uri: str | None = None
    if winning_track_id is not None and track_repo is not None:
        uri = _track_spotify_uri(track_repo.find_by_id(winning_track_id))

    def _advance(host: User) -> None:
        if uri is not None:
            spotify_queue.start_track(host, uri)
        else:
            spotify_queue.skip_to_next(host)

    _run_for_host(spotify_queue, user_repo, jam, _advance)
