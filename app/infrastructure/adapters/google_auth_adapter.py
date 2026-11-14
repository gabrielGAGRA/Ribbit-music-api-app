"""Adapter verifying Google Identity Provider ID tokens via Google tokeninfo endpoint."""

import niquests

from app.application.ports.services.google_auth import (
    GoogleIdpVerifierPort,
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


__all__ = ["GoogleIdpVerifierAdapter"]
