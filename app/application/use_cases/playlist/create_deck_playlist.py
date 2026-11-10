"""Use case for creating a contextual track deck playlist."""

import json
from dataclasses import dataclass

from app.domain.exceptions import EntityNotFoundError
from app.domain.models.playlist import Playlist
lazy from app.application.dtos.playlist_dtos import CreateDeckPlaylistCommand
lazy from app.application.ports.repositories.playlist_repository import (
    PlaylistRepositoryPort,
)
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.domain.models.track import Track


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

    def _select_tracks(  # noqa: C901
        self,
        command: CreateDeckPlaylistCommand,
        user: object,
        filters: dict[str, list[str] | list[int]],
        reference_id: int | None,
        target_seconds: int | None,
    ) -> tuple[list[Track], int]:
        if not command.populate_tracks:
            return [], 0

        candidates: list[Track]
        if reference_id is not None:
            source_playlist = self.playlist_repo.find_by_id(reference_id)
            if source_playlist is None:
                raise EntityNotFoundError(f"Playlist with ID {reference_id} not found.")
            candidates = list(source_playlist.tracks)
        elif any(filters.values()):
            candidates = self.track_repo.find_by_filters(
                artist=(
                    filters["artist"][0]
                    if len(filters["artist"]) == 1
                    else filters["artist"]
                ),
                genre=(
                    filters["genre"][0]
                    if len(filters["genre"]) == 1
                    else filters["genre"]
                ),
                year=(
                    filters["year"][0] if len(filters["year"]) == 1 else filters["year"]
                ),
            )
        else:
            candidates = self.track_repo.list_active(
                limit=250,
                block_explicit=not user.is_adult,
                excluded_genres=list(user.blocked_genres),
                excluded_genre_terms=(
                    tuple(sorted(user.MINOR_RESTRICTED_GENRE_TERMS))
                    if user.is_minor()
                    else ()
                ),
            )

        if reference_id is None and not any(filters.values()):
            if not user.is_adult:
                candidates = [track for track in candidates if not track.explicit]
        elif any(filters.values()):
            candidates = [
                track
                for track in candidates
                if self._matches_fields(
                    track,
                    genre=filters["genre"] or None,
                    year=filters["year"] or None,
                    artist=filters["artist"] or None,
                    country=filters["country"] or None,
                )
            ]
        if (reference_id is not None or any(filters.values())) and not user.is_adult:
            candidates = [track for track in candidates if not track.explicit]

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

        normalized_genre = self._coerce_string_list(command.genre)
        normalized_artist = self._coerce_string_list(command.artist)
        normalized_year = self._coerce_year_list(command.year)
        normalized_country = self._coerce_string_list(command.country)

        deck_filters_dict = {
            "genre": normalized_genre,
            "year": normalized_year,
            "artist": normalized_artist,
            "country": normalized_country,
        }
        if isinstance(command.deck_filters, dict):
            deck_filters_dict = {
                "genre": self._coerce_string_list(
                    command.deck_filters.get("genre")
                    or command.deck_filters.get("genero")
                ),
                "year": self._coerce_year_list(
                    command.deck_filters.get("year") or command.deck_filters.get("ano")
                ),
                "artist": self._coerce_string_list(
                    command.deck_filters.get("artist")
                    or command.deck_filters.get("artista")
                ),
                "country": self._coerce_string_list(
                    command.deck_filters.get("country")
                    or command.deck_filters.get("pais")
                ),
            }
        elif isinstance(command.deck_filters, str):
            try:
                parsed = json.loads(command.deck_filters)
                if isinstance(parsed, dict):
                    deck_filters_dict = {
                        "genre": self._coerce_string_list(
                            parsed.get("genre") or parsed.get("genero")
                        ),
                        "year": self._coerce_year_list(
                            parsed.get("year") or parsed.get("ano")
                        ),
                        "artist": self._coerce_string_list(
                            parsed.get("artist") or parsed.get("artista")
                        ),
                        "country": self._coerce_string_list(
                            parsed.get("country") or parsed.get("pais")
                        ),
                    }
            except TypeError, ValueError:
                deck_filters_dict = {
                    "genre": [],
                    "year": [],
                    "artist": [],
                    "country": [],
                }

        if not any(deck_filters_dict.values()):
            deck_filters_dict = {
                "genre": normalized_genre,
                "year": normalized_year,
                "artist": normalized_artist,
                "country": normalized_country,
            }

        deck_filters_str = json.dumps(deck_filters_dict)

        reference_id = command.reference_playlist_id or command.source_playlist_id
        selected_tracks, accumulated_seconds = self._select_tracks(
            command, user, deck_filters_dict, reference_id, target_seconds
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
