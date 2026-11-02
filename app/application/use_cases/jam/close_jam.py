"""Use case for closing a collaborative Jam session."""

from dataclasses import dataclass

from app.application.dtos.jam_dtos import CloseJamCommand
from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError
lazy from app.application.ports.repositories.jam_repository import JamRepositoryPort
lazy from app.domain.models.jam import Jam


@dataclass(slots=True, frozen=True)
class CloseJamUseCase:
    """Closes an active Jam session, restricted exclusively to the host user."""

    jam_repo: JamRepositoryPort

    def execute(
        self,
        command_or_jam_id: CloseJamCommand | int,
        host_user_id: int | None = None,
    ) -> Jam:
        if isinstance(command_or_jam_id, CloseJamCommand):
            jam_id = command_or_jam_id.jam_id
            effective_host_id = command_or_jam_id.host_user_id
        else:
            jam_id = command_or_jam_id
            if host_user_id is None:
                raise ValueError(
                    "host_user_id must be provided when passing jam_id directly."
                )
            effective_host_id = host_user_id

        jam = self.jam_repo.find_by_id(jam_id)
        if not jam or not jam.is_active:
            raise EntityNotFoundError("Jam room not found or inactive.")

        if not jam.is_host(effective_host_id):
            raise PermissionDeniedError("Only the host can close the Jam.")

        jam.is_active = False
        return self.jam_repo.save(jam)
