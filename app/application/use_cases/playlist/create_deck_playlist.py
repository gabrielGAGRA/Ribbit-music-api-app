"""Use case for creating a contextual track deck playlist."""

import json
from dataclasses import dataclass
from typing import TypedDict

from app.domain.exceptions import EntityNotFoundError
from app.domain.models.playlist import Playlist
lazy from app.application.dtos.playlist_dtos import CreateDeckPlaylistCommand
lazy from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.track import Track
lazy from app.domain.models.user import User


class DeckFilters(TypedDict):
    genre: list[str]
    year: list[int]
    artist: list[str]
    country: list[str]


@dataclass(slots=True, frozen=True)
class CreateDeckPlaylistUseCase:
    """Builds and persists a new playlist matching duration and filter constraints."""

    user_repo: UserRepositoryPort
    track_repo: TrackRepositoryPort
    playlist_repo: PlaylistRepositoryPort

    @staticmethod
    def _coerce_string_list(value: object | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            values: list[str] = []
            for item in value:
                values.extend(CreateDeckPlaylistUseCase._coerce_string_list(item))
            return values
        text = str(value).strip()
        if not text:
            return []
        return [part.strip() for part in text.split(",") if part.strip()]

    @staticmethod
    def _coerce_year_list(value: object | None) -> list[int]:
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            values: list[int] = []
            for item in value:
                values.extend(CreateDeckPlaylistUseCase._coerce_year_list(item))
            return values
        try:
            return [int(str(value).strip())] if str(value).strip() else []
        except TypeError, ValueError:
            return []

    @staticmethod
    def _matches_fields(
        track: Track,
        *,
        genre: list[str] | None,
        year: list[int] | None,
        artist: list[str] | None,
        country: list[str] | None,
    ) -> bool:
        if genre and not any(
            part.casefold() in track.genre.casefold() for part in genre
        ):
            return False
        if year is not None and track.release_year not in year:
            return False
        if artist and not any(
            part.casefold() in track.artist.casefold() for part in artist
        ):
            return False
        return not (
            country
            and not any(
                (track.country or "").casefold().find(part.casefold()) >= 0
                for part in country
            )
        )

    def _extract_dict_filters(self, payload: dict[str, object]) -> DeckFilters:
        return {
            "genre": self._coerce_string_list(payload.get("genre")),
            "year": self._coerce_year_list(payload.get("year")),
            "artist": self._coerce_string_list(payload.get("artist")),
            "country": self._coerce_string_list(payload.get("country")),
        }

    def _resolve_deck_filters(self, command: CreateDeckPlaylistCommand) -> DeckFilters:
        deck_filters_dict: DeckFilters = {
            "genre": self._coerce_string_list(command.genre),
            "year": self._coerce_year_list(command.year),
            "artist": self._coerce_string_list(command.artist),
            "country": self._coerce_string_list(command.country),
        }
        if isinstance(command.deck_filters, dict):
            deck_filters_dict = self._extract_dict_filters(command.deck_filters)
        elif isinstance(command.deck_filters, str):
            try:
                parsed = json.loads(command.deck_filters)
                if isinstance(parsed, dict):
                    deck_filters_dict = self._extract_dict_filters(parsed)
            except TypeError, ValueError:
                deck_filters_dict = {
                    "genre": [],
                    "year": [],
                    "artist": [],
                    "country": [],
                }

        if not any(deck_filters_dict.values()):
            deck_filters_dict = {
                "genre": self._coerce_string_list(command.genre),
                "year": self._coerce_year_list(command.year),
                "artist": self._coerce_string_list(command.artist),
                "country": self._coerce_string_list(command.country),
            }
        return deck_filters_dict

    def _fetch_candidate_tracks(
        self,
        *,
        reference_id: int | None,
        deck_filters: DeckFilters,
        user: User,
    ) -> list[Track]:
        if reference_id is not None:
            source_playlist = self.playlist_repo.find_by_id(reference_id)
            if source_playlist is None:
                raise EntityNotFoundError(f"Playlist with ID {reference_id} not found.")
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
                if self._matches_fields(
                    t,
                    genre=deck_filters["genre"] or None,
                    year=deck_filters["year"] or None,
                    artist=deck_filters["artist"] or None,
                    country=deck_filters["country"] or None,
                )
            ]
        if not user.is_adult:
            candidates = [t for t in candidates if not t.explicit]
        if not candidates:
            candidates = self.track_repo.list_active(
                block_explicit=True,
                limit=10,
            )

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
        deck_filters_dict = self._resolve_deck_filters(command)
        deck_filters_str = json.dumps(deck_filters_dict)
        reference_id = command.reference_playlist_id or command.source_playlist_id

        selected_tracks: list[Track] = []
        accumulated_seconds = 0
        if command.populate_tracks:
            candidates = self._fetch_candidate_tracks(
                reference_id=reference_id,
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
            source_playlist_id=reference_id,
            initial_tracks=selected_tracks,
        )
        return self.playlist_repo.save(playlist)
