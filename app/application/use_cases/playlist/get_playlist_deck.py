"""Use case for retrieving candidate tracks for a playlist deck."""

from dataclasses import dataclass

from app.application.dtos.playlist_dtos import (
    GetPlaylistDeckCommand,
    PlaylistDeckResult,
)
from app.application.use_cases.playlist.deck_filter_helpers import (
    extract_deck_filters_tuple,
    matches_track_filters,
)
from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError
from app.domain.models.interaction import InteractionAction
lazy from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
lazy from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.playlist import Playlist
lazy from app.domain.models.track import Track
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True)
class GetPlaylistDeckUseCase:
    """Returns a cursor-paginated page of candidate tracks eligible for a deck playlist."""

    user_repo: UserRepositoryPort
    playlist_repo: PlaylistRepositoryPort
    track_repo: TrackRepositoryPort
    interaction_repo: InteractionRepositoryPort | None = None

    def _resolve_params(
        self,
        command_or_playlist_id: GetPlaylistDeckCommand | int | None,
        playlist_id: int | None,
        user_id: int | None,
        limit: int,
        cursor_id: int | None,
    ) -> tuple[int, int, int, int | None]:
        if isinstance(command_or_playlist_id, GetPlaylistDeckCommand):
            return (
                command_or_playlist_id.playlist_id,
                command_or_playlist_id.user_id,
                command_or_playlist_id.limit,
                command_or_playlist_id.cursor_id,
            )
        if isinstance(command_or_playlist_id, int):
            if user_id is None:
                raise ValueError(
                    "user_id must be provided when passing playlist_id directly."
                )
            return command_or_playlist_id, user_id, limit, cursor_id
        if playlist_id is not None:
            if user_id is None:
                raise ValueError(
                    "user_id must be provided when passing playlist_id directly."
                )
            return playlist_id, user_id, limit, cursor_id
        raise ValueError("playlist_id must be provided.")

    def _is_track_eligible(
        self,
        track: Track,
        user: User,
        excluded_ids: set[int],
        remaining_duration: int | None,
        genre_filter: list[str] | None,
        year_filter: list[int] | None,
        artist_filter: list[str] | None,
        country_filter: list[str] | None,
        cursor: int | None,
    ) -> bool:
        if track.track_id is None or track.track_id in excluded_ids:
            return False
        if track.is_deleted or not user.can_listen(track):
            return False
        if (
            remaining_duration is not None
            and track.duration_seconds > remaining_duration
        ):
            return False
        if not matches_track_filters(
            track,
            genre=genre_filter,
            year=year_filter,
            artist=artist_filter,
            country=country_filter,
        ):
            return False
        return not (cursor is not None and track.track_id <= cursor)

    def _resolve_excluded_ids(self, playlist: Playlist, eff_user_id: int) -> set[int]:
        excluded_ids = {t.track_id for t in playlist.tracks if t.track_id is not None}
        if self.interaction_repo:
            rejected = self.interaction_repo.list_by_user(
                eff_user_id, action=InteractionAction.DISLIKE
            )
            excluded_ids.update(i.track_id for i in rejected)
        return excluded_ids

    def _fetch_candidates(
        self,
        *,
        source_playlist_id: int | None,
        genre_f: list[str] | None,
        artist_f: list[str] | None,
        year_f: list[int] | None,
        user: User,
        excluded_ids: set[int],
    ) -> list[Track]:
        candidates: list[Track] = []
        if source_playlist_id is not None:
            source_playlist = self.playlist_repo.find_by_id(source_playlist_id)
            if source_playlist is not None:
                candidates = list(source_playlist.tracks)

        if not candidates and (genre_f or artist_f or year_f):
            candidates = self.track_repo.find_by_filters(
                artist=artist_f,
                genre=genre_f,
                year=year_f,
                limit=100,
            )

        if not candidates:
            candidates = self.track_repo.list_active(
                limit=100,
                excluded_genres=list(user.blocked_genres),
                excluded_genre_terms=user.restricted_genre_terms(),
                block_explicit=user.is_minor(),
                excluded_ids=list(excluded_ids),
            )

        return candidates

    def execute(
        self,
        command_or_playlist_id: GetPlaylistDeckCommand | int | None = None,
        playlist_id: int | None = None,
        user_id: int | None = None,
        limit: int = 20,
        cursor_id: int | None = None,
    ) -> PlaylistDeckResult:
        pl_id, eff_user_id, page_limit, cursor = self._resolve_params(
            command_or_playlist_id, playlist_id, user_id, limit, cursor_id
        )

        user = self.user_repo.find_by_id(eff_user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {eff_user_id} not found.")

        playlist = self.playlist_repo.find_by_id(pl_id)
        if not playlist:
            raise EntityNotFoundError(f"Playlist with ID {pl_id} not found.")

        if not playlist.is_owned_by(eff_user_id):
            raise PermissionDeniedError(
                "Access denied: playlist does not belong to this user."
            )

        remaining: int | None = None
        if playlist.max_duration_seconds is not None:
            remaining = playlist.max_duration_seconds - playlist.total_duration_seconds
            if remaining <= 0:
                return PlaylistDeckResult(items=[], next_cursor=None, has_more=False)

        excluded_ids = self._resolve_excluded_ids(playlist, eff_user_id)
        genre_f, artist_f, year_f, country_f = extract_deck_filters_tuple(
            playlist.deck_filters
        )

        candidates = self._fetch_candidates(
            source_playlist_id=playlist.source_playlist_id,
            genre_f=genre_f,
            artist_f=artist_f,
            year_f=year_f,
            user=user,
            excluded_ids=excluded_ids,
        )

        eligible = [
            t
            for t in candidates
            if self._is_track_eligible(
                t,
                user,
                excluded_ids,
                remaining,
                genre_f,
                year_f,
                artist_f,
                country_f,
                cursor,
            )
        ]
        eligible.sort(key=lambda t: t.track_id or 0)

        has_more = len(eligible) > page_limit
        items = eligible[:page_limit]
        next_cursor = items[-1].track_id if has_more and items else None

        return PlaylistDeckResult(
            items=items, next_cursor=next_cursor, has_more=has_more
        )
