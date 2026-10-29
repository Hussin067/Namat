"""Request and response bodies for the /auth endpoints.

Response models list their fields explicitly, so private columns such as
password_hash can never leak into an API response.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# Length limits instead of composition rules (NIST SP 800-63B): long passphrases
# are encouraged; the maximum stops huge inputs from tying up the Argon2 hasher.
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128


def normalize_email(value: str) -> str:
    """One canonical form everywhere: no surrounding spaces, lowercase."""
    return value.strip().lower()


class RegisterRequest(BaseModel):
    # Reject unknown fields, so a client can't sneak in e.g. "is_active".
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=320)
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, value: object) -> object:
        return normalize_email(value) if isinstance(value, str) else value


class UserPublic(BaseModel):
    """The only user fields the API ever returns."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str | None
    timezone: str
    created_at: datetime


class SessionOut(BaseModel):
    """The signed-in user and when the session ends. The token itself is never in a
    response body: browsers get it as an HttpOnly cookie that JavaScript can't read."""

    user: UserPublic
    expires_at: datetime = Field(description="When the session cookie and its token expire (UTC)")


class ProtectedMessage(BaseModel):
    message: str
    user_id: uuid.UUID
