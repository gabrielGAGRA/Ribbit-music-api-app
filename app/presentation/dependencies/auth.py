"""Authentication and authorization dependency providers."""

from typing import Annotated

from fastapi import Depends, Header, Query, Request

from app.config import load_settings
from app.domain.exceptions import (
    AuthenticationRequiredError,
    PermissionDeniedError,
)
from app.infrastructure.security.token_service import HMACTokenService
lazy from app.domain.models.user import User

ADMIN_ID_HEADER = "X-Admin-User-Id"
USER_ID_HEADER = "X-User-Id"


def get_admin_id(
    header: Annotated[str | None, Header(alias=ADMIN_ID_HEADER)] = None,
) -> int:
    """Extracts and validates that an administrator ID header is present."""
    if header is None:
        raise AuthenticationRequiredError("Administrator ID header missing.")
    try:
        return int(header)
    except ValueError as exc:
        raise AuthenticationRequiredError("Invalid administrator ID header.") from exc


def _extract_credential_string(
    authorization: str | None,
    x_user_id: str | None,
    user_id: str | None,
) -> str:
    if authorization is not None and authorization.strip():
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        if len(parts) == 1:
            return parts[0]
        raise AuthenticationRequiredError("Invalid user ID.")
    if x_user_id is not None and x_user_id.strip():
        return x_user_id.strip()
    if user_id is not None and user_id.strip():
        return user_id.strip()
    raise AuthenticationRequiredError("Authentication required.")


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
    request: Request = None,  # type: ignore[assignment]
    authorization: Annotated[str | None, Header()] = None,
    x_user_id: Annotated[str | None, Header(alias=USER_ID_HEADER)] = None,
    user_id: Annotated[str | None, Query()] = None,
) -> int:
    """Extracts and validates current user identifier from Bearer token, headers or query."""
    raw_val = _extract_credential_string(authorization, x_user_id, user_id)
    if raw_val.isdigit():
        return int(raw_val)

    if len(raw_val.split(".")) == 3:
        return _decode_token_user_id(raw_val, request)

    try:
        return int(raw_val)
    except ValueError as exc:
        raise AuthenticationRequiredError("Invalid user ID.") from exc


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
    authorization: Annotated[str | None, Header()] = None,
    x_admin_user_id: Annotated[str | None, Header(alias=ADMIN_ID_HEADER)] = None,
    x_user_id: Annotated[str | None, Header(alias=USER_ID_HEADER)] = None,
    admin_id: int | None = None,
) -> int:
    """Enforces admin credential existence and role validation."""
    if admin_id is not None:
        target_id = admin_id
    elif x_admin_user_id is not None and x_admin_user_id.strip():
        target_id = get_admin_id(header=x_admin_user_id)
    else:
        target_id = get_current_user_id(
            request=request,
            authorization=authorization,
            x_user_id=x_user_id,
        )

    admin_user = request.app.state.container.user_repo.find_by_id(target_id)
    if not admin_user:
        raise AuthenticationRequiredError("Administrator user not found.")
    if not admin_user.is_admin:
        raise PermissionDeniedError("Access restricted to administrators.")
    request.state.admin_user = admin_user
    request.state.user = admin_user
    return target_id


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
    "ADMIN_ID_HEADER",
    "USER_ID_HEADER",
    "get_admin_id",
    "get_current_user",
    "get_current_user_id",
    "require_admin",
    "require_user",
]
