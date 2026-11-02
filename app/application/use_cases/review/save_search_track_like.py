"""Use case for saving liked search tracks into interactions and playlists."""

from dataclasses import dataclass

from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    ForbiddenError,
)
from app.domain.models.interaction import Interaction, InteractionAction
lazy from app.application.dtos.review_dtos import SaveSearchTrackLikeCommand
lazy from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
lazy from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.track import Track


@dataclass(slots=True, frozen=True)
class SaveSearchTrackLikeUseCase:
    """Saves a track like from search into interactions and optionally into a playlist."""

    user_repo: UserRepositoryPort
    track_repo: TrackRepositoryPort
    interaction_repo: InteractionRepositoryPort
    playlist_repo: PlaylistRepositoryPort | None = None

    def _resolve_args(
        self,
        user_id_or_cmd: int | SaveSearchTrackLikeCommand,
        track_id: int | None,
        playlist_id: int | None,
    ) -> tuple[int, int, int | None]:
        if isinstance(user_id_or_cmd, SaveSearchTrackLikeCommand):
            return (
                user_id_or_cmd.user_id,
                user_id_or_cmd.track_id,
                user_id_or_cmd.playlist_id,
            )
        if track_id is None:
            raise ValueError("track_id must be provided when passing user_id.")
        return user_id_or_cmd, track_id, playlist_id

    def _add_to_playlist(self, user_id: int, playlist_id: int, track: Track) -> None:
        if self.playlist_repo is None:
            raise BusinessRuleViolationError("Playlist repository is not configured.")
        playlist = self.playlist_repo.find_by_id(playlist_id)
        if not playlist:
            raise EntityNotFoundError("Playlist não encontrada.")
        if not playlist.is_owned_by(user_id):
            raise ForbiddenError("A playlist não pertence a este usuário.")
        if track.track_id is None or all(
            existing.track_id != track.track_id for existing in playlist.tracks
        ):
            playlist.add_track(track)
            self.playlist_repo.save(playlist)

    def execute(
        self,
        user_id_or_cmd: int | SaveSearchTrackLikeCommand,
        track_id: int | None = None,
        playlist_id: int | None = None,
    ) -> bool:
        uid, tid, pid = self._resolve_args(user_id_or_cmd, track_id, playlist_id)

        user = self.user_repo.find_by_id(uid)
        if not user:
            raise EntityNotFoundError(f"User with ID {uid} not found.")

        track = self.track_repo.find_by_id(tid)
        if not track or track.is_deleted:
            raise EntityNotFoundError("Música não encontrada ou inativa.")

        if user.is_minor() and track.explicit:
            raise BusinessRuleViolationError(
                "Música bloqueada para usuários menores de idade."
            )

        if pid is not None:
            self._add_to_playlist(uid, pid, track)

        interaction = Interaction(
            user_id=uid,
            track_id=tid,
            action=InteractionAction.LIKE,
        )
        self.interaction_repo.save(interaction)
        return True


__all__ = ["SaveSearchTrackLikeUseCase"]
