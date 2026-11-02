"""Domain model representing a playlist entity."""

from dataclasses import InitVar, dataclass, field
from typing import Self
lazy from collections.abc import Sequence
lazy from datetime import datetime

from app.domain.exceptions import BusinessRuleViolationError
lazy from app.domain.models.track import Track


@dataclass(slots=True, kw_only=True, eq=False)
class Playlist:
    playlist_id: int | None = None
    user_id: int
    name: str
    description: str | None = None
    spotify_playlist_id: str | None = None
    is_exported: bool = False
    created_at: datetime | None = None
    max_duration_seconds: int | None = None
    deck_filters: str | None = None
    initial_tracks: InitVar[Sequence[Track]] = ()
    _tracks: list[Track] = field(init=False, default_factory=list, repr=False)

    def __post_init__(self, initial_tracks: Sequence[Track]) -> None:
        for track in initial_tracks:
            self.add_track(track)

    def is_owned_by(self, user_id: int) -> bool:
        return self.user_id == user_id

    @property
    def tracks(self) -> tuple[Track, ...]:
        return tuple(self._tracks)

    @property
    def total_duration_seconds(self) -> int:
        return sum(t.duration_seconds for t in self._tracks)

    duracao_total_segundos = total_duration_seconds

    def can_fit_duration(self, additional_seconds: int) -> bool:
        if self.max_duration_seconds is None:
            return True
        return (
            self.total_duration_seconds + additional_seconds
            <= self.max_duration_seconds
        )

    def add_track(self, track: Track) -> Self:
        if track.track_id is not None and any(
            existing.track_id == track.track_id for existing in self._tracks
        ):
            raise BusinessRuleViolationError(
                f"Track {track.track_id} is already in the playlist."
            )
        if not self.can_fit_duration(track.duration_seconds):
            raise BusinessRuleViolationError(
                "Track addition exceeds maximum playlist duration."
            )
        self._tracks.append(track)
        return self

    def remove_track(self, track_id: int) -> Self:
        self._tracks = [t for t in self._tracks if t.track_id != track_id]
        return self

    def replace_tracks(self, tracks: Sequence[Track]) -> Self:
        """Swaps the whole track list, keeping the previous one if any track is rejected."""
        previous = self._tracks
        self._tracks = []
        try:
            for track in tracks:
                self.add_track(track)
        except BusinessRuleViolationError:
            self._tracks = previous
            raise
        return self

    def export(self, spotify_playlist_id: str) -> Self:
        self.spotify_playlist_id = spotify_playlist_id
        self.is_exported = True
        return self
