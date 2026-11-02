"""Collaborative Jam session presentation schemas."""

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.presentation.schemas.playlists import TrackResponse


class CreateJamRequest(BaseModel):
    """Payload to initiate a new collaborative Jam session."""

    model_config = ConfigDict(populate_by_name=True)

    room_name: str = Field(alias="nome_sala", min_length=1, max_length=100)
    duration_minutes: int = Field(default=60, alias="duracao_minutos", gt=0)
    max_superlikes: int = Field(default=10, alias="limite_superlikes", ge=0)
    skip_votes_threshold: int = Field(default=3, alias="meta_votos_pular", gt=0)
    deck_source: str = Field(default="livre", alias="fonte_deck")
    source_playlist_id: int | None = Field(default=None, alias="playlist_origem_id")
    host_user_id: int | None = Field(default=None, alias="host_usuario_id")


CriarJamRequest = CreateJamRequest


class JoinJamRequest(BaseModel):
    """Payload to join an ongoing Jam session via room code."""

    model_config = ConfigDict(populate_by_name=True)

    room_code: str = Field(
        alias="codigo_sala",
        min_length=1,
        max_length=20,
        pattern=r"^(\d{6}|[A-Za-z0-9_\-]{3,20})$",
    )


EntrarJamRequest = JoinJamRequest


class VoteJamTrackRequest(BaseModel):
    """Payload to vote points for a track in a Jam queue or deck."""

    model_config = ConfigDict(populate_by_name=True)

    track_id: int = Field(alias="musica_id")
    action: str = Field(default="like", alias="acao")
    points: int = Field(default=1, ge=1, le=10)
    user_id: int | None = None


InteragirDeckJamRequest = VoteJamTrackRequest
VotarMusicaJamRequest = VoteJamTrackRequest


class SkipJamTrackRequest(BaseModel):
    """Payload to register a skip vote for the active Jam track."""

    model_config = ConfigDict(populate_by_name=True)

    track_id: int | None = Field(default=None, alias="musica_id")
    user_id: int | None = None


PularMusicaJamRequest = SkipJamTrackRequest


class SaveQueueTrackRequest(BaseModel):
    """Payload to save a Jam queue track to user favorites and optional playlist."""

    model_config = ConfigDict(populate_by_name=True)

    track_id: int = Field(alias="musica_id")
    playlist_id: int | None = None


SalvarFaixaJamRequest = SaveQueueTrackRequest


class JamQueueItemResponse(BaseModel):
    """Public representation of an entry in the Jam playback queue."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    jam_queue_id: int | None = None
    jam_id: int
    track_id: int
    vote_points: int

    @computed_field
    @property
    def jam_fila_id(self) -> int | None:
        return self.jam_queue_id

    @computed_field
    @property
    def musica_id(self) -> int:
        return self.track_id

    @computed_field
    @property
    def pontos_voto(self) -> int:
        return self.vote_points


JamFilaResponse = JamQueueItemResponse


class JamResponse(BaseModel):
    """Public representation of a Jam session."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    jam_id: int | None = None
    host_user_id: int
    room_name: str
    room_code: str
    is_active: bool
    current_track_id: int | None = None
    duration_minutes: int = 60
    max_superlikes: int = 10
    superlikes_used: int = 0
    skip_votes_threshold: int = 3
    accumulated_duration_seconds: int = 0
    deck_source: str = "livre"
    source_playlist_id: int | None = None

    @computed_field
    @property
    def host_usuario_id(self) -> int:
        return self.host_user_id

    @computed_field
    @property
    def nome_sala(self) -> str:
        return self.room_name

    @computed_field
    @property
    def codigo_sala(self) -> str:
        return self.room_code

    @computed_field
    @property
    def is_ativa(self) -> bool:
        return self.is_active

    @computed_field
    @property
    def musica_atual_id(self) -> int | None:
        return self.current_track_id

    @computed_field
    @property
    def duracao_minutos(self) -> int:
        return self.duration_minutes

    @computed_field
    @property
    def limite_superlikes(self) -> int:
        return self.max_superlikes

    @computed_field
    @property
    def superlikes_usados(self) -> int:
        return self.superlikes_used

    @computed_field
    @property
    def meta_votos_pular(self) -> int:
        return self.skip_votes_threshold

    @computed_field
    @property
    def duracao_acumulada_segundos(self) -> int:
        return self.accumulated_duration_seconds

    @computed_field
    @property
    def fonte_deck(self) -> str:
        return self.deck_source

    @computed_field
    @property
    def playlist_origem_id(self) -> int | None:
        return self.source_playlist_id


class JamStateResponse(BaseModel):
    """Public representation of current Jam playback and queue state."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    jam: JamResponse
    current_track: TrackResponse | None = None
    queue: list[JamQueueItemResponse] = Field(default_factory=list)
    skip_votes: int = 0

    @computed_field
    @property
    def musica_atual(self) -> TrackResponse | None:
        return self.current_track

    @computed_field
    @property
    def fila(self) -> list[JamQueueItemResponse]:
        return self.queue

    @computed_field
    @property
    def votos_pular(self) -> int:
        return self.skip_votes


JamEstadoResponse = JamStateResponse


class SkipVoteResponse(BaseModel):
    """Response payload for a participant skip vote."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    jam_id: int
    track_id: int
    votes: int
    threshold: int
    advanced: bool
    is_active: bool
    success: bool = True

    @computed_field
    @property
    def musica_id(self) -> int:
        return self.track_id

    @computed_field
    @property
    def votos(self) -> int:
        return self.votes

    @computed_field
    @property
    def meta(self) -> int:
        return self.threshold

    @computed_field
    @property
    def avancou(self) -> bool:
        return self.advanced

    @computed_field
    @property
    def jam_ativa(self) -> bool:
        return self.is_active


__all__ = [
    "CreateJamRequest",
    "CriarJamRequest",
    "EntrarJamRequest",
    "InteragirDeckJamRequest",
    "JamEstadoResponse",
    "JamFilaResponse",
    "JamQueueItemResponse",
    "JamResponse",
    "JamStateResponse",
    "JoinJamRequest",
    "PularMusicaJamRequest",
    "SalvarFaixaJamRequest",
    "SaveQueueTrackRequest",
    "SkipJamTrackRequest",
    "SkipVoteResponse",
    "VoteJamTrackRequest",
    "VotarMusicaJamRequest",
]
