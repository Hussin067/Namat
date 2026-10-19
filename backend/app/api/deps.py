"""Shared FastAPI dependencies: database session and the authenticated user."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import InvalidTokenError, decode_access_token
from app.db.session import get_db
from app.models import User

# Reads "Authorization: Bearer <token>"; answers 401 by itself if it's missing.
# tokenUrl also powers the "Authorize" button in the /docs page.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

DbSession = Annotated[Session, Depends(get_db)]


def credentials_error() -> HTTPException:
    # One generic message for every failure, so callers learn nothing about why.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], db: DbSession
) -> User:
    """Identity comes only from a valid token, never from a client-supplied user ID."""
    try:
        user_id = decode_access_token(token)
    except InvalidTokenError:
        raise credentials_error() from None

    user = db.get(User, user_id)
    if user is None or not user.is_active:  # deleted or disabled since the token was issued
        raise credentials_error()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
