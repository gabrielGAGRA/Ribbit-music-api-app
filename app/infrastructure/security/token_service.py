"""HMAC-SHA256 bearer token service implementation."""

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from app.application.ports.services.token_service import TokenServicePort
from app.domain.exceptions import AuthenticationRequiredError


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _base64url_decode(segment: str) -> bytes:
    padding = "=" * ((4 - len(segment) % 4) % 4)
    b64_str = (segment + padding).replace("-", "+").replace("_", "/")
    try:
        return base64.b64decode(b64_str.encode("ascii"), validate=True, canonical=True)
    except TypeError:
        return base64.b64decode(b64_str.encode("ascii"), validate=True)


class HMACTokenService(TokenServicePort):
    """Generates and validates signed JWT-formatted access tokens using HMAC-SHA256."""

    def __init__(
        self,
        secret_key: str,
        default_expiration_seconds: int = 43200,
        expiration_seconds: int | None = None,
    ) -> None:
        if not secret_key:
            raise ValueError("Secret key cannot be empty.")
        self.secret_key = secret_key.encode("utf-8")
        self.default_expiration_seconds = (
            expiration_seconds
            if expiration_seconds is not None
            else default_expiration_seconds
        )

    def _sign(self, message: bytes) -> bytes:
        return hmac.new(self.secret_key, message, hashlib.sha256).digest()

    def create_access_token(
        self,
        user_id: int,
        is_admin: bool = False,
        expires_in_seconds: int | None = None,
    ) -> str:
        ttl = (
            expires_in_seconds
            if expires_in_seconds is not None
            else self.default_expiration_seconds
        )
        now = int(time.time())
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": str(user_id),
            "is_admin": is_admin,
            "iat": now,
            "exp": now + ttl,
        }
        encoded_header = _base64url_encode(
            json.dumps(header, separators=(",", ":")).encode("utf-8")
        )
        encoded_payload = _base64url_encode(
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
        )
        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
        signature = _base64url_encode(self._sign(signing_input))
        return f"{encoded_header}.{encoded_payload}.{signature}"

    def decode_access_token(self, token: str) -> dict[str, Any]:
        parts = token.split(".")
        if len(parts) != 3:
            raise AuthenticationRequiredError("Invalid token format.")
        header_b64, payload_b64, sig_b64 = parts
        try:
            actual_sig = _base64url_decode(sig_b64)
            header = json.loads(_base64url_decode(header_b64).decode("utf-8"))
            payload = json.loads(_base64url_decode(payload_b64).decode("utf-8"))
        except Exception as exc:
            raise AuthenticationRequiredError(f"Invalid token: {exc}") from exc

        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        expected_sig = self._sign(signing_input)
        if not hmac.compare_digest(expected_sig, actual_sig):
            raise AuthenticationRequiredError("Invalid token signature.")

        if header.get("alg") != "HS256":
            raise AuthenticationRequiredError("Unsupported token algorithm.")

        exp = payload.get("exp")
        if exp is not None and int(exp) < int(time.time()):
            raise AuthenticationRequiredError("Token has expired.")

        return payload


__all__ = ["HMACTokenService"]
