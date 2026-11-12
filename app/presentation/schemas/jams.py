"""Collaborative Jam session presentation schemas."""

from pydantic import BaseModel, ConfigDict, Field

from app.presentation.schemas.playlists import TrackResponse


class CreateJamRequest(BaseModel):
    """Payload to initiate a new collaborative Jam session."""

    model_config = ConfigDict(extra="forbid")

    room_name: str = Field(min_length=1, max_length=100)
    duration_minutes: int = Field(default=60, gt=0)
    max_superlikes: int = Field(default=10, ge=0)
    skip_votes_threshold: int = Field(default=3, gt=0)
    deck_source: str = "free"
    source_playlist_id: int | None = None


CriarJamRequest = CreateJamRequest


class JoinJamRequest(BaseModel):
    """Payload to join an ongoing Jam session via room code."""

    model_config = ConfigDict(extra="forbid")

    room_code: str = Field(
        min_length=1,
        max_length=20,
        pattern=r"^(\d{6}|[A-Za-z0-9_\-]{3,20})$",
    )


EntrarJamRequest = JoinJamRequest


class VoteJamTrackRequest(BaseModel):
    """Payload to vote points for a track in a Jam queue or deck."""

    model_config = ConfigDict(extra="forbid")

    track_id: int
    action: str = "like"
    points: int = Field(default=1, ge=1, le=10)


InteragirDeckJamRequest = VoteJamTrackRequest
VotarMusicaJamRequest = VoteJamTrackRequest


class SkipJamTrackRequest(BaseModel):
    """Payload to register a skip vote for the active Jam track."""

    model_config = ConfigDict(extra="forbid")

    track_id: int | None = None


PularMusicaJamRequest = SkipJamTrackRequest


class SaveQueueTrackRequest(BaseModel):
    """Payload to save a Jam queue track to user favorites and optional playlist."""

    model_config = ConfigDict(extra="forbid")

    track_id: int
    playlist_id: int | None = None


SalvarFaixaJamRequest = SaveQueueTrackRequest


class JamQueueItemResponse(BaseModel):
    """Public representation of an entry in the Jam playback queue."""

    model_config = ConfigDict(from_attributes=True)

    jam_queue_id: int | None = None
    jam_id: int
    track_id: int
    vote_points: int


JamFilaResponse = JamQueueItemResponse


class JamResponse(BaseModel):
    """Public representation of a Jam session."""

    model_config = ConfigDict(from_attributes=True)

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
    deck_source: str = "free"
    source_playlist_id: int | None = None


class JamStateResponse(BaseModel):
    """Public representation of current Jam playback and queue state."""

    model_config = ConfigDict(from_attributes=True)

    jam: JamResponse
    current_track: TrackResponse | None = None
    queue: list[JamQueueItemResponse] = Field(default_factory=list)
    skip_votes: int = 0


JamEstadoResponse = JamStateResponse


class SkipVoteResponse(BaseModel):
    """Response payload for a participant skip vote."""

    model_config = ConfigDict(from_attributes=True)

    jam_id: int
    track_id: int
    votes: int
    threshold: int
    advanced: bool
    is_active: bool
    success: bool = True


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
