"""Registration, login, logout and current-user endpoints.

A successful login sets two cookies (see set_session_cookies):
- the session cookie: the signed JWT. HttpOnly, so JavaScript can never read it;
- the CSRF cookie: a random per-session value that the app's own pages read and
  send back in the X-CSRF-Token header on requests that change data.
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentSession, CurrentUser, DbSession
from app.core.config import get_settings
from app.core.rate_limit import (
    LOGIN_FAILURES_PER_ACCOUNT,
    LOGIN_FAILURES_PER_CLIENT,
    REGISTRATIONS_PER_CLIENT,
    check,
    check_and_record,
    client_address,
    limiter,
)
from app.core.security import (
    burn_password_check,
    create_access_token,
    hash_password,
    new_csrf_token,
    verify_password,
)
from app.models import User
from app.schemas.auth import (
    PASSWORD_MAX_LENGTH,
    ProtectedMessage,
    RegisterRequest,
    SessionOut,
    UserPublic,
    normalize_email,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _email_taken() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered.")


def _bad_login() -> HTTPException:
    # Same message whether the email is unknown or the password is wrong.
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def set_session_cookies(response: Response, token: str, csrf: str, lifetime_seconds: int) -> None:
    """Both cookies share the token's lifetime, Path=/ and SameSite; only the session one is HttpOnly."""
    settings = get_settings()
    common = {
        "max_age": lifetime_seconds,
        "path": "/",
        "secure": settings.cookies_secure,
        "samesite": settings.cookie_samesite,
    }
    response.set_cookie(settings.session_cookie_name, token, httponly=True, **common)
    response.set_cookie(settings.csrf_cookie_name, csrf, httponly=False, **common)


def clear_session_cookies(response: Response) -> None:
    """Expire both cookies, with the same attributes they were set with."""
    settings = get_settings()
    common = {"path": "/", "secure": settings.cookies_secure, "samesite": settings.cookie_samesite}
    response.delete_cookie(settings.session_cookie_name, httponly=True, **common)
    response.delete_cookie(settings.csrf_cookie_name, httponly=False, **common)


def _find_user_by_email(db: DbSession, email: str) -> User | None:
    # lower(email) matches the uq_users_email_lower index exactly.
    return db.scalar(select(User).where(func.lower(User.email) == email))


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: DbSession, request: Request) -> User:
    check_and_record(REGISTRATIONS_PER_CLIENT, client_address(request))
    if _find_user_by_email(db, body.email) is not None:
        raise _email_taken()

    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Two sign-ups with the same email at the same moment: the unique index wins.
        db.rollback()
        raise _email_taken() from None
    db.refresh(user)  # load server-set columns such as created_at
    return user


@router.post("/login", response_model=SessionOut)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
    request: Request,
    response: Response,
) -> SessionOut:
    """OAuth2 password form: the email goes in the `username` form field.

    On success the session is set as cookies; the response body holds the user and
    the expiry time, never the token.

    Failed attempts are limited per account and per client address (429 with
    Retry-After once used up). The limit applies whether or not the email
    exists, so it reveals nothing about which accounts exist.
    """
    email = normalize_email(form.username)
    password = form.password
    client = client_address(request)
    check(LOGIN_FAILURES_PER_CLIENT, client)
    check(LOGIN_FAILURES_PER_ACCOUNT, email[:320])

    def failed() -> HTTPException:
        limiter.record(LOGIN_FAILURES_PER_CLIENT, client)
        limiter.record(LOGIN_FAILURES_PER_ACCOUNT, email[:320])
        return _bad_login()

    if len(password) > PASSWORD_MAX_LENGTH or len(email) > 320:
        raise failed()  # never hash oversized input

    user = _find_user_by_email(db, email)
    if user is None:
        burn_password_check(password)  # keep timing equal to a wrong password
        raise failed()

    valid, upgraded_hash = verify_password(password, user.password_hash)
    if not valid or not user.is_active:
        raise failed()
    if upgraded_hash is not None:  # hashing parameters were strengthened since signup
        user.password_hash = upgraded_hash
        db.commit()

    csrf = new_csrf_token()
    token, expires_in = create_access_token(user.id, csrf=csrf)
    set_session_cookies(response, token, csrf, expires_in)
    response.headers["Cache-Control"] = "no-store"  # sessions must not be cached (RFC 6749)
    return SessionOut(user=user, expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout() -> Response:
    """End the browser session: both cookies are expired. Works even if the session already ended."""
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookies(response)
    return response


@router.get("/session", response_model=SessionOut)
def read_session(session: CurrentSession) -> SessionOut:
    """The current user and when the session ends; the app calls this on start-up."""
    user, claims = session
    return SessionOut(user=user, expires_at=datetime.fromtimestamp(claims["exp"], timezone.utc))


@router.get("/me", response_model=UserPublic)
def read_me(current_user: CurrentUser) -> User:
    return current_user


@router.get("/protected", response_model=ProtectedMessage)
def protected(current_user: CurrentUser) -> ProtectedMessage:
    """Minimal endpoint for checking that authentication works. Returns no health data."""
    return ProtectedMessage(message="You are authenticated.", user_id=current_user.id)
