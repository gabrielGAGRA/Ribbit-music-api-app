"""User profile and membership presentation schemas."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from app.presentation.schemas.admin import PlanResponse
from app.presentation.schemas.auth import UserResponse
from app.presentation.schemas.discovery import InteractionResponse


class UpdateProfileRequest(BaseModel):
    """Payload to revise display name or password credentials."""

    model_config = ConfigDict(populate_by_name=True)

    display_name: str | None = Field(default=None, min_length=2, max_length=50)
    new_password: str | None = Field(default=None, min_length=6)
    current_password: str | None = Field(default=None)

    nome_exibicao: str | None = None
    nova_senha: str | None = None
    senha_atual: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _map_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "nome_exibicao" in data and "display_name" not in data:
                data["display_name"] = data["nome_exibicao"]
            if "nova_senha" in data and "new_password" not in data:
                data["new_password"] = data["nova_senha"]
            if "senha_atual" in data and "current_password" not in data:
                data["current_password"] = data["senha_atual"]
        return data


class LinkSpotifyRequest(BaseModel):
    """Payload to associate a third-party Spotify identifier."""

    user_id: int
    spotify_id: str


class ChangePlanRequest(BaseModel):
    """Payload to switch subscription plan tier."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: int | None = None
    new_plan_id: int

    usuario_id: int | None = None
    novo_plano_id: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _map_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "usuario_id" in data and "user_id" not in data:
                data["user_id"] = data["usuario_id"]
            if "novo_plano_id" in data and "new_plan_id" not in data:
                data["new_plan_id"] = data["novo_plano_id"]
            if "plan_id" in data and "new_plan_id" not in data:
                data["new_plan_id"] = data["plan_id"]
            if "plano_id" in data and "new_plan_id" not in data:
                data["new_plan_id"] = data["plano_id"]
        return data


class BlockedGenresRequest(BaseModel):
    """Payload to update blocked music genres."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: int | None = None
    blocked_genres: str | list[str]

    usuario_id: int | None = None
    generos_bloqueados: str | list[str] | None = None

    @model_validator(mode="before")
    @classmethod
    def _map_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "usuario_id" in data and "user_id" not in data:
                data["user_id"] = data["usuario_id"]
            if "generos_bloqueados" in data and "blocked_genres" not in data:
                data["blocked_genres"] = data["generos_bloqueados"]
        return data


class AddFamilyMemberRequest(BaseModel):
    """Payload to link or provision a dependent profile under a primary account."""

    model_config = ConfigDict(populate_by_name=True)

    primary_account_id: int | None = None
    dependent_user_id: int | None = None
    email: str | None = None
    password: str | None = None
    display_name: str | None = None
    birth_date: str | None = None
    age: int = 0

    # Portuguese aliases
    conta_titular_id: int | None = None
    usuario_dependente_id: int | None = None
    nome_exibicao: str | None = None
    senha: str | None = None
    data_nascimento: str | None = None
    idade: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _map_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "conta_titular_id" in data and "primary_account_id" not in data:
                data["primary_account_id"] = data["conta_titular_id"]
            if "usuario_dependente_id" in data and "dependent_user_id" not in data:
                data["dependent_user_id"] = data["usuario_dependente_id"]
            if "senha" in data and "password" not in data:
                data["password"] = data["senha"]
            if "nome_exibicao" in data and "display_name" not in data:
                data["display_name"] = data["nome_exibicao"]
            if "data_nascimento" in data and "birth_date" not in data:
                data["birth_date"] = data["data_nascimento"]
            if "idade" in data and "age" not in data:
                data["age"] = data["idade"]
        return data


class UserProfileResponse(BaseModel):
    """Composite presentation of a user profile along with active plan details and history."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    user: UserResponse
    plan: PlanResponse
    recent_interactions: list[InteractionResponse] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def usuario(self) -> UserResponse:
        return self.user

    @computed_field  # type: ignore[prop-decorator]
    @property
    def plano(self) -> PlanResponse:
        return self.plan

    @computed_field  # type: ignore[prop-decorator]
    @property
    def interacoes_recentes(self) -> list[InteractionResponse]:
        return self.recent_interactions


class AnnualStatsResponse(BaseModel):
    """Aggregated listening statistics and retrospective metrics for a user."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    estimated_listening_hours: float
    total_likes: int
    top_genres: list[str] = Field(default_factory=list)
    top_artists: list[str] = Field(default_factory=list)


__all__ = [
    "AddFamilyMemberRequest",
    "AnnualStatsResponse",
    "BlockedGenresRequest",
    "ChangePlanRequest",
    "LinkSpotifyRequest",
    "UpdateProfileRequest",
    "UserProfileResponse",
]
