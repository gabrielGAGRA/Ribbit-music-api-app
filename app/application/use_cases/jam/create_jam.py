"""Use case for creating a collaborative Jam session."""

from dataclasses import dataclass

from app.domain.exceptions import (
    BusinessRuleViolationError,
    EntityNotFoundError,
    PermissionDeniedError,
)
from app.domain.models.jam import Jam
lazy from app.application.dtos.jam_dtos import CreateJamCommand
lazy from app.application.ports.repositories.jam_repository import JamRepositoryPort
lazy from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort


@dataclass(slots=True, frozen=True)
class CreateJamUseCase:
    """Creates a new collaborative Jam session with a 6-digit room code and adds the host."""

    jam_repo: JamRepositoryPort
    user_repo: UserRepositoryPort
    playlist_repo: PlaylistRepositoryPort | None = None

    def execute(self, command: CreateJamCommand) -> Jam:
        host = self.user_repo.find_by_id(command.host_user_id)
        if not host:
            raise EntityNotFoundError(f"Host user {command.host_user_id} not found.")

        deck_source = (command.deck_source or "livre").strip().lower()
        if deck_source not in ("livre", "curtidas", "playlist"):
            raise BusinessRuleViolationError(
                "Deck source must be 'livre', 'curtidas', or 'playlist'."
            )

        if deck_source == "playlist":
            if command.source_playlist_id is None:
                raise BusinessRuleViolationError(
                    "Source playlist ID must be provided when deck source is 'playlist'."
                )
            if self.playlist_repo is not None:
                playlist = self.playlist_repo.find_by_id(command.source_playlist_id)
                if not playlist or not playlist.is_owned_by(command.host_user_id):
                    raise PermissionDeniedError(
                        "Source playlist does not exist or does not belong to the host."
                    )

        jam = Jam.create(
            host_user_id=command.host_user_id,
            room_name=command.room_name.strip(),
            duration_minutes=command.duration_minutes,
            max_superlikes=command.max_superlikes,
            skip_votes_threshold=command.skip_votes_threshold,
            deck_source=deck_source,
            source_playlist_id=command.source_playlist_id,
        )
        saved_jam = self.jam_repo.save(jam)
        if saved_jam.jam_id is not None and host.user_id is not None:
            self.jam_repo.add_participant(saved_jam.jam_id, host.user_id)
        return saved_jam
