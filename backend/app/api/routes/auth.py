"""Registration, login and current-user endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
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
    verify_password,
)
from app.models import User
from app.schemas.auth import (
    PASSWORD_MAX_LENGTH,
    ProtectedMessage,
    RegisterRequest,
    Token,
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


@router.post("/login", response_model=Token)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
    request: Request,
    response: Response,
) -> Token:
    """OAuth2 password flow: the email goes in the `username` form field.

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

    token, expires_in = create_access_token(user.id)
    response.headers["Cache-Control"] = "no-store"  # tokens must not be cached (RFC 6749)
    return Token(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserPublic)
def read_me(current_user: CurrentUser) -> User:
    return current_user


@router.get("/protected", response_model=ProtectedMessage)
def protected(current_user: CurrentUser) -> ProtectedMessage:
    """Minimal endpoint for checking that authentication works. Returns no health data."""
    return ProtectedMessage(message="You are authenticated.", user_id=current_user.id)
