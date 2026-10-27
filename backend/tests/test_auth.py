"""/auth: registration, login, tokens and login rate limits. Run from backend/ with:  python -m pytest

Synthetic example.com accounts only; every test is rolled back.
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.rate_limit import LOGIN_FAILURES_PER_ACCOUNT, REGISTRATIONS_PER_CLIENT
from app.core.security import TOKEN_ISSUER, create_access_token
from app.models import User
from tests.conftest import TEST_PASSWORD

GENERIC_401 = "Could not validate credentials"


def register(client, email, password=TEST_PASSWORD, **extra):
    return client.post("/auth/register", json={"email": email, "password": password, **extra})


def login(client, email, password=TEST_PASSWORD):
    return client.post("/auth/login", data={"username": email, "password": password})


def token_for(claims: dict, key: str | None = None, algorithm: str = "HS256") -> str:
    secret = key or get_settings().jwt_secret_key.get_secret_value()
    now = datetime.now(timezone.utc)
    payload = {"sub": None, "iss": TOKEN_ISSUER, "type": "access", "iat": now, "exp": now + timedelta(minutes=5)} | claims
    return jwt.encode({k: v for k, v in payload.items() if v is not ...}, secret, algorithm=algorithm)


@pytest.fixture
def account(client, db_session):
    assert register(client, "auth.a@example.com").status_code == 201
    return db_session.scalar(select(User).where(User.email == "auth.a@example.com"))


# --- Registration ------------------------------------------------------------------------

def test_register_returns_only_public_fields_and_hashes_with_argon2(client, db_session):
    response = register(client, "  New.User@Example.com ")
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "email", "display_name", "timezone", "created_at"}
    assert body["email"] == "new.user@example.com"  # normalised
    stored = db_session.scalar(select(User).where(User.email == "new.user@example.com"))
    assert stored.password_hash.startswith("$argon2id$")
    assert TEST_PASSWORD not in stored.password_hash


def test_duplicate_email_is_rejected_case_insensitively(client, account):
    response = register(client, "AUTH.A@example.com")
    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered."}


@pytest.mark.parametrize(
    "email, password",
    [
        ("not-an-email", TEST_PASSWORD),
        ("short@example.com", "elevenchars"),  # 11 < 12
        ("long@example.com", "x" * 129),
        ("", TEST_PASSWORD),
    ],
)
def test_invalid_registrations_are_rejected(client, email, password):
    assert register(client, email, password).status_code == 422


def test_registration_cannot_set_privileged_fields(client):
    assert register(client, "sneaky@example.com", is_active=False).status_code == 422
    assert register(client, "sneaky@example.com", id=str(uuid.uuid4())).status_code == 422


# --- Login ---------------------------------------------------------------------------------

def test_login_returns_a_short_lived_bearer_token_that_is_not_cached(client, account):
    response = login(client, "Auth.A@Example.com")  # any case works
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == get_settings().access_token_expire_minutes * 60
    assert response.headers["cache-control"] == "no-store"
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["id"] == str(account.id)


def test_wrong_password_and_unknown_email_get_the_same_answer(client, account):
    wrong = login(client, "auth.a@example.com", "wrong-password-123")
    unknown = login(client, "nobody@example.com")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "Incorrect email or password."}


def test_oversized_login_input_is_rejected_without_hashing(client, account):
    assert login(client, "auth.a@example.com", "x" * 10_000).status_code == 401


def test_inactive_account_cannot_log_in_or_use_a_token(client, db_session, account):
    token, _ = create_access_token(account.id)
    account.is_active = False
    db_session.flush()
    assert login(client, "auth.a@example.com").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


# --- Tokens ----------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "make_token",
    [
        lambda uid: token_for({"sub": uid, "exp": datetime.now(timezone.utc) - timedelta(seconds=1)}),  # expired
        lambda uid: token_for({"sub": uid}, key="a-different-secret-that-is-at-least-32-chars"),  # wrong key
        lambda uid: token_for({"sub": uid}, algorithm="HS512"),  # algorithm swap
        lambda uid: jwt.encode({"sub": uid, "iss": TOKEN_ISSUER, "type": "access"}, None, algorithm="none"),  # unsigned
        lambda uid: token_for({"sub": uid, "iss": "someone-else"}),  # wrong issuer
        lambda uid: token_for({"sub": uid, "type": "refresh"}),  # wrong token type
        lambda uid: token_for({"sub": uid, "exp": ...}),  # no expiry
        lambda uid: token_for({"sub": "not-a-uuid"}),
        lambda uid: token_for({"sub": str(uuid.uuid4())}),  # user doesn't exist
        lambda uid: "not.a.jwt",
        lambda uid: "",
    ],
    ids=["expired", "wrong-key", "hs512", "alg-none", "issuer", "type", "no-exp", "bad-sub", "unknown-user", "malformed", "empty"],
)
def test_invalid_tokens_are_rejected_with_one_generic_answer(client, account, make_token):
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {make_token(str(account.id))}"})
    assert response.status_code == 401
    assert response.json() == {"detail": GENERIC_401} or response.json() == {"detail": "Not authenticated"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_a_valid_token_works(client, account):
    good = token_for({"sub": str(account.id)})
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {good}"}).status_code == 200


def test_tokens_hold_no_personal_data(account):
    token, _ = create_access_token(account.id)
    claims = jwt.decode(token, options={"verify_signature": False})
    assert set(claims) == {"sub", "iss", "type", "iat", "exp"}
    assert "example.com" not in token


# --- Rate limits ----------------------------------------------------------------------------------

def test_repeated_failed_logins_are_slowed_down_per_account(client, account):
    for _ in range(LOGIN_FAILURES_PER_ACCOUNT.limit):
        assert login(client, "auth.a@example.com", "wrong-password-123").status_code == 401
    blocked = login(client, "auth.a@example.com")  # even the right password waits
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0
    assert blocked.json() == {"detail": "Too many attempts. Please wait a moment and try again."}
    # Another account isn't affected by this one's failures.
    assert register(client, "auth.b@example.com").status_code == 201
    assert login(client, "auth.b@example.com").status_code == 200


def test_unknown_emails_are_limited_the_same_way(client):
    for _ in range(LOGIN_FAILURES_PER_ACCOUNT.limit):
        assert login(client, "ghost@example.com").status_code == 401
    assert login(client, "ghost@example.com").status_code == 429  # reveals nothing about existence


def test_successful_logins_are_not_counted(client, account):
    for _ in range(LOGIN_FAILURES_PER_ACCOUNT.limit + 3):
        assert login(client, "auth.a@example.com").status_code == 200


def test_registrations_are_limited_per_client(client):
    for i in range(REGISTRATIONS_PER_CLIENT.limit):
        assert register(client, f"bulk{i}@example.com").status_code == 201
    response = register(client, "one-too-many@example.com")
    assert response.status_code == 429
    assert "retry-after" in response.headers
