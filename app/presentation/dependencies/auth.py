"""Authentication and authorization dependency providers."""

from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import load_settings
from app.domain.exceptions import (
    AuthenticationRequiredError,
    PermissionDeniedError,
)
from app.infrastructure.security.token_service import HMACTokenService
lazy from app.domain.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def _decode_token_user_id(raw_val: str, request: Request | None) -> int:
    if (
        request is not None
        and hasattr(request, "app")
        and hasattr(request.app.state, "container")
        and hasattr(request.app.state.container, "token_service")
    ):
        token_service = request.app.state.container.token_service
    elif (
        request is not None
        and hasattr(request, "app")
        and hasattr(request.app.state, "settings")
    ):
        token_service = HMACTokenService(
            secret_key=request.app.state.settings.secret_key
        )
    else:
        token_service = HMACTokenService(secret_key=load_settings().secret_key)

    payload = token_service.decode_access_token(raw_val)
    sub = payload.get("sub")
    if sub is None:
        raise AuthenticationRequiredError("Token missing subject claim.")
    try:
        return int(sub)
    except ValueError as exc:
        raise AuthenticationRequiredError("Invalid user ID in token subject.") from exc


def get_current_user_id(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
    authorization: Annotated[str | None, Header(include_in_schema=False)] = None,
) -> int:
    """Extracts and validates the current user ID from a Bearer access token."""
    if credentials is not None:
        if credentials.scheme.lower() != "bearer":
            raise AuthenticationRequiredError("A valid bearer token is required.")
        token = credentials.credentials
    elif authorization is not None:
        scheme, separator, token = authorization.strip().partition(" ")
        if scheme.lower() != "bearer" or not separator:
            raise AuthenticationRequiredError("A valid bearer token is required.")
    else:
        raise AuthenticationRequiredError("Authentication required.")

    if not token or any(character.isspace() for character in token):
        raise AuthenticationRequiredError("A valid bearer token is required.")

    user_id = _decode_token_user_id(token, request)
    if user_id <= 0:
        raise AuthenticationRequiredError("Invalid user ID in token subject.")
    return user_id


def require_user(
    request: Request,
    user_id: Annotated[int, Depends(get_current_user_id)],
) -> int:
    """Enforces user credential existence and validation."""
    user = request.app.state.container.user_repo.find_by_id(user_id)
    if not user:
        raise AuthenticationRequiredError("User not found.")
    request.state.user = user
    return user_id


def require_admin(
    request: Request,
    admin_id: Annotated[int, Depends(get_current_user_id)],
) -> int:
    """Enforces admin credential existence and role validation."""
    admin_user = request.app.state.container.user_repo.find_by_id(admin_id)
    if not admin_user:
        raise AuthenticationRequiredError("Administrator user not found.")
    if not admin_user.is_admin:
        raise PermissionDeniedError("Access restricted to administrators.")
    request.state.admin_user = admin_user
    request.state.user = admin_user
    return admin_id


def get_current_user(
    request: Request,
    user_id: Annotated[int, Depends(require_user)],
) -> User:
    """Returns the authenticated domain User entity."""
    user = getattr(request.state, "user", None)
    if user is not None:
        return user
    found_user = request.app.state.container.user_repo.find_by_id(user_id)
    if not found_user:
        raise AuthenticationRequiredError("User not found.")
    return found_user


__all__ = [
    "get_current_user",
    "get_current_user_id",
    "require_admin",
    "require_user",
]
