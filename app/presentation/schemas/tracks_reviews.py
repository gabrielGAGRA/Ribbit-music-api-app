"""Review presentation schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.presentation.schemas.discovery import InteractionResponse


class PublishReviewRequest(BaseModel):
    """Payload to post a star rating and critique on a track."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: int | None = None
    track_id: int | None = None
    musica_id: int | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    nota: int | None = Field(default=None, ge=1, le=5)
    text: str | None = Field(default=None, max_length=1000)
    texto: str | None = Field(default=None, max_length=1000)

    @property
    def resolved_track_id(self) -> int:
        tid = self.track_id if self.track_id is not None else self.musica_id
        if tid is None:
            raise ValueError("track_id or musica_id is required.")
        return tid

    @property
    def resolved_rating(self) -> int:
        r = self.rating if self.rating is not None else self.nota
        if r is None:
            raise ValueError("rating or nota is required.")
        return r

    @property
    def resolved_text(self) -> str | None:
        return self.text if self.text is not None else self.texto


class ReviewResponse(BaseModel):
    """Public representation of a user review."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    review_id: int | None = None
    user_id: int
    track_id: int
    rating: int
    text: str | None = None
    likes_count: int = 0
    is_deleted: bool = False
    created_at: datetime | None = None

    @computed_field
    def avaliacao_id(self) -> int | None:
        return self.review_id

    @computed_field
    def usuario_id(self) -> int:
        return self.user_id

    @computed_field
    def musica_id(self) -> int:
        return self.track_id

    @computed_field
    def nota(self) -> int:
        return self.rating

    @computed_field
    def texto(self) -> str | None:
        return self.text


class CatalogTrackResponse(BaseModel):
    """Public representation of a catalog track with multi-language aliases."""

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
    def musica_id(self) -> int:
        return self.track_id

    @computed_field
    def titulo(self) -> str:
        return self.title

    @computed_field
    def artista(self) -> str:
        return self.artist

    @computed_field
    def duracao_segundos(self) -> int:
        return self.duration_seconds

    @computed_field
    def genero(self) -> str:
        return self.genre

    @computed_field
    def bloqueado_para_menores(self) -> bool:
        return self.explicit


class RecentInteractedTrackResponse(BaseModel):
    """Response item pairing an interaction with the track details."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    interaction: InteractionResponse
    track: CatalogTrackResponse

    @computed_field
    def interacao(self) -> InteractionResponse:
        return self.interaction

    @computed_field
    def musica(self) -> CatalogTrackResponse:
        return self.track


class SaveSearchTrackLikeRequest(BaseModel):
    """Payload to save a search track into favorites and optional playlist."""

    playlist_id: int | None = None


class TrackReviewListResponse(BaseModel):
    """Response aggregating track details and its community reviews."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    track: CatalogTrackResponse | None = None
    reviews: list[ReviewResponse] = Field(default_factory=list)

    @computed_field
    def musica(self) -> CatalogTrackResponse | None:
        return self.track


class ReviewActionResponse(BaseModel):
    """Generic action response for reviews endpoints."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    success: bool = True
    sucesso: bool = True


__all__ = [
    "CatalogTrackResponse",
    "PublishReviewRequest",
    "RecentInteractedTrackResponse",
    "ReviewActionResponse",
    "ReviewResponse",
    "SaveSearchTrackLikeRequest",
    "TrackReviewListResponse",
]
