"""Use case for retrieving current Jam state, queue, and playback."""

from dataclasses import dataclass

from app.application.dtos.jam_dtos import JamStateResult
from app.domain.exceptions import EntityNotFoundError
lazy from app.application.ports.repositories.jam_repository import JamRepositoryPort
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.jam import JamQueueItem


@dataclass(slots=True, frozen=True)
class GetJamStateUseCase:
    """Returns room state, currently playing track, skip votes count, and ordered queue."""

    jam_repo: JamRepositoryPort
    user_repo: UserRepositoryPort
    track_repo: TrackRepositoryPort

    def execute(self, jam_id: int, user_id: int) -> JamStateResult:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        jam = self.jam_repo.find_by_id(jam_id)
        if not jam:
            raise EntityNotFoundError(f"Jam session {jam_id} not found.")

        raw_queue = self.jam_repo.list_queue(jam_id)
        track_ids: list[int] = [item.track_id for item in raw_queue]
        if jam.current_track_id is not None:
            track_ids.append(jam.current_track_id)

        tracks_by_id = self.track_repo.find_by_ids(track_ids)

        current_track_domain = (
            tracks_by_id.get(jam.current_track_id)
            if jam.current_track_id is not None
            else None
        )

        queue_items: list[JamQueueItem] = []
        for item in raw_queue:
            track = tracks_by_id.get(item.track_id)
            if not track or track.is_deleted:
                continue
            if not user.can_listen(track):
                continue
            queue_items.append(item)

        current_track = None
        if (
            current_track_domain
            and not current_track_domain.is_deleted
            and user.can_listen(current_track_domain)
        ):
            current_track = current_track_domain

        skip_votes = 0
        if jam.current_track_id and hasattr(self.jam_repo, "count_skip_votes"):
            skip_votes = self.jam_repo.count_skip_votes(jam_id, jam.current_track_id)

        return JamStateResult(
            jam=jam,
            current_track=current_track,
            queue=queue_items,
            skip_votes=skip_votes,
        )
