"""Use case for retrieving candidate tracks for a Jam deck."""

from dataclasses import dataclass

from app.application.dtos.jam_dtos import GetJamDeckCommand
from app.application.dtos.playlist_dtos import PlaylistDeckResult
from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError
from app.domain.models.interaction import InteractionAction
lazy from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
lazy from app.application.ports.repositories.jam_repository import JamRepositoryPort
lazy from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.jam import Jam
lazy from app.domain.models.track import Track
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True)
class GetJamDeckUseCase:
    """Returns a cursor-paginated page of candidate tracks for Jam participants."""

    jam_repo: JamRepositoryPort
    user_repo: UserRepositoryPort
    track_repo: TrackRepositoryPort
    playlist_repo: PlaylistRepositoryPort | None = None
    interaction_repo: InteractionRepositoryPort | None = None

    def _resolve_params(
        self,
        command_or_jam_id: GetJamDeckCommand | int | None,
        jam_id: int | None,
        user_id: int | None,
        limit: int,
        cursor_id: int | None,
    ) -> tuple[int, int, int, int | None]:
        if isinstance(command_or_jam_id, GetJamDeckCommand):
            return (
                command_or_jam_id.jam_id,
                command_or_jam_id.user_id,
                command_or_jam_id.limit,
                command_or_jam_id.cursor_id,
            )
        if isinstance(command_or_jam_id, int):
            if user_id is None:
                raise ValueError(
                    "user_id must be provided when passing jam_id directly."
                )
            return command_or_jam_id, user_id, limit, cursor_id
        if jam_id is not None:
            if user_id is None:
                raise ValueError(
                    "user_id must be provided when passing jam_id directly."
                )
            return jam_id, user_id, limit, cursor_id
        raise ValueError("jam_id must be provided.")

    def _fetch_candidates(
        self,
        jam: Jam,
        user: User,
        user_id: int,
        excluded_ids: set[int],
    ) -> list[Track]:
        source = (jam.deck_source or "livre").strip().lower()

        if source == "playlist" and jam.source_playlist_id and self.playlist_repo:
            playlist = self.playlist_repo.find_by_id(jam.source_playlist_id)
            return list(playlist.tracks) if playlist else []

        if source == "curtidas" and self.interaction_repo:
            likes = self.interaction_repo.list_by_user(user_id)
            fav_ids = [
                i.track_id
                for i in likes
                if i.action in (InteractionAction.LIKE, InteractionAction.SUPERLIKE)
            ]
            if fav_ids:
                tracks_map = self.track_repo.find_by_ids(fav_ids)
                return [tracks_map[tid] for tid in fav_ids if tid in tracks_map]
            return []

        return self.track_repo.list_active(
            limit=100,
            excluded_genres=list(user.blocked_genres),
            block_explicit=not user.is_adult,
            excluded_ids=list(excluded_ids),
        )

    def execute(
        self,
        command_or_jam_id: GetJamDeckCommand | int | None = None,
        jam_id: int | None = None,
        user_id: int | None = None,
        limit: int = 20,
        cursor_id: int | None = None,
    ) -> PlaylistDeckResult:
        t_jam_id, eff_user_id, page_limit, cursor = self._resolve_params(
            command_or_jam_id, jam_id, user_id, limit, cursor_id
        )

        user = self.user_repo.find_by_id(eff_user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {eff_user_id} not found.")

        jam = self.jam_repo.find_by_id(t_jam_id)
        if not jam or not jam.is_active:
            raise EntityNotFoundError("Jam room not found or inactive.")

        if not self.jam_repo.is_participant(t_jam_id, eff_user_id):
            raise PermissionDeniedError(
                "User must join the Jam room before requesting deck candidates."
            )

        excluded_ids = {item.track_id for item in self.jam_repo.list_queue(t_jam_id)}
        if jam.current_track_id is not None:
            excluded_ids.add(jam.current_track_id)

        if self.interaction_repo is not None:
            rejected = self.interaction_repo.list_by_user(
                eff_user_id, action=InteractionAction.DISLIKE
            )
            excluded_ids.update(i.track_id for i in rejected)

        candidates = self._fetch_candidates(jam, user, eff_user_id, excluded_ids)

        eligible = [
            t
            for t in candidates
            if t.track_id is not None
            and t.track_id not in excluded_ids
            and not t.is_deleted
            and user.can_listen(t)
            and not (cursor is not None and t.track_id <= cursor)
        ]
        eligible.sort(key=lambda t: t.track_id or 0)

        has_more = len(eligible) > page_limit
        items = eligible[:page_limit]
        next_cursor = items[-1].track_id if has_more and items else None

        return PlaylistDeckResult(
            items=items, next_cursor=next_cursor, has_more=has_more
        )
