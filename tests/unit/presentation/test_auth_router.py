"""Unit tests for authentication router functions."""

from unittest.mock import MagicMock

lazy import pytest

from app.application.dtos import AuthenticateUserCommand, RegisterUserCommand
from app.application.dtos.auth_dtos import AuthResult
from app.application.ports.services.token_service import TokenServicePort
from app.application.use_cases.auth import (
    AuthenticateUserUseCase,
    RegisterUserUseCase,
)
from app.domain.models import User
from app.presentation.routers.auth import login, register
from app.presentation.schemas import LoginRequest, RegisterUserRequest


def test_register_issues_bearer_token_and_returns_user() -> None:
    mock_use_case = MagicMock(spec=RegisterUserUseCase)
    token_service = MagicMock(spec=TokenServicePort)
    user = User(
        user_id=1,
        email="new@ribbit.com",
        password_hash="hashed",
        display_name="New Frog",
        age=21,
        plan_id=2,
        blocked_genres=["Jazz"],
    )
    mock_use_case.execute.return_value = user
    token_service.create_access_token.return_value = "signed-token"
    req = RegisterUserRequest(
        email="new@ribbit.com",
        password="test-password",
        display_name="New Frog",
        age=21,
        plan_id=2,
        blocked_genres=["Jazz"],
    )

    res = register(req=req, use_case=mock_use_case, token_service=token_service)

    assert res.access_token == "signed-token"
    assert res.token_type == "bearer"
    assert res.user.user_id == 1
    token_service.create_access_token.assert_called_once_with(user_id=1, is_admin=False)
    mock_use_case.execute.assert_called_once_with(
        RegisterUserCommand(
            email="new@ribbit.com",
            password="test-password",
            display_name="New Frog",
            age=21,
            plan_id=2,
            birth_date=None,
            blocked_genres=("Jazz",),
        )
    )


def test_login_returns_authentication_result() -> None:
    mock_use_case = MagicMock(spec=AuthenticateUserUseCase)
    user = User(
        user_id=5,
        email="member@ribbit.com",
        password_hash="hashed",
        display_name="Member",
        age=28,
        plan_id=1,
    )
    mock_use_case.execute.return_value = AuthResult(
        user=user,
        access_token="signed-token",
    )
    req = LoginRequest(email="member@ribbit.com", password="test-password")

    res = login(req=req, use_case=mock_use_case)

    assert res.access_token == "signed-token"
    assert res.token_type == "bearer"
    assert res.user.user_id == 5
    mock_use_case.execute.assert_called_once_with(
        AuthenticateUserCommand(
            email="member@ribbit.com",
            password="test-password",
        )
    )


def test_auth_router_exposes_only_english_routes() -> None:
    from app.presentation.routers.auth import router

    paths = [getattr(route, "path", None) for route in router.routes]
    assert paths == [
        "/api/auth/register",
        "/api/auth/login",
        "/api/auth/google",
        "/api/auth/google/client-id",
        "/api/auth/google/authorize",
        "/api/auth/google/callback",
        "/api/auth/google/session",
    ]


def test_auth_router_get_google_client_id() -> None:
    from app.config import Settings
    from app.presentation.routers.auth import get_google_client_id

    response = get_google_client_id(
        settings=Settings(google_client_id="my-google-client-id")
    )

    assert response.client_id == "my-google-client-id"


def test_http_get_google_client_id_resolves_settings_via_di() -> None:
    import sqlite3

    from app.composition import create_app
    from app.config import Settings
    from tests.integration.test_client import TestClient

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        app = create_app(
            settings=Settings(
                database_path=":memory:",
                password_hash_iterations=1_000,
                google_client_id="di-client-id.apps.googleusercontent.com",
            ),
            connection=conn,
        )
        client = TestClient(app)

        response = client.get("/api/auth/google/client-id")

        assert response.status_code == 200
        assert response.json() == {
            "client_id": "di-client-id.apps.googleusercontent.com"
        }
    finally:
        conn.close()


