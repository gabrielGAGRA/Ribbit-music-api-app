"""Use case for upvoting or adding a track to a Jam queue."""

from dataclasses import dataclass

from app.application.use_cases.jam._spotify_sync import sync_enqueue_track
from app.application.use_cases.spotify.premium_guard import require_spotify_premium
from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    PermissionDeniedError,
)
from app.domain.models.interaction import (
    Interaction,
    InteractionAction,
    InteractionSource,
)
from app.domain.models.jam import JamQueueItem
lazy from app.application.dtos.jam_dtos import VoteJamTrackCommand
lazy from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
lazy from app.application.ports.repositories.jam_repository import JamRepositoryPort
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.application.ports.services.spotify import SpotifyHostQueuePort
lazy from app.domain.models.jam import Jam
lazy from app.domain.models.track import Track


@dataclass(slots=True, frozen=True)
class VoteJamTrackUseCase:
    """Adds a track or votes points on a Jam track, enforcing limits and auto-advancing."""

    jam_repo: JamRepositoryPort
    user_repo: UserRepositoryPort
    track_repo: TrackRepositoryPort
    interaction_repo: InteractionRepositoryPort | None = None
    spotify_queue: SpotifyHostQueuePort | None = None

    def _compute_vote_points(self, command: VoteJamTrackCommand) -> tuple[int, bool]:
        action = InteractionAction.parse(command.action, default=InteractionAction.LIKE)
        is_superlike = action == InteractionAction.SUPERLIKE or command.points >= 2
        vote_points = (
            2 if is_superlike else (command.points if command.points == 1 else 1)
        )
        return vote_points, is_superlike

    def _check_duration_cap(self, jam: Jam, track: Track) -> None:
        if jam.jam_id is None:
            raise EntityNotFoundError("Jam ID is missing.")
        queued_duration = 0
        raw_queue = self.jam_repo.list_queue(jam.jam_id)
        if raw_queue and isinstance(raw_queue, list):
            for item in raw_queue:
                t = self.track_repo.find_by_id(item.track_id)
                if t:
                    queued_duration += t.duration_seconds

        if jam.current_track_id is not None:
            curr_t = self.track_repo.find_by_id(jam.current_track_id)
            if curr_t:
                queued_duration += curr_t.duration_seconds

        max_allowed_seconds = jam.duration_minutes * 60
        total_seconds = (
            jam.accumulated_duration_seconds + queued_duration + track.duration_seconds
        )
        if total_seconds > max_allowed_seconds:
            raise BusinessRuleViolationError(
                "Track addition exceeds configured jam duration."
            )

    def _save_vote(
        self, jam_id: int, track_id: int, vote_points: int
    ) -> tuple[JamQueueItem, bool]:
        existing_item = self.jam_repo.find_queue_item(jam_id, track_id)
        if existing_item is not None:
            existing_item.vote(vote_points)
            return self.jam_repo.save_queue_item(existing_item), False

        new_item = JamQueueItem(
            jam_id=jam_id,
            track_id=track_id,
            initial_vote_points=vote_points,
        )
        return self.jam_repo.save_queue_item(new_item), True

    def _record_interaction(
        self,
        jam_id: int,
        user_id: int,
        track_id: int,
        action: str | InteractionAction | None,
        *,
        is_superlike: bool = False,
    ) -> None:
        if self.interaction_repo is None:
            return

        interaction_action = (
            InteractionAction.SUPERLIKE
            if is_superlike
            else InteractionAction.parse(action, default=InteractionAction.LIKE)
        )

        existing = (
            self.interaction_repo.find_by_user_and_track(user_id, track_id)
            if hasattr(self.interaction_repo, "find_by_user_and_track")
            else None
        )
        if isinstance(existing, Interaction):
            if existing.is_positive:
                if not interaction_action.is_positive:
                    return
                if (
                    interaction_action == InteractionAction.SUPERLIKE
                    and existing.action != InteractionAction.SUPERLIKE
                ):
                    existing.change_action(InteractionAction.SUPERLIKE)
                    self.interaction_repo.save(existing)
                return

            if interaction_action.is_positive:
                existing.change_action(interaction_action)
                self.interaction_repo.save(existing)
                return
            return

        self.interaction_repo.save(
            Interaction(
                user_id=user_id,
                track_id=track_id,
                action=interaction_action,
                source=InteractionSource.JAM,
                jam_id=jam_id,
            )
        )

    def _maybe_auto_advance(self, jam: Jam) -> None:
        if jam.current_track_id is not None or jam.jam_id is None:
            return
        queue = self.jam_repo.list_queue(jam.jam_id)
        if queue and isinstance(queue, list) and len(queue) > 0:
            champion = queue[0]
            jam.current_track_id = champion.track_id
            self.jam_repo.remove_track_from_queue(jam.jam_id, champion.track_id)
            self.jam_repo.save(jam)

    def execute(self, command: VoteJamTrackCommand) -> JamQueueItem:
        user = self.user_repo.find_by_id(command.user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {command.user_id} not found.")
        require_spotify_premium(user)

        jam = self.jam_repo.find_by_id(command.jam_id)
        if not jam or not jam.is_active:
            raise EntityNotFoundError("Jam room not found or inactive.")

        if hasattr(self.jam_repo, "is_participant"):
            is_participant = self.jam_repo.is_participant(
                command.jam_id, command.user_id
            )
            if not is_participant and jam.host_user_id != command.user_id:
                raise PermissionDeniedError("Must join Jam room before interacting.")

        track = self.track_repo.find_by_id(command.track_id)
        if not track or track.is_deleted:
            raise EntityNotFoundError("Track not found or inactive.")

        if not user.can_listen(track):
            raise BusinessRuleViolationError(
                "Track is blocked for underage users or violates genre preferences."
            )

        vote_points, is_superlike = self._compute_vote_points(command)
        if is_superlike and jam.superlikes_used >= jam.max_superlikes:
            raise BusinessRuleViolationError(
                "Superlike limit reached for this Jam session."
            )

        self._check_duration_cap(jam, track)

        saved_item, is_new_item = self._save_vote(
            command.jam_id, command.track_id, vote_points
        )
        self._record_interaction(
            command.jam_id,
            command.user_id,
            command.track_id,
            command.action,
            is_superlike=is_superlike,
        )

        if is_superlike:
            jam.superlikes_used += 1
            self.jam_repo.save(jam)

        self._maybe_auto_advance(jam)
        if is_new_item:
            sync_enqueue_track(self.spotify_queue, self.user_repo, jam, track)
        return saved_item
