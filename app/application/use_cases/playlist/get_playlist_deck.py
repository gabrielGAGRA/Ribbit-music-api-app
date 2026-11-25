"""Use case for retrieving candidate tracks for a playlist deck."""

from dataclasses import dataclass

from app.application.dtos.playlist_dtos import (
    GetPlaylistDeckCommand,
    PlaylistDeckResult,
)
from app.application.use_cases.playlist.deck_filter_helpers import (
    extract_deck_filters_tuple,
    extract_reference_source,
    matches_track_filters,
)
from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError
from app.domain.models.interaction import Interaction, InteractionAction
from app.domain.services.recommendation import order_tracks_by_weighted_preference
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

_INTERACTION_REF_SOURCES = frozenset({"curtidas", "amadas"})
_EXACT_REF_SOURCES = frozenset({"curtidas", "amadas", "playlists"})


@dataclass(slots=True, frozen=True)
class GetPlaylistDeckUseCase:
    """Returns a cursor-paginated page of candidate tracks eligible for a deck playlist."""

    user_repo: UserRepositoryPort
    playlist_repo: PlaylistRepositoryPort
    track_repo: TrackRepositoryPort
    interaction_repo: InteractionRepositoryPort | None = None

    @staticmethod
    def _normalize_phase(phase: str) -> str:
        return "additional" if phase.strip().casefold() == "additional" else "primary"

    def _resolve_params(
        self,
        command_or_playlist_id: GetPlaylistDeckCommand | int | None,
        playlist_id: int | None,
        user_id: int | None,
        limit: int,
        cursor_id: int | None,
        phase: str,
    ) -> tuple[int, int, int, int | None, str]:
        if isinstance(command_or_playlist_id, GetPlaylistDeckCommand):
            return (
                command_or_playlist_id.playlist_id,
                command_or_playlist_id.user_id,
                command_or_playlist_id.limit,
                command_or_playlist_id.cursor_id,
                self._normalize_phase(command_or_playlist_id.phase),
            )
        target_id = (
            command_or_playlist_id
            if isinstance(command_or_playlist_id, int)
            else playlist_id
        )
        if target_id is None:
            raise ValueError("playlist_id must be provided.")
        if user_id is None:
            raise ValueError(
                "user_id must be provided when passing playlist_id directly."
            )
        return target_id, user_id, limit, cursor_id, self._normalize_phase(phase)

    def _is_track_eligible(
        self,
        track: Track,
        user: User,
        excluded_ids: set[int],
        genre_filter: list[str] | None,
        year_filter: list[int] | None,
        artist_filter: list[str] | None,
        country_filter: list[str] | None,
    ) -> bool:
        if track.track_id is None or track.track_id in excluded_ids:
            return False
        if track.is_deleted or not user.can_listen(track):
            return False
        return matches_track_filters(
            track,
            genre=genre_filter,
            year=year_filter,
            artist=artist_filter,
            country=country_filter,
        )

    @staticmethod
    def _deduplicate_tracks(tracks: list[Track]) -> list[Track]:
        seen: set[int] = set()
        unique: list[Track] = []
        for track in tracks:
            if track.track_id is None or track.track_id in seen:
                continue
            seen.add(track.track_id)
            unique.append(track)
        return unique

    def _resolve_excluded_ids(
        self,
        playlist: Playlist,
        interactions: list[Interaction],
        *,
        exclude_all_interactions: bool,
        extra_excluded_tracks: tuple[Track, ...] = (),
    ) -> set[int]:
        excluded_ids = {t.track_id for t in playlist.tracks if t.track_id is not None}
        excluded_ids.update(
            t.track_id for t in extra_excluded_tracks if t.track_id is not None
        )
        if exclude_all_interactions:
            excluded_ids.update(i.track_id for i in interactions)
        else:
            excluded_ids.update(
                i.track_id
                for i in interactions
                if i.action == InteractionAction.DISLIKE
            )
        return excluded_ids

    def _fetch_from_interaction_source(
        self,
        reference_source: str,
        interactions: list[Interaction],
    ) -> list[Track]:
        allowed_actions = (
            {InteractionAction.SUPERLIKE}
            if reference_source == "amadas"
            else {InteractionAction.LIKE, InteractionAction.SUPERLIKE}
        )
        track_ids = list(
            dict.fromkeys(
                i.track_id for i in interactions if i.action in allowed_actions
            )
        )
        if not track_ids:
            return []
        tracks_by_id = self.track_repo.find_by_ids(track_ids)
        return [tracks_by_id[tid] for tid in track_ids if tid in tracks_by_id]

    def _fetch_from_user_playlists(
        self,
        user_id: int,
        *,
        skip_playlist_ids: set[int],
    ) -> list[Track]:
        playlists = self.playlist_repo.list_by_user(user_id)
        collected: list[Track] = []
        for pl in playlists:
            if pl.playlist_id is not None and pl.playlist_id in skip_playlist_ids:
                continue
            collected.extend(pl.tracks)
        return self._deduplicate_tracks(collected)

    def _fetch_catalog_candidates(
        self,
        *,
        genre_f: list[str] | None,
        artist_f: list[str] | None,
        year_f: list[int] | None,
        country_f: list[str] | None,
        user: User,
        excluded_ids: set[int],
        page_limit: int,
    ) -> list[Track]:
        return self.track_repo.list_active(
            limit=max(100, page_limit + 1),
            excluded_genres=list(user.blocked_genres),
            excluded_genre_terms=user.restricted_genre_terms(),
            preferred_genres=tuple(user.favorite_genres),
            block_explicit=user.is_minor(),
            excluded_ids=list(excluded_ids),
            artist=artist_f,
            genre=genre_f,
            country=country_f,
            year=year_f,
            max_duration_seconds=None,
        )

    def _fetch_by_reference_source(
        self,
        *,
        reference_source: str,
        playlist_id: int,
        source_playlist_id: int | None,
        eff_user_id: int,
        interactions: list[Interaction],
        genre_f: list[str] | None,
        artist_f: list[str] | None,
        year_f: list[int] | None,
        country_f: list[str] | None,
        user: User,
        excluded_ids: set[int],
        page_limit: int,
    ) -> list[Track]:
        if reference_source in _INTERACTION_REF_SOURCES:
            return self._fetch_from_interaction_source(reference_source, interactions)
        if reference_source == "playlists":
            skip_ids = {playlist_id}
            if source_playlist_id is not None:
                skip_ids.add(source_playlist_id)
            return self._fetch_from_user_playlists(
                eff_user_id, skip_playlist_ids=skip_ids
            )
        return self._fetch_catalog_candidates(
            genre_f=genre_f,
            artist_f=artist_f,
            year_f=year_f,
            country_f=country_f,
            user=user,
            excluded_ids=excluded_ids,
            page_limit=page_limit,
        )

    def _resolve_deck_pool(
        self,
        *,
        playlist: Playlist,
        pl_id: int,
        eff_user_id: int,
        eff_phase: str,
        reference_source: str | None,
        interactions: list[Interaction],
        genre_f: list[str] | None,
        artist_f: list[str] | None,
        year_f: list[int] | None,
        country_f: list[str] | None,
        user: User,
        page_limit: int,
    ) -> tuple[list[Track], set[int]] | None:
        source_playlist: Playlist | None = None
        if playlist.source_playlist_id is not None:
            candidate_pl = self.playlist_repo.find_by_id(playlist.source_playlist_id)
            if candidate_pl is not None and candidate_pl.is_owned_by(eff_user_id):
                source_playlist = candidate_pl

        if eff_phase == "additional":
            if playlist.source_playlist_id is None or reference_source is None:
                return None
            source_tracks = (
                source_playlist.tracks if source_playlist is not None else ()
            )
            exclude_all = reference_source == "livre"
            excluded_ids = self._resolve_excluded_ids(
                playlist,
                interactions,
                exclude_all_interactions=exclude_all,
                extra_excluded_tracks=source_tracks,
            )
            candidates = self._fetch_by_reference_source(
                reference_source=reference_source,
                playlist_id=pl_id,
                source_playlist_id=playlist.source_playlist_id,
                eff_user_id=eff_user_id,
                interactions=interactions,
                genre_f=genre_f,
                artist_f=artist_f,
                year_f=year_f,
                country_f=country_f,
                user=user,
                excluded_ids=excluded_ids,
                page_limit=page_limit,
            )
            return candidates, excluded_ids

        if playlist.source_playlist_id is not None:
            if source_playlist is None or not source_playlist.tracks:
                return None
            excluded_ids = self._resolve_excluded_ids(
                playlist, interactions, exclude_all_interactions=False
            )
            return list(source_playlist.tracks), excluded_ids

        exclude_all = reference_source not in _EXACT_REF_SOURCES
        excluded_ids = self._resolve_excluded_ids(
            playlist, interactions, exclude_all_interactions=exclude_all
        )
        effective_source = reference_source or "livre"
        candidates = self._fetch_by_reference_source(
            reference_source=effective_source,
            playlist_id=pl_id,
            source_playlist_id=None,
            eff_user_id=eff_user_id,
            interactions=interactions,
            genre_f=genre_f,
            artist_f=artist_f,
            year_f=year_f,
            country_f=country_f,
            user=user,
            excluded_ids=excluded_ids,
            page_limit=page_limit,
        )
        return candidates, excluded_ids

    def _order_and_slice_cursor(
        self,
        *,
        playlist_id: int,
        user: User,
        user_id: int,
        phase: str,
        eligible: list[Track],
        cursor: int | None,
    ) -> list[Track]:
        pool = eligible
        if cursor is not None and all(t.track_id != cursor for t in eligible):
            cursor_track = self.track_repo.find_by_id(cursor)
            if (
                isinstance(cursor_track, Track)
                and cursor_track.track_id == cursor
                and not cursor_track.is_deleted
                and user.can_listen(cursor_track)
            ):
                pool = [*eligible, cursor_track]

        seed_suffix = ":additional" if phase == "additional" else ""
        ordered = order_tracks_by_weighted_preference(
            pool,
            user,
            seed_key=f"playlist:{playlist_id}:user:{user_id}{seed_suffix}",
        )
        if cursor is None:
            return ordered
        for index, track in enumerate(ordered):
            if track.track_id == cursor:
                return ordered[index + 1 :]
        return [t for t in ordered if t.track_id != cursor]

    def execute(
        self,
        command_or_playlist_id: GetPlaylistDeckCommand | int | None = None,
        playlist_id: int | None = None,
        user_id: int | None = None,
        limit: int = 20,
        cursor_id: int | None = None,
        phase: str = "primary",
    ) -> PlaylistDeckResult:
        pl_id, eff_user_id, page_limit, cursor, eff_phase = self._resolve_params(
            command_or_playlist_id, playlist_id, user_id, limit, cursor_id, phase
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

        if playlist.is_duration_limit_reached:
            return PlaylistDeckResult(items=[], next_cursor=None, has_more=False)

        interactions = (
            self.interaction_repo.list_by_user(eff_user_id)
            if self.interaction_repo is not None
            else []
        )
        genre_f, artist_f, year_f, country_f = extract_deck_filters_tuple(
            playlist.deck_filters
        )
        reference_source = extract_reference_source(playlist.deck_filters)

        resolved = self._resolve_deck_pool(
            playlist=playlist,
            pl_id=pl_id,
            eff_user_id=eff_user_id,
            eff_phase=eff_phase,
            reference_source=reference_source,
            interactions=interactions,
            genre_f=genre_f,
            artist_f=artist_f,
            year_f=year_f,
            country_f=country_f,
            user=user,
            page_limit=page_limit,
        )
        if resolved is None:
            return PlaylistDeckResult(items=[], next_cursor=None, has_more=False)

        candidates, excluded_ids = resolved
        eligible = self._deduplicate_tracks(
            [
                t
                for t in candidates
                if self._is_track_eligible(
                    t,
                    user,
                    excluded_ids,
                    genre_f,
                    year_f,
                    artist_f,
                    country_f,
                )
            ]
        )
        eligible = self._order_and_slice_cursor(
            playlist_id=pl_id,
            user=user,
            user_id=eff_user_id,
            phase=eff_phase,
            eligible=eligible,
            cursor=cursor,
        )

        has_more = len(eligible) > page_limit
        items = eligible[:page_limit]
        next_cursor = items[-1].track_id if has_more and items else None

        return PlaylistDeckResult(
            items=items, next_cursor=next_cursor, has_more=has_more
        )
