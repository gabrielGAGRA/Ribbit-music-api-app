"""Use case for fetching the next track candidate for swipe discovery."""

import logging
from dataclasses import dataclass
lazy import random

from app.domain.exceptions import EntityNotFoundError, ExternalServiceError
from app.domain.models.interaction import InteractionAction
from app.domain.services.recommendation import (
    RecommendationProfile,
    select_weighted_track,
)
lazy from app.application.ports.repositories.interaction_repository import (
    InteractionRepositoryPort,
)
lazy from app.application.ports.repositories.track_access_repository import (
    TrackAccessRepositoryPort,
)
lazy from app.application.ports.repositories.track_repository import TrackRepositoryPort
lazy from app.application.ports.repositories.user_repository import UserRepositoryPort
lazy from app.application.ports.services.catalog_source import TrackCatalogFilePort
lazy from app.application.ports.services.music_service import (
    TrackPreviewPort,
    lookup_matching_preview,
)
lazy from app.domain.models.track import Track
lazy from app.domain.models.user import User


def _is_missing_or_placeholder_url(url: str | None) -> bool:
    return not url or "example.com" in url


@dataclass(slots=True, frozen=True)
class GetNextDiscoveryTrackUseCase:
    """Finds the next active track matching user age and genre preferences."""

    user_repo: UserRepositoryPort
    track_repo: TrackRepositoryPort
    interaction_repo: InteractionRepositoryPort
    track_access_repo: TrackAccessRepositoryPort | None = None
    track_preview_port: TrackPreviewPort | None = None
    catalog_file_port: TrackCatalogFilePort | None = None
    candidate_pool_size: int = 100
    max_preview_attempts: int = 5
    rng: random.Random | None = None

    def _list_candidates(
        self,
        user: User,
        blocked_genres: tuple[str, ...],
        interacted_ids: list[int],
    ) -> list[Track]:
        if user.favorite_genres:
            return self.track_repo.list_active(
                excluded_genres=blocked_genres,
                excluded_genre_terms=user.restricted_genre_terms(),
                preferred_genres=tuple(user.favorite_genres),
                block_explicit=user.is_minor(),
                excluded_ids=interacted_ids,
                limit=self.candidate_pool_size,
            )
        return self.track_repo.list_active(
            excluded_genres=blocked_genres,
            excluded_genre_terms=user.restricted_genre_terms(),
            block_explicit=user.is_minor(),
            excluded_ids=interacted_ids,
            limit=self.candidate_pool_size,
        )

    def _write_track_delta(self, track: Track) -> None:
        if self.catalog_file_port is None:
            return
        try:
            self.catalog_file_port.write_track_delta(
                title=track.title,
                artist=track.artist,
                preview_url=track.itunes_preview_url,
                genre=track.genre,
                cover_url=track.cover_url,
                spotify_id=track.spotify_id,
                album=track.album,
                duration_seconds=track.duration_seconds,
                country=track.country,
                release_year=track.release_year,
                explicit=track.explicit,
                is_deleted=track.is_deleted,
                created_at=track.created_at.isoformat() if track.created_at else None,
            )
        except ExternalServiceError as exc:
            logging.getLogger(__name__).warning(
                "Failed to write track delta for track %s: %s",
                track.track_id,
                exc,
                extra={
                    "event": "catalog.delta_write.failed",
                    "status": "warning",
                    "track_id": track.track_id,
                },
            )

    @staticmethod
    def _record_signal(
        genres: dict[str, float],
        artists: dict[str, float],
        decades: dict[int, float],
        *,
        genre: str,
        artist: str,
        release_year: int | None,
        delta: float,
    ) -> None:
        genre_key = genre.strip().casefold()
        artist_key = artist.strip().casefold()
        if genre_key and genre_key != "unknown":
            genres[genre_key] = genres.get(genre_key, 0.0) + delta
        if artist_key:
            artists[artist_key] = artists.get(artist_key, 0.0) + delta
        if release_year is not None:
            decade = (release_year // 10) * 10
            decades[decade] = decades.get(decade, 0.0) + delta

    def _build_recommendation_profile(self, user_id: int) -> RecommendationProfile:
        pos_genres: dict[str, float] = {}
        disliked_genres: dict[str, float] = {}
        pos_artists: dict[str, float] = {}
        disliked_artists: dict[str, float] = {}
        pos_decades: dict[int, float] = {}
        disliked_decades: dict[int, float] = {}

        interactions = self.interaction_repo.list_by_user(user_id)
        recent_interactions = (
            interactions[-50:] if isinstance(interactions, list) else []
        )
        raw_access = (
            self.track_access_repo.list_by_user(
                user_id, include_deleted=False, limit=50
            )
            if self.track_access_repo is not None
            else []
        )
        access_entries = raw_access if isinstance(raw_access, list) else []

        track_ids = list(
            {i.track_id for i in recent_interactions}
            | {e.track_id for e in access_entries}
        )
        raw_tracks = self.track_repo.find_by_ids(track_ids) if track_ids else {}
        tracks_by_id = raw_tracks if isinstance(raw_tracks, dict) else {}

        for interaction in recent_interactions:
            track = tracks_by_id.get(interaction.track_id)
            if track is None or track.is_deleted:
                continue
            if interaction.action in (
                InteractionAction.LIKE,
                InteractionAction.SUPERLIKE,
            ):
                delta = (
                    2.0 if interaction.action == InteractionAction.SUPERLIKE else 1.0
                )
                self._record_signal(
                    pos_genres,
                    pos_artists,
                    pos_decades,
                    genre=track.genre,
                    artist=track.artist,
                    release_year=track.release_year,
                    delta=delta,
                )
            elif interaction.action == InteractionAction.DISLIKE:
                self._record_signal(
                    disliked_genres,
                    disliked_artists,
                    disliked_decades,
                    genre=track.genre,
                    artist=track.artist,
                    release_year=track.release_year,
                    delta=1.0,
                )

        for entry in access_entries:
            track = tracks_by_id.get(entry.track_id)
            self._record_signal(
                pos_genres,
                pos_artists,
                pos_decades,
                genre=entry.track_genre,
                artist=entry.track_artist,
                release_year=track.release_year if track is not None else None,
                delta=0.4,
            )

        return RecommendationProfile(
            positive_genres=pos_genres,
            disliked_genres=disliked_genres,
            positive_artists=pos_artists,
            disliked_artists=disliked_artists,
            positive_decades=pos_decades,
            disliked_decades=disliked_decades,
        )

    def execute(self, user_id: int) -> Track | None:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise EntityNotFoundError(f"User with ID {user_id} not found.")

        interacted_ids = self.interaction_repo.list_interacted_track_ids(user_id)
        profile = self._build_recommendation_profile(user_id)
        candidates = self._list_candidates(
            user,
            tuple(user.blocked_genres),
            interacted_ids,
        )
        preview_port = self.track_preview_port
        remaining = list(candidates)

        for _ in range(max(1, self.max_preview_attempts)):
            track = select_weighted_track(
                remaining, user, rng=self.rng, profile=profile
            )
            if track is None:
                return None
            if preview_port is None:
                return track

            needs_preview = _is_missing_or_placeholder_url(track.itunes_preview_url)
            needs_genre = not track.has_known_genre()
            needs_cover = _is_missing_or_placeholder_url(track.cover_url)
            external_error = False
            if needs_preview or needs_genre or needs_cover:
                external_error = self._enrich_track_from_preview(
                    track,
                    preview_port=preview_port,
                    needs_preview=needs_preview,
                    needs_genre=needs_genre,
                    needs_cover=needs_cover,
                )
            if external_error or not _is_missing_or_placeholder_url(
                track.itunes_preview_url
            ):
                return track

            track.mark_as_deleted()
            self.track_repo.save(track)
            self._write_track_delta(track)
            remaining = [t for t in remaining if t is not track]

        return None

    def _enrich_track_from_preview(
        self,
        track: Track,
        *,
        preview_port: TrackPreviewPort,
        needs_preview: bool,
        needs_genre: bool,
        needs_cover: bool,
    ) -> bool:
        try:
            preview = lookup_matching_preview(
                preview_port, title=track.title, artist=track.artist
            )
        except ExternalServiceError:
            return True
        if not preview:
            return False
        if (
            needs_preview
            and preview.preview_url
            and _is_missing_or_placeholder_url(track.itunes_preview_url)
        ):
            track.itunes_preview_url = None
        if (
            needs_cover
            and preview.cover_url
            and _is_missing_or_placeholder_url(track.cover_url)
        ):
            track.cover_url = None
        changed = track.merge_missing_metadata(
            itunes_preview_url=str(preview.preview_url)
            if needs_preview and preview.preview_url
            else None,
            genre=str(preview.genre) if needs_genre and preview.genre else None,
            cover_url=str(preview.cover_url)
            if needs_cover and preview.cover_url
            else None,
        )
        if changed:
            self.track_repo.save(track)
            self._write_track_delta(track)
        return False


__all__ = ["GetNextDiscoveryTrackUseCase"]
