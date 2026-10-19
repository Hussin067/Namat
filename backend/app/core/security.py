"""Password hashing (pwdlib + Argon2) and JWT access tokens (PyJWT).

Nothing in this module logs or returns passwords, hashes or secrets.
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

# Argon2id with pwdlib's recommended parameters.
password_hasher = PasswordHash.recommended()

# Verified against when a login email doesn't exist, so a wrong email takes as
# long as a wrong password and response time doesn't reveal which accounts exist.
_DUMMY_HASH = password_hasher.hash("namat-dummy-password-for-timing")

TOKEN_ISSUER = "namat-api"
TOKEN_TYPE = "access"


class InvalidTokenError(Exception):
    """The token is missing, malformed, expired, wrongly signed or otherwise invalid."""


# --- Passwords ---

def hash_password(plain_password: str) -> str:
    return password_hasher.hash(plain_password)


def verify_password(plain_password: str, stored_hash: str) -> tuple[bool, str | None]:
    """Return (is_valid, new_hash).

    new_hash is not None when the stored hash uses outdated parameters and should
    be replaced; the caller saves it so hashes upgrade transparently on login.
    """
    return password_hasher.verify_and_update(plain_password, stored_hash)


def burn_password_check(plain_password: str) -> None:
    """Spend the same time as a real check, for logins with an unknown email."""
    password_hasher.verify(plain_password, _DUMMY_HASH)


# --- Access tokens ---

def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    """Return (token, lifetime_in_seconds). The token holds no personal data."""
    settings = get_settings()
    lifetime = timedelta(minutes=settings.access_token_expire_minutes)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iss": TOKEN_ISSUER,
        "type": TOKEN_TYPE,
        "iat": now,
        "exp": now + lifetime,
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return token, int(lifetime.total_seconds())


def decode_access_token(token: str) -> uuid.UUID:
    """Validate the token strictly and return the user ID it was issued for."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            # Only this algorithm is accepted: blocks "alg: none" and algorithm swaps.
            algorithms=[settings.jwt_algorithm],
            issuer=TOKEN_ISSUER,
            options={"require": ["sub", "iss", "iat", "exp"]},
        )
    except jwt.PyJWTError as exc:  # bad signature, expired, malformed, missing claim ...
        raise InvalidTokenError from exc

    if payload.get("type") != TOKEN_TYPE:
        raise InvalidTokenError
    try:
        return uuid.UUID(payload["sub"])
    except (ValueError, TypeError) as exc:
        raise InvalidTokenError from exc
