"""Use case for retrieving candidate tracks for a playlist deck."""

import json
from dataclasses import dataclass

from app.application.dtos.playlist_dtos import (
    GetPlaylistDeckCommand,
    PlaylistDeckResult,
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

    @staticmethod
    def _coerce_string_list(value: object | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            values: list[str] = []
            for item in value:
                values.extend(GetPlaylistDeckUseCase._coerce_string_list(item))
            return values
        text = str(value).strip()
        if not text:
            return []
        return [part.strip() for part in text.split(",") if part.strip()]

    @staticmethod
    def _coerce_int_list(value: object | None) -> list[int]:
        values: list[int] = []
        if value is None:
            return values
        if isinstance(value, (list, tuple, set)):
            for item in value:
                values.extend(GetPlaylistDeckUseCase._coerce_int_list(item))
            return values
        try:
            if str(value).strip():
                values.append(int(str(value).strip()))
        except TypeError, ValueError:
            return []
        return values

    @staticmethod
    def _matches_any(value: str | None, expected: list[str]) -> bool:
        if not expected:
            return True
        haystack = (value or "").strip().casefold()
        return any(part.casefold() in haystack for part in expected)

    def _extract_filters(
        self, deck_filters: str | None
    ) -> tuple[list[str] | None, list[str] | None, list[int] | None, list[str] | None]:
        if not deck_filters:
            return None, None, None, None
        try:
            filters = json.loads(deck_filters)
            if not isinstance(filters, dict):
                return None, None, None, None
        except ValueError, TypeError:
            return None, None, None, None

        genre_values = self._coerce_string_list(
            filters.get("genre") or filters.get("genero")
        )
        artist_values = self._coerce_string_list(
            filters.get("artist") or filters.get("artista")
        )
        year_values = self._coerce_int_list(filters.get("year") or filters.get("ano"))
        country_values = self._coerce_string_list(
            filters.get("country") or filters.get("pais")
        )
        return (
            genre_values or None,
            artist_values or None,
            year_values or None,
            country_values or None,
        )

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
        if genre_filter and not self._matches_any(track.genre, genre_filter):
            return False
        if year_filter is not None and track.release_year not in year_filter:
            return False
        if artist_filter and not self._matches_any(track.artist, artist_filter):
            return False
        if country_filter and not self._matches_any(track.country, country_filter):
            return False
        return not (cursor is not None and track.track_id <= cursor)

    def execute(  # noqa: C901
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

        excluded_ids = {t.track_id for t in playlist.tracks if t.track_id is not None}
        if self.interaction_repo:
            rejected = self.interaction_repo.list_by_user(
                eff_user_id, action=InteractionAction.DISLIKE
            )
            excluded_ids.update(i.track_id for i in rejected)

        genre_f, artist_f, year_f, country_f = self._extract_filters(
            playlist.deck_filters
        )

        candidates: list[Track] = []
        if playlist.source_playlist_id is not None:
            source_playlist = self.playlist_repo.find_by_id(playlist.source_playlist_id)
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
                excluded_genre_terms=(
                    tuple(sorted(user.MINOR_RESTRICTED_GENRE_TERMS))
                    if user.is_minor()
                    else ()
                ),
                block_explicit=not user.is_adult,
                excluded_ids=list(excluded_ids),
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
