"""Cookie sessions and CSRF protection. Run from backend/ with:  python -m pytest

Synthetic example.com accounts only; every test is rolled back. The test client
keeps a cookie jar like a browser, so these tests exercise the browser flow.
"""

from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie

import jwt
import pytest
from sqlalchemy import select

from app.api.routes import auth as auth_routes
from app.core.config import Settings, get_settings
from app.core.security import TOKEN_ISSUER
from app.models import User
from tests.conftest import TEST_PASSWORD

SESSION = get_settings().session_cookie_name  # "namat_session" over plain HTTP (tests, development)
CSRF = get_settings().csrf_cookie_name
ORIGIN = get_settings().cors_origins[0]
EPISODE = {"started_at": "2026-06-01T08:00:00+00:00", "peak_intensity": 5}


def set_cookies(response) -> dict[str, dict]:
    """Parse every Set-Cookie header: {name: {"value": ..., attribute: ...}}."""
    cookies = {}
    for header in response.headers.get_list("set-cookie"):
        parsed = SimpleCookie()
        parsed.load(header)
        for name, morsel in parsed.items():
            cookies[name] = {"value": morsel.value, **{k: v for k, v in morsel.items() if v != ""}, "_raw": header}
    return cookies


@pytest.fixture
def account(client, db_session):
    assert client.post("/auth/register", json={"email": "cookie.a@example.com", "password": TEST_PASSWORD}).status_code == 201
    return db_session.scalar(select(User).where(User.email == "cookie.a@example.com"))


def login(client, email="cookie.a@example.com"):
    return client.post("/auth/login", data={"username": email, "password": TEST_PASSWORD})


def csrf_header(client) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get(CSRF)}


# --- Login sets the cookies correctly ----------------------------------------------------------

def test_login_sets_an_httponly_session_cookie_and_a_readable_csrf_cookie(client, account):
    response = login(client)
    assert response.status_code == 200
    cookies = set_cookies(response)
    lifetime = str(get_settings().access_token_expire_minutes * 60)

    session = cookies[SESSION]
    assert "httponly" in session["_raw"].lower()  # JavaScript can never read the token
    assert session["path"] == "/"
    assert session["samesite"].lower() == "lax"
    assert session["max-age"] == lifetime
    assert "secure" not in session["_raw"].lower()  # plain HTTP in development and tests

    csrf = cookies[CSRF]
    assert "httponly" not in csrf["_raw"].lower()  # the app's own pages read it
    assert (csrf["path"], csrf["samesite"].lower(), csrf["max-age"]) == ("/", "lax", lifetime)

    # The token isn't in the body, and the CSRF value is bound to the token.
    assert session["value"] not in response.text
    claims = jwt.decode(session["value"], options={"verify_signature": False})
    assert claims["csrf"] == csrf["value"]


def test_failed_login_sets_no_cookies(client, account):
    response = client.post("/auth/login", data={"username": "cookie.a@example.com", "password": "wrong-password-123"})
    assert response.status_code == 401
    assert set_cookies(response) == {}


def test_production_cookies_are_secure_and_host_prefixed(client, account, monkeypatch):
    production = Settings(
        _env_file=None, database_url="postgresql+psycopg://localhost/example_test", jwt_secret_key="s" * 40, app_env="production"
    )
    monkeypatch.setattr(auth_routes, "get_settings", lambda: production)
    cookies = set_cookies(login(client))
    for name in ("__Host-namat_session", "__Host-namat_csrf"):
        raw = cookies[name]["_raw"].lower()
        assert "secure" in raw and "path=/" in raw and "domain=" not in raw  # what the __Host- prefix requires
    assert "httponly" in cookies["__Host-namat_session"]["_raw"].lower()


def test_cross_site_cookie_settings_require_secure():
    base = {"_env_file": None, "database_url": "postgresql+psycopg://localhost/example_test", "jwt_secret_key": "s" * 40}
    with pytest.raises(ValueError, match="requires secure cookies"):
        Settings(**base, cookie_samesite="none")
    assert Settings(**base, cookie_samesite="none", cookie_secure=True).cookies_secure


# --- The cookie restores the session ("refresh") ----------------------------------------------

def test_session_and_me_work_with_the_cookie_alone(client, account):
    expires_at = login(client).json()["expires_at"]
    session = client.get("/auth/session")  # what the app calls on start-up / after a refresh
    assert session.status_code == 200
    assert session.json()["user"]["id"] == str(account.id)
    assert session.json()["expires_at"][:16] == expires_at[:16]
    assert client.get("/auth/me").json()["email"] == "cookie.a@example.com"
    assert client.get("/episodes").status_code == 200