def test_http_get_google_client_id_uses_only_injected_settings_without_reloading_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sqlite3

    from app.composition import create_app
    from app.config import Settings
    from tests.integration.test_client import TestClient

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("RIBBIT_SECRET_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "env-client.apps.googleusercontent.com")

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        app = create_app(
            settings=Settings(
                database_path=":memory:",
                password_hash_iterations=1_000,
                environment="production",
                secret_key="p" * 40,
                google_client_id=None,
            ),
            connection=conn,
        )
        client = TestClient(app)

        response = client.get("/api/auth/google/client-id")

        assert response.status_code == 200
        assert response.json() == {"client_id": None}
    finally:
        conn.close()


def test_auth_router_google_login_success() -> None:
    from app.application.dtos.auth_dtos import (
        AuthenticateWithGoogleCommand,
        AuthResult,
    )
    from app.application.use_cases.auth.authenticate_with_google import (
        AuthenticateWithGoogleUseCase,
    )
    from app.presentation.routers.auth import login_with_google
    from app.presentation.schemas.auth import GoogleLoginRequest

    mock_use_case = MagicMock(spec=AuthenticateWithGoogleUseCase)
    mock_use_case.execute.return_value = AuthResult(
        user=User(
            user_id=12,
            email="google@ribbit.com",
            password_hash="oauth_dummy",
            display_name="Google User",
            plan_id=1,
        ),
        access_token="google_access_jwt",
    )

    response = login_with_google(
        req=GoogleLoginRequest(id_token="valid_id_token"),
        use_case=mock_use_case,
    )

    assert response.access_token == "google_access_jwt"
    assert response.user.email == "google@ribbit.com"
    mock_use_case.execute.assert_called_once_with(
        AuthenticateWithGoogleCommand(id_token="valid_id_token")
    )


def test_google_authorize_endpoint() -> None:
    from fastapi import Response

    from app.application.use_cases.auth.get_google_authorize_url import (
        GetGoogleAuthorizeUrlUseCase,
    )
    from app.config import Settings
    from app.domain.exceptions import ExternalServiceError
    from app.presentation.routers.auth import google_authorize

    settings = Settings(secret_key="secret-key-1234")
    response = Response()

    with pytest.raises(ExternalServiceError, match="not configured"):
        google_authorize(response=response, settings=settings, use_case=None)

    mock_uc = MagicMock(spec=GetGoogleAuthorizeUrlUseCase)
    mock_uc.execute.return_value = "https://accounts.google.com/auth?sample=1"

    auth_res = google_authorize(response=response, settings=settings, use_case=mock_uc)
    assert auth_res.authorization_url == "https://accounts.google.com/auth?sample=1"
    assert "ribbit_google_oauth_state" in response.headers.get("set-cookie", "")


def test_google_callback_endpoint() -> None:
    from fastapi import Request

    from app.application.dtos.auth_dtos import AuthResult
    from app.application.use_cases.auth.complete_google_oauth import (
        CompleteGoogleOAuthUseCase,
    )
    from app.config import Settings
    from app.domain.models.user import User
    from app.presentation.routers.auth import _sign_cookie_payload, google_callback

    settings = Settings(
        secret_key="secret-key-1234", google_frontend_redirect_url="/custom-login"
    )

    # 1. Error param from Google
    req_err = Request({"type": "http", "headers": []})
    res_err = google_callback(request=req_err, settings=settings, error="access_denied")
    assert res_err.status_code == 302
    assert (
        "/custom-login?google_auth_error=access_denied" in res_err.headers["location"]
    )

    # 2. Missing parameters
    res_missing = google_callback(
        request=req_err, settings=settings, code=None, state=None
    )
    assert (
        "/custom-login?google_auth_error=missing_parameters"
        in res_missing.headers["location"]
    )

    # 3. Invalid state cookie
    req_bad_state = Request(
        {
            "type": "http",
            "headers": [(b"cookie", b"ribbit_google_oauth_state=bad_cookie")],
        }
    )
    res_bad_state = google_callback(
        request=req_bad_state,
        settings=settings,
        code="code123",
        state="state123",
        complete_use_case=MagicMock(spec=CompleteGoogleOAuthUseCase),
    )
    assert (
        "/custom-login?google_auth_error=invalid_state"
        in res_bad_state.headers["location"]
    )

    # 4. Successful exchange
    valid_state_token = _sign_cookie_payload(
        {"state": "state123", "code_verifier": "verifier123", "exp": 9999999999},
        secret_key="secret-key-1234",
    )
    req_ok = Request(
        {
            "type": "http",
            "headers": [
                (
                    b"cookie",
                    f"ribbit_google_oauth_state={valid_state_token}".encode("ascii"),
                )
            ],
        }
    )
    mock_complete_uc = MagicMock(spec=CompleteGoogleOAuthUseCase)
    mock_complete_uc.execute.return_value = AuthResult(
        user=User(
            user_id=88,
            email="google@ribbit.com",
            password_hash="oauth",
            display_name="Google User",
            plan_id=1,
        ),
        access_token="tok",
    )

    res_ok = google_callback(
        request=req_ok,
        settings=settings,
        code="code123",
        state="state123",
        complete_use_case=mock_complete_uc,
    )
    assert res_ok.status_code == 302
    assert "/custom-login?google_auth=complete" in res_ok.headers["location"]
    set_cookie_headers = res_ok.headers.getlist("set-cookie")
    assert any("ribbit_google_oauth_handoff" in h for h in set_cookie_headers)
    assert any("ribbit_google_oauth_state" in h for h in set_cookie_headers)
    mock_complete_uc.execute.assert_called_once_with(
        code="code123", code_verifier="verifier123"
    )


def test_google_session_endpoint() -> None:
    from fastapi import Request, Response

    from app.application.ports.repositories.user_repository import UserRepositoryPort
    from app.application.ports.services.token_service import TokenServicePort
    from app.config import Settings
    from app.domain.models.user import User
    from app.presentation.routers.auth import _sign_cookie_payload, google_session

    settings = Settings(secret_key="secret-key-1234")
    user_repo = MagicMock(spec=UserRepositoryPort)
    token_service = MagicMock(spec=TokenServicePort)

    req_empty = Request({"type": "http", "headers": []})
    resp = Response()

    empty_res = google_session(
        request=req_empty,
        response=resp,
        settings=settings,
        user_repo=user_repo,
        token_service=token_service,
    )
    assert empty_res.status_code == 401
    assert b"No valid Google OAuth session" in empty_res.body
    assert "ribbit_google_oauth_handoff" in empty_res.headers.get("set-cookie", "")

    valid_handoff = _sign_cookie_payload(
        {"user_id": 99, "exp": 9999999999}, secret_key="secret-key-1234"
    )
    req_valid = Request(
        {
            "type": "http",
            "headers": [
                (
                    b"cookie",
                    f"ribbit_google_oauth_handoff={valid_handoff}".encode("ascii"),
                )
            ],
        }
    )
    user_repo.find_by_id.return_value = User(
        user_id=99,
        email="user99@ribbit.com",
        password_hash="oauth",
        display_name="User 99",
        plan_id=1,
    )
    token_service.create_access_token.return_value = "new_jwt_for_user_99"

    auth_res = google_session(
        request=req_valid,
        response=resp,
        settings=settings,
        user_repo=user_repo,
        token_service=token_service,
    )

    assert auth_res.access_token == "new_jwt_for_user_99"
    assert auth_res.user.user_id == 99
    assert auth_res.user.email == "user99@ribbit.com"


def test_google_session_rejects_minor_on_free_plan() -> None:
    from fastapi import Request, Response

    from app.application.ports.repositories.plan_repository import PlanRepositoryPort
    from app.application.ports.repositories.user_repository import UserRepositoryPort
    from app.application.ports.services.token_service import TokenServicePort
    from app.config import Settings
    from app.domain.models.plan import Plan
    from app.presentation.routers.auth import _sign_cookie_payload, google_session

    settings = Settings(database_path=":memory:", secret_key="secret-key-1234")
    user_repo = MagicMock(spec=UserRepositoryPort)
    plan_repo = MagicMock(spec=PlanRepositoryPort)
    token_service = MagicMock(spec=TokenServicePort)

    valid_handoff = _sign_cookie_payload(
        {"user_id": 100, "exp": 9999999999}, secret_key="secret-key-1234"
    )
    req_valid = Request(
        {
            "type": "http",
            "headers": [
                (
                    b"cookie",
                    f"ribbit_google_oauth_handoff={valid_handoff}".encode("ascii"),
                )
            ],
        }
    )
    user_repo.find_by_id.return_value = User(
        user_id=100,
        email="minor100@ribbit.com",
        password_hash="oauth",
        display_name="Minor 100",
        age=15,
        plan_id=1,
    )
    plan_repo.find_by_id.return_value = Plan(
        plan_id=1, name="Free", initial_monthly_price=0.0, initial_max_profiles=1
    )

    resp = Response()
    res = google_session(
        request=req_valid,
        response=resp,
        settings=settings,
        user_repo=user_repo,
        token_service=token_service,
        plan_repo=plan_repo,
    )
    assert res.status_code == 403
    assert b"Minor users cannot use the Free plan" in res.body
    token_service.create_access_token.assert_not_called()


def test_google_callback_and_session_forward_unregistered_user_to_register() -> None:
    from fastapi import Request

    from app.application.use_cases.auth.complete_google_oauth import (
        CompleteGoogleOAuthUseCase,
    )
    from app.composition import create_app
    from app.config import Settings
    from app.domain.exceptions import EntityNotFoundError
    from app.presentation.routers.auth import (
        _sign_cookie_payload,
        _verify_cookie_payload,
        google_callback,
    )
    from tests.integration.test_client import TestClient

    settings = Settings(
        database_path=":memory:",
        secret_key="secret-key-1234",
        google_frontend_redirect_url="/login",
    )

    valid_state_cookie = _sign_cookie_payload(
        {"state": "state_reg", "code_verifier": "verifier_reg", "exp": 9999999999},
        secret_key="secret-key-1234",
    )
    req_cb = Request(
        {
            "type": "http",
            "headers": [
                (
                    b"cookie",
                    f"ribbit_google_oauth_state={valid_state_cookie}".encode("ascii"),
                )
            ],
        }
    )
    mock_complete_uc = MagicMock(spec=CompleteGoogleOAuthUseCase)
    mock_complete_uc.execute.side_effect = EntityNotFoundError(
        "No Ribbit account found.",
        entity_name="User",
        details={
            "registration_required": True,
            "email": "new.google@ribbit.com",
            "display_name": "New Google User",
        },
    )

    res_cb = google_callback(
        request=req_cb,
        settings=settings,
        code="code_new",
        state="state_reg",
        complete_use_case=mock_complete_uc,
    )
    assert res_cb.status_code == 302
    assert res_cb.headers["location"] == "/login?google_auth=register"
    assert "new.google@ribbit.com" not in res_cb.headers["location"]

    set_cookie_headers = res_cb.headers.getlist("set-cookie")
    handoff_header = next(
        h for h in set_cookie_headers if h.startswith("ribbit_google_oauth_handoff=")
    )
    handoff_cookie_val = handoff_header.split("=", 1)[1].split(";", 1)[0]
    decoded = _verify_cookie_payload(handoff_cookie_val, "secret-key-1234")
    assert decoded is not None
    assert decoded["registration_required"] is True
    assert decoded["email"] == "new.google@ribbit.com"
    assert decoded["display_name"] == "New Google User"

    app = create_app(settings)
    client = TestClient(app)
    res_http = client.post(
        "/api/auth/google/session",
        headers={"cookie": f"ribbit_google_oauth_handoff={handoff_cookie_val}"},
    )
    assert res_http.status_code == 404
    body = res_http.json()
    assert body["details"]["registration_required"] is True
    assert body["details"]["email"] == "new.google@ribbit.com"
    assert body["details"]["display_name"] == "New Google User"
    set_cookie_resp = res_http.headers.get("set-cookie", "")
    assert "ribbit_google_oauth_handoff=" in set_cookie_resp
    assert "max-age=0" in set_cookie_resp.lower()

    # After the browser clears the cookie, replaying without it yields 401
    res_replay = client.post("/api/auth/google/session")
    assert res_replay.status_code == 401
    assert "ribbit_google_oauth_handoff=" in res_replay.headers.get("set-cookie", "")


def test_google_oauth_endpoints_via_fastapi_di_when_unconfigured() -> None:
    from app.composition import create_app
    from app.config import Settings
    from tests.integration.test_client import TestClient

    settings = Settings(
        database_path=":memory:",
        secret_key="secret-key-1234",
        google_client_id=None,
        google_client_secret=None,
        google_redirect_uri=None,
    )
    app = create_app(settings)
    client = TestClient(app)

    # 1. Authorize endpoint should return 502 ExternalServiceError instead of 500 KeyError
    res_auth = client.get("/api/auth/google/authorize")
    assert res_auth.status_code == 502
    assert "not configured" in res_auth.json().get("message", "")

    # 2. Callback endpoint should redirect with error instead of 500 KeyError
    res_cb = client.get("/api/auth/google/callback?error=access_denied")
    assert res_cb.status_code == 302
    assert "google_auth_error=access_denied" in res_cb.headers.get("location", "")
