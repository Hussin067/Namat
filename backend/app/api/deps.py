"""Shared FastAPI dependencies: database session and the authenticated user.

Browsers authenticate with the HttpOnly session cookie set by POST /auth/login.
API clients (and the test suite) may instead send "Authorization: Bearer <token>".

CSRF: a request authenticated by the cookie that changes data (POST, PATCH,
DELETE ...) must also send the session's CSRF token in the X-CSRF-Token header.
The token is random per session, stored inside the signed JWT and mirrored in a
readable cookie that only pages on the app's own site can read. A Bearer header
can't be attached by another site, so it needs no CSRF token.
"""

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import InvalidTokenError, decode_access_token_claims
from app.db.session import get_db
from app.models import User

# auto_error=False: a missing header isn't an error, because the cookie may be used.
bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_HEADER = "X-CSRF-Token"


def credentials_error() -> HTTPException:
    # One generic message for every failure, so callers learn nothing about why.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def csrf_error() -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, detail="CSRF token missing or invalid.")


def get_current_session(
    request: Request,
    db: DbSession,
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> tuple[User, dict]:
    """(user, token claims). Identity comes only from a valid token, never from a client-supplied user ID."""
    cookie_token = request.cookies.get(get_settings().session_cookie_name)
    if bearer is not None:
        token, from_cookie = bearer.credentials, False
    elif cookie_token:
        token, from_cookie = cookie_token, True
    else:
        raise credentials_error()

    try:
        user_id, claims = decode_access_token_claims(token)
    except InvalidTokenError:
        raise credentials_error() from None

    if from_cookie and request.method not in SAFE_METHODS:
        expected = claims.get("csrf")
        sent = request.headers.get(CSRF_HEADER, "")
        if not expected or not secrets.compare_digest(sent.encode(), expected.encode()):
            raise csrf_error()

    user = db.get(User, user_id)
    if user is None or not user.is_active:  # deleted or disabled since the token was issued
        raise credentials_error()
    return user, claims


def get_current_user(session: Annotated[tuple[User, dict], Depends(get_current_session)]) -> User:
    return session[0]


CurrentSession = Annotated[tuple[User, dict], Depends(get_current_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]
