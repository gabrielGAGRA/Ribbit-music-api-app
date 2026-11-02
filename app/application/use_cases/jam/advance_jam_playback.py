"""Use case for advancing Jam playback to the top-voted queue track."""

from dataclasses import dataclass

from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    PermissionDeniedError,
)
lazy from app.application.ports.repositories.jam_repository import JamRepositoryPort
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.domain.models.jam import Jam


@dataclass(slots=True, frozen=True)
class AdvanceJamPlaybackUseCase:
    """Promotes highest voted queue track to currently playing, updating duration and skip votes."""

    jam_repo: JamRepositoryPort
    track_repo: TrackRepositoryPort | None = None

    def execute(self, jam_id: int, requester_user_id: int | None = None) -> Jam:
        jam = self.jam_repo.find_by_id(jam_id)
        if not jam or not jam.is_active:
            raise EntityNotFoundError("Jam room not found or inactive.")

        if requester_user_id is not None and not jam.is_host(requester_user_id):
            raise PermissionDeniedError("Only the jam host can advance playback.")

        prev_track_id = jam.current_track_id
        if prev_track_id is not None:
            if self.track_repo is not None:
                prev_track = self.track_repo.find_by_id(prev_track_id)
                if prev_track is not None:
                    jam.accumulated_duration_seconds += prev_track.duration_seconds
            if hasattr(self.jam_repo, "clear_skip_votes"):
                self.jam_repo.clear_skip_votes(jam_id, prev_track_id)

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
            return self.jam_repo.advance_playback(
                jam_id=jam_id,
                new_track_id=winning_item.track_id,
                removed_track_id=winning_item.track_id,
            )

        self.jam_repo.remove_track_from_queue(jam_id, winning_item.track_id)
        jam.current_track_id = winning_item.track_id
        return self.jam_repo.save(jam)
