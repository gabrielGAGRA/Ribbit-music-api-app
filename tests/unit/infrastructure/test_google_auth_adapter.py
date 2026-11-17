"""Unit tests for Google IDP verifier adapter."""

from unittest.mock import MagicMock

import niquests
import pytest

from app.domain.exceptions import AuthenticationRequiredError
from app.infrastructure.adapters.google_auth_adapter import (
    GoogleIdpVerifierAdapter,
    GoogleOAuthAdapter,
)


def test_verify_id_token_successful() -> None:
    mock_session = MagicMock(spec=niquests.Session)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "email": "google_user@example.com",
        "email_verified": "true",
        "name": "Google User",
        "sub": "google-sub-12345",
        "aud": "my-client-id",
    }
    mock_session.get.return_value = mock_response

    adapter = GoogleIdpVerifierAdapter(
        expected_client_id="my-client-id", session=mock_session
    )
    info = adapter.verify_id_token("valid_token")

    assert info.email == "google_user@example.com"
    assert info.email_verified is True
    assert info.name == "Google User"
    assert info.sub == "google-sub-12345"


def test_verify_id_token_mismatched_audience_raises_error() -> None:
    mock_session = MagicMock(spec=niquests.Session)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "email": "google_user@example.com",
        "email_verified": "true",
        "name": "Google User",
        "aud": "attacker-client-id",
    }
    mock_session.get.return_value = mock_response

    adapter = GoogleIdpVerifierAdapter(
        expected_client_id="my-client-id", session=mock_session
    )
    with pytest.raises(AuthenticationRequiredError, match="does not match"):
        adapter.verify_id_token("valid_token")


def test_verify_id_token_whitespace_name_falls_back_to_email_prefix() -> None:
    mock_session = MagicMock(spec=niquests.Session)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "email": "john.doe@example.com",
        "email_verified": True,
        "name": "    ",
    }
    mock_session.get.return_value = mock_response

    adapter = GoogleIdpVerifierAdapter(session=mock_session)
    info = adapter.verify_id_token("token")
    assert info.name == "john.doe"


def test_verify_id_token_blank_raises_error() -> None:
    adapter = GoogleIdpVerifierAdapter()
    with pytest.raises(AuthenticationRequiredError, match="cannot be blank"):
        adapter.verify_id_token("   ")


def test_verify_id_token_unverified_email_raises_error() -> None:
    mock_session = MagicMock(spec=niquests.Session)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "email": "unverified@example.com",
        "email_verified": False,
        "name": "Unverified",
    }
    mock_session.get.return_value = mock_response

    adapter = GoogleIdpVerifierAdapter(session=mock_session)
    with pytest.raises(AuthenticationRequiredError, match="not verified"):
        adapter.verify_id_token("token_unverified")


def test_verify_id_token_invalid_response_raises_error() -> None:
    mock_session = MagicMock(spec=niquests.Session)
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_session.get.return_value = mock_response

    adapter = GoogleIdpVerifierAdapter(session=mock_session)
    with pytest.raises(AuthenticationRequiredError, match="Invalid or expired"):
        adapter.verify_id_token("token_bad")


def test_verify_id_token_rejects_cross_client_prefix_audience() -> None:
    mock_session = MagicMock(spec=niquests.Session)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "email": "user@example.com",
        "email_verified": True,
        "name": "User",
        "sub": "sub-1",
        "aud": "108921521849256271018-abcdef.apps.googleusercontent.com",
    }
    mock_session.get.return_value = mock_response

    adapter = GoogleIdpVerifierAdapter(
        expected_client_id="108921521849256271018", session=mock_session
    )
    with pytest.raises(AuthenticationRequiredError, match="does not match"):
        adapter.verify_id_token("cross_client_token")


def test_google_oauth_adapter_constructor_validates_inputs() -> None:
    with pytest.raises(ValueError, match="client_id"):
        GoogleOAuthAdapter(client_id="", client_secret="sec", redirect_uri="http://cb")
    with pytest.raises(ValueError, match="client_secret"):
        GoogleOAuthAdapter(client_id="cid", client_secret="", redirect_uri="http://cb")
    with pytest.raises(ValueError, match="redirect_uri"):
        GoogleOAuthAdapter(client_id="cid", client_secret="sec", redirect_uri="")


def test_google_oauth_adapter_build_authorize_url() -> None:
    adapter = GoogleOAuthAdapter(
        client_id="cid123",
        client_secret="sec456",
        redirect_uri="http://localhost:4200/callback",
    )
    url = adapter.build_authorize_url(state="state_xyz")
    assert "https://accounts.google.com/o/oauth2/auth?" in url
    assert "client_id=cid123" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A4200%2Fcallback" in url
    assert "response_type=code" in url
    assert "state=state_xyz" in url
    assert "code_challenge" not in url

    pkce_url = adapter.build_authorize_url(
        state="state_xyz", code_challenge="challenge_abc"
    )
    assert "code_challenge=challenge_abc" in pkce_url
    assert "code_challenge_method=S256" in pkce_url


def test_google_oauth_adapter_exchange_code_successful() -> None:
    mock_session = MagicMock(spec=niquests.Session)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "access_token": "ya29.acc",
        "id_token": "google.id.token.jwt",
        "expires_in": 3599,
        "token_type": "Bearer",
    }
    mock_session.post.return_value = mock_resp

    adapter = GoogleOAuthAdapter(
        client_id="cid123",
        client_secret="sec456",
        redirect_uri="http://localhost:4200/callback",
        session=mock_session,
    )

    id_token = adapter.exchange_code(code="auth_code_123", code_verifier="verifier_456")
    assert id_token == "google.id.token.jwt"
    mock_session.post.assert_called_once_with(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": "cid123",
            "client_secret": "sec456",
            "code": "auth_code_123",
            "grant_type": "authorization_code",
            "redirect_uri": "http://localhost:4200/callback",
            "code_verifier": "verifier_456",
        },
        timeout=5.0,
    )


def test_google_oauth_adapter_exchange_code_validations_and_errors() -> None:
    mock_session = MagicMock(spec=niquests.Session)
    adapter = GoogleOAuthAdapter(
        client_id="cid123",
        client_secret="sec456",
        redirect_uri="http://localhost:4200/callback",
        session=mock_session,
    )

    with pytest.raises(AuthenticationRequiredError, match="cannot be blank"):
        adapter.exchange_code("   ")

    mock_session.post.side_effect = niquests.RequestException("Network down")
    with pytest.raises(AuthenticationRequiredError, match="network failure"):
        adapter.exchange_code("valid_code")

    mock_resp_400 = MagicMock()
    mock_resp_400.status_code = 400
    mock_session.post.side_effect = None
    mock_session.post.return_value = mock_resp_400
    with pytest.raises(AuthenticationRequiredError, match="Invalid or expired"):
        adapter.exchange_code("valid_code")

    mock_resp_no_token = MagicMock()
    mock_resp_no_token.status_code = 200
    mock_resp_no_token.json.return_value = {"access_token": "ya29"}
    mock_session.post.return_value = mock_resp_no_token
    with pytest.raises(AuthenticationRequiredError, match="missing id_token"):
        adapter.exchange_code("valid_code")
