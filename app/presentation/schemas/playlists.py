"""Playlist and track presentation schemas."""

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class TrackResponse(BaseModel):
    """Public representation of a catalog track."""

    model_config = ConfigDict(from_attributes=True)

    track_id: int
    title: str
    artist: str
    duration_seconds: int
    genre: str
    spotify_id: str | None = None
    album: str | None = None
    country: str | None = None
    release_year: int | None = None
    cover_url: str | None = None
    itunes_preview_url: str | None = None
    explicit: bool = False
    is_deleted: bool = False


class DeckPlaylistRequest(BaseModel):
    """Payload for generating a dynamic deck playlist."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = Field(min_length=1, max_length=100)
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    genre: str | list[str] | None = None
    year: int | list[int] | None = None
    artist: str | list[str] | None = None
    country: str | list[str] | None = None
    description: str | None = Field(default=None, max_length=500)
    source_playlist_id: int | None = Field(
        default=None,
        validation_alias=AliasChoices("source_playlist_id", "reference_playlist_id"),
    )

    @field_validator("year")
    @classmethod
    def validate_year(cls, value: int | list[int] | None) -> int | list[int] | None:
        if value is None:
            return None
        years = [value] if isinstance(value, int) else value
        for y in years:
            if not (1900 <= y <= 2100):
                raise ValueError(f"Year must be between 1900 and 2100, got {y}.")
        return value

    @property
    def reference_playlist_id(self) -> int | None:
        return self.source_playlist_id


class SwipeAddTrackRequest(BaseModel):
    """Payload for adding a swiped track to a playlist."""

    model_config = ConfigDict(extra="forbid")

    track_id: int
    action: str = "like"


SwipeAddMusicaRequest = SwipeAddTrackRequest


class PlaylistResponse(BaseModel):
    """Public representation of a playlist and its tracks."""

    model_config = ConfigDict(from_attributes=True)

    playlist_id: int
    user_id: int
    name: str
    description: str | None = None
    spotify_playlist_id: str | None = None
    cover_image_url: str | None = None
    is_exported: bool = False
    tracks: list[TrackResponse] = Field(default_factory=list)
    max_duration_seconds: int | None = None
    deck_filters: str | None = None
    source_playlist_id: int | None = None
    total_duration_seconds: int = 0


class PaginatedTracksResponse(BaseModel):
    """Cursor-paginated tracks page."""

    model_config = ConfigDict(from_attributes=True)

    items: list[TrackResponse] = Field(default_factory=list)
    next_cursor: int | None = None
    has_more: bool = False


PaginaMusicasResponse = PaginatedTracksResponse


__all__ = [
    "DeckPlaylistRequest",
    "PaginaMusicasResponse",
    "PaginatedTracksResponse",
    "PlaylistResponse",
    "SwipeAddMusicaRequest",
    "SwipeAddTrackRequest",
    "TrackResponse",
]
