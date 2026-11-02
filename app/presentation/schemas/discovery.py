"""Discovery and interaction presentation schemas."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

_ACTION_SYNONYMS: dict[str, Literal["like", "superlike", "dislike"]] = {
    "curtida": "like",
    "curtir": "like",
    "gostei": "like",
    "descurtida": "dislike",
    "descurtir": "dislike",
    "pular": "dislike",
    "dispensar": "dislike",
    "supercurtida": "superlike",
    "supercurtir": "superlike",
    "amei": "superlike",
    "rejeitada": "dislike",
    "rejeitar": "dislike",
}


class InteractionRequest(BaseModel):
    """Payload to record a swipe interaction on a track."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: int | None = None
    track_id: int
    action: Literal["like", "superlike", "dislike"]
    usuario_id: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _map_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "musica_id" in data and "track_id" not in data:
                data["track_id"] = data["musica_id"]
            if "usuario_id" in data and "user_id" not in data:
                data["user_id"] = data["usuario_id"]
            action_val = data.get("acao", data.get("action"))
            if action_val and isinstance(action_val, str):
                normalized = action_val.strip().lower()
                data["action"] = _ACTION_SYNONYMS.get(normalized, normalized)
        return data


class ChangeInteractionRequest(BaseModel):
    """Payload to modify an existing swipe interaction."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: int
    track_id: int
    new_action: Literal["like", "superlike", "dislike"]

    @model_validator(mode="before")
    @classmethod
    def _map_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "musica_id" in data and "track_id" not in data:
                data["track_id"] = data["musica_id"]
            if "usuario_id" in data and "user_id" not in data:
                data["user_id"] = data["usuario_id"]
            action_val = data.get("nova_acao", data.get("acao", data.get("new_action")))
            if action_val and isinstance(action_val, str):
                normalized = action_val.strip().lower()
                data["new_action"] = _ACTION_SYNONYMS.get(normalized, normalized)
        return data


class InteractionResponse(BaseModel):
    """Public representation of an interaction event."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    interaction_id: int
    user_id: int
    track_id: int
    action: str
    created_at: datetime | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def id(self) -> int:
        return self.interaction_id

    @computed_field  # type: ignore[prop-decorator]
    @property
    def usuario_id(self) -> int:
        return self.user_id

    @computed_field  # type: ignore[prop-decorator]
    @property
    def musica_id(self) -> int:
        return self.track_id

    @computed_field  # type: ignore[prop-decorator]
    @property
    def acao(self) -> str:
        return self.action


class TrackSearchQuery(BaseModel):
    """Query parameters for track catalog searches."""

    query: str | None = None
    artist: str | None = None
    album: str | None = None
    genre: str | None = None
    year: int | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


__all__ = [
    "ChangeInteractionRequest",
    "InteractionRequest",
    "InteractionResponse",
    "TrackSearchQuery",
]
