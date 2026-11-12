"""Use case for creating a contextual track deck playlist."""

import json
from dataclasses import dataclass

from app.application.use_cases.playlist.deck_filter_helpers import (
    DeckFilters,
    matches_track_filters,
    resolve_deck_filters,
)
from app.domain.exceptions import EntityNotFoundError, PermissionDeniedError
from app.domain.models.playlist import Playlist
lazy from app.application.dtos.playlist_dtos import CreateDeckPlaylistCommand
lazy from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.track import Track
lazy from app.domain.models.user import User


@dataclass(slots=True, frozen=True)
class CreateDeckPlaylistUseCase:
    """Builds and persists a new playlist matching duration and filter constraints."""

    user_repo: UserRepositoryPort
    track_repo: TrackRepositoryPort
    playlist_repo: PlaylistRepositoryPort

    def _fetch_candidate_tracks(
        self,
        *,
        source_playlist: Playlist | None,
        deck_filters: DeckFilters,
        user: User,
    ) -> list[Track]:
        if source_playlist is not None:
            return list(source_playlist.tracks)

        if any(deck_filters.values()):
            return self.track_repo.find_by_filters(
                artist=(
                    deck_filters["artist"][0]
                    if len(deck_filters["artist"]) == 1
                    else deck_filters["artist"]
                )
                or None,
                genre=(
                    deck_filters["genre"][0]
                    if len(deck_filters["genre"]) == 1
                    else deck_filters["genre"]
                )
                or None,
                year=(
                    deck_filters["year"][0]
                    if len(deck_filters["year"]) == 1
                    else deck_filters["year"]
                )
                or None,
            )

        return self.track_repo.list_active(
            limit=250,
            block_explicit=user.is_minor(),
            excluded_genres=list(user.blocked_genres),
            excluded_genre_terms=user.restricted_genre_terms(),
        )

    def _filter_and_accumulate_tracks(
        self,
        candidates: list[Track],
        deck_filters: DeckFilters,
        user: User,
        target_seconds: int | None,
    ) -> tuple[list[Track], int]:
        if any(deck_filters.values()):
            candidates = [
                t
                for t in candidates
                if matches_track_filters(
                    t,
                    genre=deck_filters["genre"] or None,
                    year=deck_filters["year"] or None,
                    artist=deck_filters["artist"] or None,
                    country=deck_filters["country"] or None,
                )
            ]

        candidates = [t for t in candidates if not t.is_deleted and user.can_listen(t)]

        if not candidates:
            fallback = self.track_repo.list_active(
                block_explicit=True,
                limit=10,
            )
            candidates = [
                t for t in fallback if not t.is_deleted and user.can_listen(t)
            ]

        selected_tracks: list[Track] = []
        accumulated_seconds = 0
        for track in candidates:
            if target_seconds and accumulated_seconds + track.duration_seconds > (
                target_seconds + 60
            ):
                break
            selected_tracks.append(track)
            accumulated_seconds += track.duration_seconds

        return selected_tracks, accumulated_seconds

    def execute(self, command: CreateDeckPlaylistCommand) -> Playlist:
        user = self.user_repo.find_by_id(command.user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {command.user_id} not found.")

        target_seconds = (
            (command.duration_minutes * 60) if command.duration_minutes else None
        )
        deck_filters_dict = resolve_deck_filters(
            genre=command.genre,
            year=command.year,
            artist=command.artist,
            country=command.country,
            raw_deck_filters=command.deck_filters,
        )
        deck_filters_str = json.dumps(deck_filters_dict)
        source_id = command.source_playlist_id or command.reference_playlist_id
        source_playlist: Playlist | None = None

        if source_id is not None:
            source_playlist = self.playlist_repo.find_by_id(source_id)
            if source_playlist is None:
                raise EntityNotFoundError(f"Playlist with ID {source_id} not found.")
            if not source_playlist.is_owned_by(command.user_id):
                raise PermissionDeniedError(
                    "Access denied: playlist does not belong to this user."
                )

        selected_tracks: list[Track] = []
        accumulated_seconds = 0
        if command.populate_tracks:
            candidates = self._fetch_candidate_tracks(
                source_playlist=source_playlist,
                deck_filters=deck_filters_dict,
                user=user,
            )
            selected_tracks, accumulated_seconds = self._filter_and_accumulate_tracks(
                candidates, deck_filters_dict, user, target_seconds
            )

        max_duration = target_seconds
        if (
            command.populate_tracks
            and max_duration is not None
            and accumulated_seconds > max_duration
        ):
            max_duration = accumulated_seconds

        playlist = Playlist(
            playlist_id=None,
            user_id=command.user_id,
            name=command.name.strip(),
            description=command.description.strip() if command.description else None,
            is_exported=False,
            max_duration_seconds=max_duration,
            deck_filters=deck_filters_str,
            source_playlist_id=source_id,
            initial_tracks=selected_tracks,
        )
        return self.playlist_repo.save(playlist)
