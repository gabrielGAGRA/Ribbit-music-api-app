"""Adapter verifying Google Identity Provider ID tokens via Google tokeninfo endpoint."""

from urllib.parse import urlencode

import niquests

from app.application.ports.services.google_auth import (
    GoogleIdpVerifierPort,
    GoogleOAuthPort,
    GoogleUserInfo,
)
from app.domain.exceptions import AuthenticationRequiredError

_GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
_HTTP_TIMEOUT_SECONDS = 5.0


class GoogleIdpVerifierAdapter(GoogleIdpVerifierPort):
    def __init__(
        self,
        expected_client_id: str | None = None,
        session: niquests.Session | None = None,
    ) -> None:
        self._expected_client_id = expected_client_id
        self._session = session or niquests.Session()

    def verify_id_token(self, id_token: str) -> GoogleUserInfo:
        if not id_token.strip():
            raise AuthenticationRequiredError("Google ID token cannot be blank.")

        try:
            resp = self._session.get(
                _GOOGLE_TOKENINFO_URL,
                params={"id_token": id_token.strip()},
                timeout=_HTTP_TIMEOUT_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001
            raise AuthenticationRequiredError(
                "Unable to verify Google ID token due to network failure."
            ) from exc

        if resp.status_code != 200:
            raise AuthenticationRequiredError("Invalid or expired Google ID token.")

        payload = resp.json()
        if self._expected_client_id:
            aud = payload.get("aud")
            if aud != self._expected_client_id:
                raise AuthenticationRequiredError(
                    f"Google ID token audience '{aud}' does not match expected client."
                )

        email = payload.get("email")
        if not email:
            raise AuthenticationRequiredError(
                "Google ID token does not contain an email address."
            )

        email_verified_val = payload.get("email_verified")
        email_verified = email_verified_val is True or email_verified_val == "true"
        if not email_verified:
            raise AuthenticationRequiredError("Google account email is not verified.")

        raw_name = (payload.get("name") or "").strip()
        display_name = raw_name if raw_name else email.split("@")[0]

        return GoogleUserInfo(
            email=email.strip().lower(),
            email_verified=True,
            name=display_name,
            sub=payload.get("sub") or "",
        )


class GoogleOAuthAdapter(GoogleOAuthPort):
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        auth_uri: str = "https://accounts.google.com/o/oauth2/auth",
        token_uri: str = "https://oauth2.googleapis.com/token",  # noqa: S107
        session: niquests.Session | None = None,
    ) -> None:
        if not client_id or not client_id.strip():
            raise ValueError("Google client_id cannot be blank.")
        if not client_secret or not client_secret.strip():
            raise ValueError("Google client_secret cannot be blank.")
        if not redirect_uri or not redirect_uri.strip():
            raise ValueError("Google redirect_uri cannot be blank.")

        self._client_id = client_id.strip()
        self._client_secret = client_secret.strip()
        self._redirect_uri = redirect_uri.strip()
        self._auth_uri = auth_uri.strip()
        self._token_uri = token_uri.strip()
        self._session = session or niquests.Session()

    def build_authorize_url(self, state: str, code_challenge: str | None = None) -> str:
        params = {
            "client_id": self._client_id,
            "response_type": "code",
            "redirect_uri": self._redirect_uri,
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "select_account",
        }
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
        return f"{self._auth_uri}?{urlencode(params)}"

    def exchange_code(self, code: str, code_verifier: str | None = None) -> str:
        if not code.strip():
            raise AuthenticationRequiredError("Authorization code cannot be blank.")

        data = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "code": code.strip(),
            "grant_type": "authorization_code",
            "redirect_uri": self._redirect_uri,
        }
        if code_verifier:
            data["code_verifier"] = code_verifier.strip()

        try:
            resp = self._session.post(
                self._token_uri,
                data=data,
                timeout=_HTTP_TIMEOUT_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001
            raise AuthenticationRequiredError(
                "Unable to exchange Google authorization code due to network failure."
            ) from exc

        if resp.status_code != 200:
            raise AuthenticationRequiredError(
                "Invalid or expired Google authorization code."
            )

        try:
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise AuthenticationRequiredError(
                "Malformed response from Google token endpoint."
            ) from exc

        id_token = payload.get("id_token")
        if not id_token or not isinstance(id_token, str) or not id_token.strip():
            raise AuthenticationRequiredError("Google token response missing id_token.")

        return id_token.strip()


__all__ = ["GoogleIdpVerifierAdapter", "GoogleOAuthAdapter"]
