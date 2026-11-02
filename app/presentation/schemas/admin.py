"""Administrative presentation schemas."""

from pydantic import BaseModel, ConfigDict, Field, computed_field


class PlanResponse(BaseModel):
    """Public representation of a subscription plan."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    plan_id: int
    name: str
    monthly_price: float
    max_profiles: int

    @computed_field
    def plano_id(self) -> int:
        return self.plan_id

    @computed_field
    def nome(self) -> str:
        return self.name

    @computed_field
    def preco_mensal(self) -> float:
        return self.monthly_price

    @computed_field
    def max_perfis(self) -> int:
        return self.max_profiles


class UpdatePlanAdminRequest(BaseModel):
    """Payload for modifying an existing subscription plan tier."""

    new_price: float | None = None
    monthly_price: float | None = None
    new_name: str | None = None
    name: str | None = None
    max_profiles: int | None = None

    novo_preco: float | None = None
    preco_mensal: float | None = None
    novo_nome: str | None = None
    nome: str | None = None
    max_perfis: int | None = None

    def resolved_price(self) -> float | None:
        if self.new_price is not None:
            return self.new_price
        if self.monthly_price is not None:
            return self.monthly_price
        if self.novo_preco is not None:
            return self.novo_preco
        if self.preco_mensal is not None:
            return self.preco_mensal
        return None

    def resolved_name(self) -> str | None:
        if self.new_name is not None:
            return self.new_name
        if self.name is not None:
            return self.name
        if self.novo_nome is not None:
            return self.novo_nome
        if self.nome is not None:
            return self.nome
        return None

    def resolved_max_profiles(self) -> int | None:
        return self.max_profiles if self.max_profiles is not None else self.max_perfis


class UpdateTrackExplicitRequest(BaseModel):
    """Payload to alter a track explicit advisory status."""

    explicit: bool


class BlockTrackRequest(BaseModel):
    """Payload for toggling track block state."""

    blocked: bool | None = None
    bloqueada: bool | None = None

    def is_blocked(self) -> bool:
        if self.blocked is not None:
            return self.blocked
        if self.bloqueada is not None:
            return self.bloqueada
        return True


class TrackBlockResponse(BaseModel):
    """Response returned upon blocking or unblocking a catalog track."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    track_id: int | None = None
    blocked: bool

    @computed_field
    def musica_id(self) -> int | None:
        return self.track_id

    @computed_field
    def bloqueada(self) -> bool:
        return self.blocked


class TrackExplicitResponse(BaseModel):
    """Response returned upon updating explicit status on a track."""

    model_config = ConfigDict(from_attributes=True)

    track_id: int
    explicit: bool


class ExecutiveDashboardResponse(BaseModel):
    """Aggregated platform performance and subscription revenue metrics."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    total_users: int
    estimated_net_revenue: float
    users_by_plan: dict[str, int] = Field(default_factory=dict)
    revenue_by_plan: dict[str, float] = Field(default_factory=dict)

    @computed_field
    def total_usuarios(self) -> int:
        return self.total_users

    @computed_field
    def receita_liquida_estimada(self) -> float:
        return self.estimated_net_revenue

    @computed_field
    def usuarios_por_plano(self) -> dict[str, int]:
        return self.users_by_plan

    @computed_field
    def receita_por_plano(self) -> dict[str, float]:
        return self.revenue_by_plan


class AudienceReportResponse(BaseModel):
    """Aggregate volume counts of registered users, catalog tracks, and blocked genres."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    total_users: int
    total_tracks: int
    active_tracks: int
    blocked_genres: dict[str, int] = Field(default_factory=dict)

    @computed_field
    def total_usuarios(self) -> int:
        return self.total_users

    @computed_field
    def total_musicas(self) -> int:
        return self.total_tracks

    @computed_field
    def musicas_ativas(self) -> int:
        return self.active_tracks

    @computed_field
    def generos_bloqueados(self) -> dict[str, int]:
        return self.blocked_genres


class UserPlanSummaryResponse(BaseModel):
    """Summary overview of a registered user and their assigned subscription plan."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int | None = None
    email: str
    display_name: str
    age: int
    plan_name: str
    is_admin: bool


class UpdateAdminRoleRequest(BaseModel):
    """Payload to alter a user's administrator privilege status."""

    is_admin: bool


class CompactCatalogResponse(BaseModel):
    """Response returned upon consolidating micro-deltas into the main catalog."""

    model_config = ConfigDict(from_attributes=True)

    new_version: int
    message: str


class SyncCatalogVersionResponse(BaseModel):
    """Response returned upon checking and syncing local database against remote catalog version."""

    model_config = ConfigDict(from_attributes=True)

    synced: bool
    version: int
    message: str


class UpdateTrackGenreRequest(BaseModel):
    """Payload to alter a track genre."""

    genre: str


class TrackGenreResponse(BaseModel):
    """Response returned upon updating genre on a track."""

    model_config = ConfigDict(from_attributes=True)

    track_id: int
    genre: str


__all__ = [
    "AudienceReportResponse",
    "BlockTrackRequest",
    "CompactCatalogResponse",
    "ExecutiveDashboardResponse",
    "PlanResponse",
    "SyncCatalogVersionResponse",
    "TrackBlockResponse",
    "TrackExplicitResponse",
    "TrackGenreResponse",
    "UpdateAdminRoleRequest",
    "UpdatePlanAdminRequest",
    "UpdateTrackExplicitRequest",
    "UpdateTrackGenreRequest",
    "UserPlanSummaryResponse",
]
