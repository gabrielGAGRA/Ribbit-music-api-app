"""Authentication and user account presentation schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class UserResponse(BaseModel):
    """Public representation of an authenticated user profile."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    user_id: int
    email: str
    display_name: str
    age: int
    plan_id: int
    birth_date: str | None = None
    spotify_id: str | None = None
    primary_account_id: int | None = None
    blocked_genres: list[str] | frozenset[str] | set[str] | None = None
    is_admin: bool = False
    created_at: datetime | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def id(self) -> int:
        return self.user_id

    @computed_field  # type: ignore[prop-decorator]
    @property
    def usuario_id(self) -> int:
        return self.user_id

    @computed_field  # type: ignore[prop-decorator]
    @property
    def nome_exibicao(self) -> str:
        return self.display_name

    @computed_field  # type: ignore[prop-decorator]
    @property
    def idade(self) -> int:
        return self.age

    @computed_field  # type: ignore[prop-decorator]
    @property
    def plano_id(self) -> int:
        return self.plan_id

    @computed_field  # type: ignore[prop-decorator]
    @property
    def data_nascimento(self) -> str | None:
        return self.birth_date


class RegisterUserRequest(BaseModel):
    """Payload for registering a new user."""

    model_config = ConfigDict(populate_by_name=True)

    email: str
    password: str = Field(min_length=6)
    display_name: str = Field(min_length=2, max_length=50)
    age: int = Field(default=0, ge=0)
    plan_id: int | None = None
    birth_date: str | None = None

    # Portuguese alias support
    data_nascimento: str | None = None
    senha: str | None = None
    nome_exibicao: str | None = None
    idade: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _map_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "senha" in data and "password" not in data:
                data["password"] = data["senha"]
            if "nome_exibicao" in data and "display_name" not in data:
                data["display_name"] = data["nome_exibicao"]
            if "data_nascimento" in data and "birth_date" not in data:
                data["birth_date"] = data["data_nascimento"]
            if "idade" in data and "age" not in data:
                data["age"] = data["idade"]
            if "plano_id" in data and "plan_id" not in data:
                data["plan_id"] = data["plano_id"]
        return data


class LoginRequest(BaseModel):
    """Credentials payload for user authentication."""

    model_config = ConfigDict(populate_by_name=True)

    email: str
    password: str
    senha: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _map_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict) and "senha" in data and "password" not in data:
            data["password"] = data["senha"]
        return data


class AuthResponse(BaseModel):
    """Authentication response payload containing token and user details."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    access_token: str
    token_type: str = "bearer"  # noqa: S105
    user: UserResponse

    @computed_field  # type: ignore[prop-decorator]
    @property
    def token(self) -> str:
        return self.access_token

    @computed_field  # type: ignore[prop-decorator]
    @property
    def usuario(self) -> UserResponse:
        return self.user

    @computed_field  # type: ignore[prop-decorator]
    @property
    def usuario_id(self) -> int:
        return self.user.user_id

    @computed_field  # type: ignore[prop-decorator]
    @property
    def user_id(self) -> int:
        return self.user.user_id

    def __getattr__(self, name: str) -> Any:
        if hasattr(self.user, name):
            return getattr(self.user, name)
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )


__all__ = [
    "AuthResponse",
    "LoginRequest",
    "RegisterUserRequest",
    "UserResponse",
]
