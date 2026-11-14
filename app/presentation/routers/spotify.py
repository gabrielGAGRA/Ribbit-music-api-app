"""Spotify connection and authorization router."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.ports.services.token_service import TokenServicePort
from app.application.use_cases.spotify import (
    ConnectSpotifyAccountUseCase,
    GetSpotifyAuthorizeUrlUseCase,
)
from app.domain.exceptions import AuthenticationRequiredError
from app.presentation.dependencies import provide, require_user
from app.presentation.schemas.auth import UserResponse
from app.presentation.schemas.spotify import (
    SpotifyAuthorizeUrlResponse,
    SpotifyConnectCallbackRequest,
)

router = APIRouter(prefix="/api/spotify", tags=["Spotify Connection"])


@router.get("/authorize", response_model=SpotifyAuthorizeUrlResponse)
def get_spotify_authorize_url(
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        GetSpotifyAuthorizeUrlUseCase, Depends(provide(GetSpotifyAuthorizeUrlUseCase))
    ],
    token_service: Annotated[TokenServicePort, Depends(provide(TokenServicePort))],
) -> SpotifyAuthorizeUrlResponse:
    state = token_service.create_access_token(user_id=user_id, expires_in_seconds=600)
    url = use_case.execute(state=state)
    return SpotifyAuthorizeUrlResponse(authorization_url=url)


@router.post("/callback", response_model=UserResponse)
def connect_spotify_callback(
    req: SpotifyConnectCallbackRequest,
    user_id: Annotated[int, Depends(require_user)],
    use_case: Annotated[
        ConnectSpotifyAccountUseCase, Depends(provide(ConnectSpotifyAccountUseCase))
    ],
    token_service: Annotated[TokenServicePort, Depends(provide(TokenServicePort))],
) -> UserResponse:
    claims = token_service.decode_access_token(req.state)
    if claims.get("sub") != str(user_id):
        raise AuthenticationRequiredError(
            "Invalid or mismatched Spotify OAuth state parameter."
        )
    user = use_case.execute(user_id=user_id, code=req.code)
    return UserResponse.model_validate(user)


__all__ = ["router"]
