"""Data transfer objects for Jam sessions and queues."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

lazy from app.domain.models.track import Track

if TYPE_CHECKING:
    from app.domain.models.jam import Jam, JamQueueItem


@dataclass(slots=True, frozen=True, kw_only=True)
class CreateJamCommand:
    host_user_id: int
    room_name: str
    duration_minutes: int = 60
    max_superlikes: int = 10
    skip_votes_threshold: int = 3
    deck_source: str = "livre"
    source_playlist_id: int | None = None


@dataclass(slots=True, frozen=True, kw_only=True)
class JoinJamCommand:
    room_code: str
    user_id: int


@dataclass(slots=True, frozen=True, kw_only=True)
class GetJamDeckCommand:
    jam_id: int
    user_id: int
    limit: int = 20
    cursor_id: int | None = None


@dataclass(slots=True, frozen=True, kw_only=True)
class VoteJamTrackCommand:
    jam_id: int
    track_id: int
    user_id: int
    points: int = 1
    action: str = "like"


@dataclass(slots=True, frozen=True, kw_only=True)
class VoteSkipJamTrackCommand:
    jam_id: int
    user_id: int
    track_id: int | None = None


@dataclass(slots=True, frozen=True, kw_only=True)
class SkipVoteResult:
    jam_id: int
    track_id: int
    votes: int
    threshold: int
    advanced: bool
    is_active: bool
    success: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "jam_id": self.jam_id,
            "track_id": self.track_id,
            "musica_id": self.track_id,
            "votes": self.votes,
            "votos": self.votes,
            "threshold": self.threshold,
            "meta": self.threshold,
            "advanced": self.advanced,
            "avancou": self.advanced,
            "is_active": self.is_active,
            "jam_ativa": self.is_active,
            "success": self.success,
        }


@dataclass(slots=True, frozen=True, kw_only=True)
class SaveQueueTrackCommand:
    jam_id: int
    user_id: int
    track_id: int
    playlist_id: int | None = None


@dataclass(slots=True, frozen=True, kw_only=True)
class CloseJamCommand:
    jam_id: int
    host_user_id: int


@dataclass(slots=True, frozen=True, kw_only=True)
class JamStateResult:
    jam: Jam
    current_track: Track | None
    queue: list[JamQueueItem]
    skip_votes: int = 0


__all__ = [
    "CloseJamCommand",
    "CreateJamCommand",
    "GetJamDeckCommand",
    "JamStateResult",
    "JoinJamCommand",
    "SaveQueueTrackCommand",
    "SkipVoteResult",
    "VoteJamTrackCommand",
    "VoteSkipJamTrackCommand",
]
