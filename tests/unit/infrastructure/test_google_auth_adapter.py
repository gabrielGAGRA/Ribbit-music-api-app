"""Unit tests for Google IDP verifier adapter."""

from unittest.mock import MagicMock

import niquests
import pytest

from app.domain.exceptions import AuthenticationRequiredError
from app.infrastructure.adapters.google_auth_adapter import GoogleIdpVerifierAdapter


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
