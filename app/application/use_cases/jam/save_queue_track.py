"""Use case for saving a Jam queue track to user's liked tracks and optionally a playlist."""

from dataclasses import dataclass

from app.application.dtos.jam_dtos import SaveQueueTrackCommand
from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    PermissionDeniedError,
)
from app.domain.models.interaction import Interaction, InteractionAction
lazy from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
lazy from app.application.ports.repositories.jam_repository import JamRepositoryPort
lazy from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.track import Track


@dataclass(slots=True, frozen=True)
class SaveQueueTrackUseCase:
    """Saves a track from the Jam queue to user's favorites and optionally into a playlist."""

    jam_repo: JamRepositoryPort
    user_repo: UserRepositoryPort
    track_repo: TrackRepositoryPort
    interaction_repo: InteractionRepositoryPort
    playlist_repo: PlaylistRepositoryPort | None = None

    def _resolve_params(
        self,
        command_or_jam_id: SaveQueueTrackCommand | int,
        user_id: int | None,
        track_id: int | None,
        playlist_id: int | None,
    ) -> tuple[int, int, int, int | None]:
        if isinstance(command_or_jam_id, SaveQueueTrackCommand):
            return (
                command_or_jam_id.jam_id,
                command_or_jam_id.user_id,
                command_or_jam_id.track_id,
                command_or_jam_id.playlist_id,
            )
        if user_id is None or track_id is None:
            raise ValueError(
                "user_id and track_id must be provided when passing jam_id directly."
            )
        return command_or_jam_id, user_id, track_id, playlist_id

    def _save_to_playlist(self, playlist_id: int, user_id: int, track: Track) -> None:
        if self.playlist_repo is None:
            return
        playlist = self.playlist_repo.find_by_id(playlist_id)
        if not playlist:
            raise EntityNotFoundError("Playlist not found.")
        if not playlist.is_owned_by(user_id):
            raise PermissionDeniedError(
                "Access denied: playlist does not belong to this user."
            )
        playlist.add_track(track)
        self.playlist_repo.save(playlist)

    def execute(
        self,
        command_or_jam_id: SaveQueueTrackCommand | int,
        user_id: int | None = None,
        track_id: int | None = None,
        playlist_id: int | None = None,
    ) -> bool:
        jam_id, eff_user_id, eff_track_id, eff_pl_id = self._resolve_params(
            command_or_jam_id, user_id, track_id, playlist_id
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
                raise PermissionDeniedError("User is not a participant in this Jam.")

        tracks_in_session = {item.track_id for item in self.jam_repo.list_queue(jam_id)}
        if jam.current_track_id is not None:
            tracks_in_session.add(jam.current_track_id)

        if eff_track_id not in tracks_in_session:
            raise EntityNotFoundError("Track does not belong to this Jam room queue.")

        track = self.track_repo.find_by_id(eff_track_id)
        if not track or track.is_deleted:
            raise EntityNotFoundError("Track not found or inactive.")

        if not user.can_listen(track):
            raise BusinessRuleViolationError(
                "Track is blocked for underage users or violates genre preferences."
            )

        if eff_pl_id is not None:
            self._save_to_playlist(eff_pl_id, eff_user_id, track)

        self.interaction_repo.save(
            Interaction(
                user_id=eff_user_id,
                track_id=eff_track_id,
                action=InteractionAction.SUPERLIKE,
            )
        )
        return True
