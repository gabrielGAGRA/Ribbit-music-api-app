"""Use case for registering a skip vote on a Jam track or downvoting a queued track."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.application.dtos.jam_dtos import SkipVoteResult, VoteSkipJamTrackCommand
from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    PermissionDeniedError,
)
lazy from app.application.ports.repositories.jam_repository import JamRepositoryPort
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort

if TYPE_CHECKING:
    from app.domain.models.jam import Jam


@dataclass(slots=True, frozen=True)
class VoteSkipJamTrackUseCase:
    """Registers a participant skip vote on current playback or decrements queue points."""

    jam_repo: JamRepositoryPort
    user_repo: UserRepositoryPort
    track_repo: TrackRepositoryPort

    def _advance(self, jam: Jam) -> bool:
        if jam.jam_id is None:
            raise EntityNotFoundError("Jam ID is missing.")
        prev_id = jam.current_track_id
        if prev_id:
            prev_track = self.track_repo.find_by_id(prev_id)
            if prev_track:
                jam.accumulated_duration_seconds += prev_track.duration_seconds
            self.jam_repo.clear_skip_votes(jam.jam_id, prev_id)

        max_seconds = jam.duration_minutes * 60
        if jam.accumulated_duration_seconds >= max_seconds:
            jam.is_active = False
            jam.current_track_id = None
            self.jam_repo.save(jam)
            return True

        queue = self.jam_repo.list_queue(jam.jam_id)
        if not queue:
            jam.current_track_id = None
            self.jam_repo.save(jam)
            return True

        winner = queue[0]
        jam.current_track_id = winner.track_id
        self.jam_repo.remove_track_from_queue(jam.jam_id, winner.track_id)
        self.jam_repo.save(jam)
        return True

    def _resolve_params(
        self,
        command_or_jam_id: VoteSkipJamTrackCommand | int,
        user_id: int | None,
        track_id: int | None,
    ) -> tuple[int, int, int | None]:
        if isinstance(command_or_jam_id, VoteSkipJamTrackCommand):
            return (
                command_or_jam_id.jam_id,
                command_or_jam_id.user_id,
                command_or_jam_id.track_id,
            )
        if user_id is None:
            raise ValueError("user_id must be provided when passing jam_id directly.")
        return command_or_jam_id, user_id, track_id

    def _downvote_queue(self, jam_id: int, track_id: int | None, user: Any) -> Any:
        if track_id is None:
            raise BusinessRuleViolationError("No track currently playing to skip.")
        track = self.track_repo.find_by_id(track_id)
        if not track or track.is_deleted:
            raise EntityNotFoundError("Track not found or inactive.")
        if not user.can_listen(track):
            raise BusinessRuleViolationError(
                "Track is blocked for underage users or violates genre preferences."
            )
        item = self.jam_repo.find_queue_item(jam_id, track_id)
        if not item:
            raise EntityNotFoundError("Track is not currently in the jam queue.")
        item.vote(-1)
        return self.jam_repo.save_queue_item(item)

    def _skip_current_track(
        self, jam: Jam, active_id: int, target_id: int | None, user: Any, user_id: int
    ) -> SkipVoteResult:
        if target_id is not None and target_id != active_id:
            raise BusinessRuleViolationError("The vote must be on the current track.")

        active_track = self.track_repo.find_by_id(active_id)
        if not active_track or active_track.is_deleted:
            raise EntityNotFoundError("Active track not found or inactive.")
        if not user.can_listen(active_track):
            raise BusinessRuleViolationError(
                "Track is blocked for underage users or violates genre preferences."
            )

        if jam.jam_id is None:
            raise EntityNotFoundError("Jam ID is missing.")
        jam_id = jam.jam_id
        self.jam_repo.record_skip_vote(jam_id, active_id, user_id)
        votes = self.jam_repo.count_skip_votes(jam_id, active_id)
        advanced = votes >= jam.skip_votes_threshold
        if advanced:
            self._advance(jam)
            updated = self.jam_repo.find_by_id(jam_id)
            if updated:
                jam = updated

        return SkipVoteResult(
            jam_id=jam_id,
            track_id=active_id,
            votes=votes,
            threshold=jam.skip_votes_threshold,
            advanced=advanced,
            is_active=jam.is_active,
            success=True,
        )

    def execute(
        self,
        command_or_jam_id: VoteSkipJamTrackCommand | int,
        user_id: int | None = None,
        track_id: int | None = None,
    ) -> Any:
        jam_id, eff_user_id, tgt_track_id = self._resolve_params(
            command_or_jam_id, user_id, track_id
        )

        user = self.user_repo.find_by_id(eff_user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {eff_user_id} not found.")

        jam = self.jam_repo.find_by_id(jam_id)
        if not jam or not jam.is_active:
            raise EntityNotFoundError("Jam room not found or inactive.")

        if hasattr(self.jam_repo, "is_participant"):
            is_participant = self.jam_repo.is_participant(jam_id, eff_user_id)
            if not is_participant and jam.host_user_id != eff_user_id:
                raise PermissionDeniedError("Participant only.")

        if jam.current_track_id is None:
            return self._downvote_queue(jam_id, tgt_track_id, user)

        return self._skip_current_track(
            jam, jam.current_track_id, tgt_track_id, user, eff_user_id
        )
