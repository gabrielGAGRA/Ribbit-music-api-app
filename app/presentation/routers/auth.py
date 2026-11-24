"""Authentication and registration router."""

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse

from app.application.dtos import (
    AuthenticateUserCommand,
    AuthenticateWithGoogleCommand,
    RegisterUserCommand,
)
from app.application.ports.repositories.user_repository import UserRepositoryPort
from app.application.ports.services.token_service import TokenServicePort
from app.application.use_cases.auth import (
    AuthenticateUserUseCase,
    AuthenticateWithGoogleUseCase,
    CompleteGoogleOAuthUseCase,
    GetGoogleAuthorizeUrlUseCase,
    RegisterUserUseCase,
)
from app.config import Settings
from app.domain.exceptions import (
    AuthenticationRequiredError,
    CustomError,
    EntityNotFoundError,
    ExternalServiceError,
)
from app.presentation.dependencies import provide, provide_optional
from app.presentation.schemas import (
    AuthResponse,
    GoogleAuthorizeUrlResponse,
    GoogleClientIdResponse,
    GoogleLoginRequest,
    LoginRequest,
    RegisterUserRequest,
    UserResponse,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _sign_cookie_payload(payload: dict[str, Any], secret_key: str) -> str:
    payload_json = json.dumps(payload, separators=(",", ":"))
    payload_b64 = (
        base64.urlsafe_b64encode(payload_json.encode("utf-8"))
        .rstrip(b"=")
        .decode("ascii")
    )
    sig = (
        base64.urlsafe_b64encode(
            hmac.new(
                secret_key.encode("utf-8"),
                payload_b64.encode("ascii"),
                hashlib.sha256,
            ).digest()
        )
        .rstrip(b"=")
        .decode("ascii")
    )
    return f"{payload_b64}.{sig}"


def _verify_cookie_payload(token: str | None, secret_key: str) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None
    payload_b64, sig = token.split(".", 1)
    expected_sig = (
        base64.urlsafe_b64encode(
            hmac.new(
                secret_key.encode("utf-8"),
                payload_b64.encode("ascii"),
                hashlib.sha256,
            ).digest()
        )
        .rstrip(b"=")
        .decode("ascii")
    )
    if not hmac.compare_digest(expected_sig, sig):
        return None
    try:
        padding = "=" * ((4 - len(payload_b64) % 4) % 4)
        payload_bytes = base64.urlsafe_b64decode(
            (payload_b64 + padding).encode("ascii")
        )
        payload = json.loads(payload_bytes.decode("utf-8"))
    except ValueError, TypeError, json.JSONDecodeError:
        return None
    else:
        if not isinstance(payload, dict):
            return None
        exp = payload.get("exp")
        if exp is not None and int(exp) < int(time.time()):
            return None
        return payload


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    req: RegisterUserRequest,
    use_case: Annotated[RegisterUserUseCase, Depends(provide(RegisterUserUseCase))],
    token_service: Annotated[
        TokenServicePort,
        Depends(provide(TokenServicePort)),
    ],
) -> AuthResponse:
    user = use_case.execute(
        RegisterUserCommand(
            email=req.email,
            password=req.password,
            display_name=req.display_name,
            age=req.age,
            plan_id=req.plan_id,
            birth_date=req.birth_date,
            blocked_genres=tuple(req.blocked_genres),
            favorite_genres=tuple(req.favorite_genres),
            preferred_theme=req.preferred_theme,
        )
    )
    if user.user_id is None:
        raise RuntimeError("Registered user is missing its persisted ID.")
    return AuthResponse(
        access_token=token_service.create_access_token(
            user_id=user.user_id, is_admin=user.is_admin
        ),
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=AuthResponse)
def login(
    req: LoginRequest,
    use_case: Annotated[
        AuthenticateUserUseCase, Depends(provide(AuthenticateUserUseCase))
    ],
) -> AuthResponse:
    result = use_case.execute(
        AuthenticateUserCommand(email=req.email, password=req.password)
    )
    return AuthResponse(
        access_token=result.access_token,
        user=UserResponse.model_validate(result.user),
    )


@router.post("/google", response_model=AuthResponse)
def login_with_google(
    req: GoogleLoginRequest,
    use_case: Annotated[
        AuthenticateWithGoogleUseCase, Depends(provide(AuthenticateWithGoogleUseCase))
    ],
) -> AuthResponse:
    result = use_case.execute(AuthenticateWithGoogleCommand(id_token=req.id_token))
    return AuthResponse(
        access_token=result.access_token,
        user=UserResponse.model_validate(result.user),
    )


@router.get("/google/client-id", response_model=GoogleClientIdResponse)
def get_google_client_id(
    settings: Annotated[Settings, Depends(provide(Settings))],
) -> GoogleClientIdResponse:
    return GoogleClientIdResponse(client_id=settings.google_client_id)


@router.get("/google/authorize", response_model=GoogleAuthorizeUrlResponse)
def google_authorize(
    response: Response,
    settings: Annotated[Settings, Depends(provide(Settings))],
    use_case: Annotated[
        GetGoogleAuthorizeUrlUseCase | None,
        Depends(provide_optional(GetGoogleAuthorizeUrlUseCase)),
    ] = None,
) -> GoogleAuthorizeUrlResponse:
    if use_case is None:
        raise ExternalServiceError("Google OAuth 2.0 is not configured on the server.")

    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    state_nonce = secrets.token_urlsafe(32)

    state_payload = {
        "state": state_nonce,
        "code_verifier": code_verifier,
        "exp": int(time.time()) + 600,
    }
    cookie_token = _sign_cookie_payload(state_payload, settings.secret_key)
    response.set_cookie(
        key="ribbit_google_oauth_state",
        value=cookie_token,
        max_age=600,
        httponly=True,
        samesite="lax",
        path="/api/auth/google",
    )

    auth_url = use_case.execute(state=state_nonce, code_challenge=code_challenge)
    return GoogleAuthorizeUrlResponse(authorization_url=auth_url)