@pytest.mark.parametrize(
    "cookie",
    [
        None,  # never logged in
        "not-a-token",
        "expired",
        "wrong-key",
    ],
)
def test_missing_invalid_or_expired_cookies_are_rejected(client, account, cookie):
    if cookie in ("expired", "wrong-key"):
        now = datetime.now(timezone.utc)
        claims = {"sub": str(account.id), "iss": TOKEN_ISSUER, "type": "access", "iat": now, "csrf": "x"}
        claims["exp"] = now - timedelta(seconds=1) if cookie == "expired" else now + timedelta(minutes=5)
        key = "another-secret-that-is-at-least-32-characters" if cookie == "wrong-key" else get_settings().jwt_secret_key.get_secret_value()
        cookie = jwt.encode(claims, key, algorithm="HS256")
    if cookie:
        client.cookies.set(SESSION, cookie)
    for path in ("/auth/session", "/auth/me", "/episodes"):
        response = client.get(path)
        assert response.status_code == 401
        assert response.json() == {"detail": "Could not validate credentials"}


# --- Logout ------------------------------------------------------------------------------------

def test_logout_clears_both_cookies_with_matching_attributes(client, account):
    login(client)
    response = client.post("/auth/logout", headers={"Origin": ORIGIN})
    assert response.status_code == 204
    cookies = set_cookies(response)
    for name in (SESSION, CSRF):
        assert cookies[name]["max-age"] == "0"
        assert cookies[name]["path"] == "/" and cookies[name]["samesite"].lower() == "lax"
    assert "httponly" in cookies[SESSION]["_raw"].lower()
    assert client.get("/auth/session").status_code == 401  # the session is gone


def test_logout_works_without_a_session(client):
    assert client.post("/auth/logout").status_code == 204


# --- CSRF ----------------------------------------------------------------------------------------

def test_cookie_requests_that_change_data_need_the_csrf_header(client, account):
    login(client)
    assert client.post("/episodes", json=EPISODE).status_code == 403  # no header
    assert client.post("/episodes", json=EPISODE, headers={"X-CSRF-Token": "guess"}).status_code == 403
    created = client.post("/episodes", json=EPISODE, headers=csrf_header(client))
    assert created.status_code == 201
    episode_id = created.json()["id"]
    assert client.patch(f"/episodes/{episode_id}", json={"notes": "x"}).status_code == 403
    assert client.delete(f"/episodes/{episode_id}").status_code == 403
    assert client.delete(f"/episodes/{episode_id}", headers=csrf_header(client)).status_code == 204


def test_csrf_token_from_another_session_is_rejected(client, account):
    login(client)
    old_token = client.cookies.get(CSRF)
    login(client)  # a new session gets a new CSRF value
    assert client.cookies.get(CSRF) != old_token
    assert client.post("/episodes", json=EPISODE, headers={"X-CSRF-Token": old_token}).status_code == 403


def test_reading_data_needs_no_csrf_header(client, account):
    login(client)
    assert client.get("/episodes").status_code == 200


def test_bearer_requests_need_no_csrf_header(client, make_user):
    headers = make_user("bearer.user@example.com")
    assert client.post("/episodes", json=EPISODE, headers=headers).status_code == 201


def test_requests_from_another_site_are_refused(client, account):
    evil = {"Origin": "https://evil.example"}
    # Even with a valid session and CSRF value, a foreign Origin is refused ...
    login(client)
    assert client.post("/episodes", json=EPISODE, headers=csrf_header(client) | evil).status_code == 403
    # ... and so are logins and registrations (login CSRF).
    client.cookies.clear()
    response = client.post("/auth/login", data={"username": "cookie.a@example.com", "password": TEST_PASSWORD}, headers=evil)
    assert response.status_code == 403 and set_cookies(response) == {}
    assert client.post("/auth/register", json={"email": "x@example.com", "password": TEST_PASSWORD}, headers=evil).status_code == 403


def test_requests_from_the_app_are_allowed(client, account):
    response = client.post(
        "/auth/login", data={"username": "cookie.a@example.com", "password": TEST_PASSWORD}, headers={"Origin": ORIGIN}
    )
    assert response.status_code == 200
    created = client.post("/episodes", json=EPISODE, headers=csrf_header(client) | {"Origin": ORIGIN})
    assert created.status_code == 201
