"""Security adapter implementing PasswordHasherPort with PBKDF2-HMAC-SHA256."""

import hashlib
import secrets

from app.application.ports.services.password_hasher import PasswordHasherPort


class PBKDF2PasswordHasher(PasswordHasherPort):
    """Cryptographic password hasher using PBKDF2 with SHA-256 and per-password salt."""

    def __init__(self, iterations: int = 100_000) -> None:
        self._iterations = iterations

    def hash_password(self, password: str) -> str:
        """Hashes the password with a random salt and returns salt$hash format."""
        salt = secrets.token_bytes(16)
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            self._iterations,
        )
        return f"{salt.hex()}${key.hex()}"

    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verifies if the provided plain text password matches the stored hash."""
        try:
            salt_hex, key_hex = hashed_password.split("$", 1)
            salt = bytes.fromhex(salt_hex)
            expected_key = bytes.fromhex(key_hex)
            actual_key = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt,
                self._iterations,
            )
            return secrets.compare_digest(actual_key, expected_key)
        except ValueError, TypeError:
            return False


__all__ = ["PBKDF2PasswordHasher"]
