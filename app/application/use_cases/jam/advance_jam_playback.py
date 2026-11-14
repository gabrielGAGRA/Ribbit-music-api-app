"""Use case for advancing Jam playback to the top-voted queue track."""

from dataclasses import dataclass

from app.application.use_cases.jam._spotify_sync import sync_advance_track
from app.application.use_cases.spotify.premium_guard import require_spotify_premium
from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    PermissionDeniedError,
)
lazy from app.application.ports.repositories.jam_repository import JamRepositoryPort
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.application.ports.services.spotify import SpotifyHostQueuePort
lazy from app.domain.models.jam import Jam


@dataclass(slots=True, frozen=True)
class AdvanceJamPlaybackUseCase:
    """Promotes highest voted queue track to currently playing, updating duration and skip votes."""

    jam_repo: JamRepositoryPort
    track_repo: TrackRepositoryPort | None = None
    user_repo: UserRepositoryPort | None = None
    spotify_queue: SpotifyHostQueuePort | None = None

    def execute(self, jam_id: int, requester_user_id: int | None = None) -> Jam:
        self._require_requester_premium(requester_user_id)

        jam = self.jam_repo.find_by_id(jam_id)
        if not jam or not jam.is_active:
            raise EntityNotFoundError("Jam room not found or inactive.")

        if requester_user_id is not None and not jam.is_host(requester_user_id):
            raise PermissionDeniedError("Only the jam host can advance playback.")

        self._record_previous_track_progress(jam, jam_id)

        max_allowed_seconds = jam.duration_minutes * 60
        if jam.accumulated_duration_seconds >= max_allowed_seconds:
            jam.is_active = False
            jam.current_track_id = None
            return self.jam_repo.save(jam)

        queue = self.jam_repo.list_queue(jam_id)
        if not queue:
            raise BusinessRuleViolationError("No tracks in queue to advance.")

        winning_item = queue[0]

        if hasattr(self.jam_repo, "advance_playback"):
            saved_jam = self.jam_repo.advance_playback(
                jam_id=jam_id,
                new_track_id=winning_item.track_id,
                removed_track_id=winning_item.track_id,
            )
            sync_advance_track(
                self.spotify_queue,
                self.user_repo,
                saved_jam,
                self.track_repo,
                winning_item.track_id,
            )
            return saved_jam

        self.jam_repo.remove_track_from_queue(jam_id, winning_item.track_id)
        jam.current_track_id = winning_item.track_id
        saved_jam = self.jam_repo.save(jam)
        sync_advance_track(
            self.spotify_queue,
            self.user_repo,
            saved_jam,
            self.track_repo,
            winning_item.track_id,
        )
        return saved_jam

    def _require_requester_premium(self, requester_user_id: int | None) -> None:
        if requester_user_id is None or self.user_repo is None:
            return
        requester = self.user_repo.find_by_id(requester_user_id)
        if not requester:
            raise EntityNotFoundError(f"User with ID {requester_user_id} not found.")
        require_spotify_premium(requester)

    def _record_previous_track_progress(self, jam: Jam, jam_id: int) -> None:
        prev_track_id = jam.current_track_id
        if prev_track_id is None:
            return
        if self.track_repo is not None:
            prev_track = self.track_repo.find_by_id(prev_track_id)
            if prev_track is not None:
                jam.accumulated_duration_seconds += prev_track.duration_seconds
        if hasattr(self.jam_repo, "clear_skip_votes"):
            self.jam_repo.clear_skip_votes(jam_id, prev_track_id)