def _build_google_handoff_redirect(
    target_url: str,
    payload_data: dict[str, Any],
    secret_key: str,
    max_age: int,
) -> RedirectResponse:
    handoff_token = _sign_cookie_payload(payload_data, secret_key)
    res = RedirectResponse(
        url=target_url,
        status_code=status.HTTP_302_FOUND,
    )
    res.delete_cookie(key="ribbit_google_oauth_state", path="/api/auth/google")
    res.set_cookie(
        key="ribbit_google_oauth_handoff",
        value=handoff_token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        path="/api/auth/google",
    )
    return res


@router.get("/google/callback")
def google_callback(
    request: Request,
    settings: Annotated[Settings, Depends(provide(Settings))],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    complete_use_case: Annotated[
        CompleteGoogleOAuthUseCase | None,
        Depends(provide_optional(CompleteGoogleOAuthUseCase)),
    ] = None,
) -> RedirectResponse:
    base_target = settings.google_frontend_redirect_url.rstrip("/") or "/"
    separator = "&" if "?" in base_target else "?"

    def _err_redirect(reason: str) -> RedirectResponse:
        res = RedirectResponse(
            url=f"{base_target}{separator}google_auth_error={quote(reason)}",
            status_code=status.HTTP_302_FOUND,
        )
        res.delete_cookie(key="ribbit_google_oauth_state", path="/api/auth/google")
        return res

    if error:
        return _err_redirect(error)

    if not code or not state:
        return _err_redirect("missing_parameters")

    if complete_use_case is None:
        return _err_redirect("oauth_not_configured")

    raw_cookie = request.cookies.get("ribbit_google_oauth_state")
    payload = _verify_cookie_payload(raw_cookie, settings.secret_key)
    if not payload or payload.get("state") != state:
        return _err_redirect("invalid_state")

    code_verifier = payload.get("code_verifier")
    try:
        result = complete_use_case.execute(code=code, code_verifier=code_verifier)
    except EntityNotFoundError as exc:
        if exc.details.get("registration_required"):
            return _build_google_handoff_redirect(
                f"{base_target}{separator}google_auth=register",
                {
                    "registration_required": True,
                    "email": exc.details.get("email", ""),
                    "display_name": exc.details.get("display_name", ""),
                    "exp": int(time.time()) + 300,
                },
                settings.secret_key,
                max_age=300,
            )
        return _err_redirect("exchange_failed")
    except Exception:  # noqa: BLE001
        logging.getLogger("app.presentation.routers.auth").warning(
            "Google OAuth callback exchange failed",
            exc_info=True,
        )
        return _err_redirect("exchange_failed")

    user_id = result.user.user_id
    if user_id is None:
        return _err_redirect("user_persisted_id_missing")

    return _build_google_handoff_redirect(
        f"{base_target}{separator}google_auth=complete",
        {"user_id": user_id, "exp": int(time.time()) + 120},
        settings.secret_key,
        max_age=120,
    )


def _error_json_clearing_handoff(exc: CustomError, status_code: int) -> JSONResponse:
    res = JSONResponse(
        status_code=status_code,
        content={
            "error": exc.name,
            "message": exc.message,
            "details": exc.details,
        },
    )
    res.delete_cookie(key="ribbit_google_oauth_handoff", path="/api/auth/google")
    return res


@router.post("/google/session", response_model=AuthResponse)
def google_session(
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(provide(Settings))],
    user_repo: Annotated[UserRepositoryPort, Depends(provide(UserRepositoryPort))],
    token_service: Annotated[TokenServicePort, Depends(provide(TokenServicePort))],
) -> AuthResponse | JSONResponse:
    handoff_cookie = request.cookies.get("ribbit_google_oauth_handoff")
    response.delete_cookie(key="ribbit_google_oauth_handoff", path="/api/auth/google")

    payload = _verify_cookie_payload(handoff_cookie, settings.secret_key)
    if not payload:
        return _error_json_clearing_handoff(
            AuthenticationRequiredError("No valid Google OAuth session found."),
            status.HTTP_401_UNAUTHORIZED,
        )

    if payload.get("registration_required"):
        return _error_json_clearing_handoff(
            EntityNotFoundError(
                "Nenhuma conta Ribbit encontrada para este e-mail Google. Conclua seu cadastro.",
                entity_name="User",
                details={
                    "registration_required": True,
                    "email": str(payload.get("email") or ""),
                    "display_name": str(payload.get("display_name") or ""),
                },
            ),
            status.HTTP_404_NOT_FOUND,
        )

    if not payload.get("user_id"):
        return _error_json_clearing_handoff(
            AuthenticationRequiredError("No valid Google OAuth session found."),
            status.HTTP_401_UNAUTHORIZED,
        )

    user = user_repo.find_by_id(int(payload["user_id"]))
    if not user or user.user_id is None:
        return _error_json_clearing_handoff(
            AuthenticationRequiredError("Authenticated user not found."),
            status.HTTP_401_UNAUTHORIZED,
        )

    token = token_service.create_access_token(
        user_id=user.user_id, is_admin=user.is_admin
    )
    return AuthResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


__all__ = ["router"]
