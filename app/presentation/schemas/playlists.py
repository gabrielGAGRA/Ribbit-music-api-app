"""Playlist and track presentation schemas."""

from pydantic import BaseModel, ConfigDict, Field, computed_field


class TrackResponse(BaseModel):
    """Public representation of a catalog track."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

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

    @computed_field
    @property
    def musica_id(self) -> int:
        return self.track_id

    @computed_field
    @property
    def titulo(self) -> str:
        return self.title

    @computed_field
    @property
    def artista(self) -> str:
        return self.artist

    @computed_field
    @property
    def duracao_segundos(self) -> int:
        return self.duration_seconds

    @computed_field
    @property
    def bloqueado_para_menores(self) -> bool:
        return self.explicit


MusicaResponse = TrackResponse


class DeckPlaylistRequest(BaseModel):
    """Payload for generating a dynamic deck playlist."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(alias="nome", min_length=1, max_length=100)
    duration_minutes: int | None = Field(
        default=None, alias="duracao_minutos", ge=1, le=600
    )
    genre: str | None = Field(default=None, alias="genero")
    year: int | None = Field(default=None, alias="ano", ge=1900, le=2100)
    artist: str | None = Field(default=None, alias="artista")
    country: str | None = Field(default=None, alias="pais")
    description: str | None = Field(default=None, alias="descricao", max_length=500)
    user_id: int | None = None


class SwipeAddTrackRequest(BaseModel):
    """Payload for adding a swiped track to a playlist."""

    model_config = ConfigDict(populate_by_name=True)

    track_id: int = Field(alias="musica_id")
    action: str = Field(default="like", alias="acao")


SwipeAddMusicaRequest = SwipeAddTrackRequest


class PlaylistResponse(BaseModel):
    """Public representation of a playlist and its tracks."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    playlist_id: int
    user_id: int
    name: str
    description: str | None = None
    spotify_playlist_id: str | None = None
    is_exported: bool = False
    tracks: list[TrackResponse] = Field(default_factory=list)
    max_duration_seconds: int | None = None
    deck_filters: str | None = None
    total_duration_seconds: int = 0

    @computed_field
    @property
    def musicas(self) -> list[TrackResponse]:
        return self.tracks

    @computed_field
    @property
    def duracao_total_segundos(self) -> int:
        return self.total_duration_seconds or sum(
            t.duration_seconds for t in self.tracks
        )

    @computed_field
    @property
    def usuario_id(self) -> int:
        return self.user_id

    @computed_field
    @property
    def nome(self) -> str:
        return self.name

    @computed_field
    @property
    def descricao(self) -> str | None:
        return self.description

    @computed_field
    @property
    def is_exportada(self) -> bool:
        return self.is_exported


class PaginatedTracksResponse(BaseModel):
    """Cursor-paginated tracks page."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    items: list[TrackResponse] = Field(default_factory=list)
    next_cursor: int | None = None
    has_more: bool = False


PaginaMusicasResponse = PaginatedTracksResponse


__all__ = [
    "DeckPlaylistRequest",
    "MusicaResponse",
    "PaginaMusicasResponse",
    "PaginatedTracksResponse",
    "PlaylistResponse",
    "SwipeAddMusicaRequest",
    "SwipeAddTrackRequest",
    "TrackResponse",
]
