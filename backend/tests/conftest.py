"""Test setup: an isolated test database, never the development one.

The tests use `namat_test`: the same server and role as DATABASE_URL in
backend/.env, with the database name swapped (override with TEST_DATABASE_URL).
A test URL derived from DATABASE_URL must also point at this machine
(localhost), so a hosted URL such as Neon's in DATABASE_URL can never be
contacted; a remote test database needs an explicit TEST_DATABASE_URL.
They refuse to run against any database whose name doesn't end in "_test",
checked three ways: the configured name, the application's own engine (the
process's DATABASE_URL is switched to the test database before the app is
imported), and the name the server reports for the open connection.

Before the first test, Alembic migrates namat_test to the latest revision
(the same migrations as development). Each test then runs inside a
transaction that is rolled back, so tests never see each other's data.
Only synthetic example.com accounts are used.

One-time setup (as the postgres superuser):
    CREATE DATABASE namat_test OWNER namat_app ENCODING 'UTF8' TEMPLATE template0;
"""

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_PASSWORD = "synthetic-test-password-123"


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _test_database_url():
    explicit = os.environ.get("TEST_DATABASE_URL")
    url = make_url(explicit) if explicit else make_url(get_settings().database_url.get_secret_value()).set(database="namat_test")
    if not (url.database or "").endswith("_test"):
        raise RuntimeError(f"Refusing to run tests against database {url.database!r}: its name must end in '_test'.")
    # A test URL derived from DATABASE_URL must point at this machine. If DATABASE_URL
    # holds a hosted (e.g. Neon production) URL, tests would otherwise connect to that
    # server. A remote test database is allowed only when named explicitly in
    # TEST_DATABASE_URL. (No socket path, i.e. host None, is also local.)
    if not explicit and url.host is not None and url.host not in LOCAL_HOSTS:
        raise RuntimeError(
            "Refusing to run tests: DATABASE_URL points at a non-local database server. "
            "Run tests against a local PostgreSQL, or set TEST_DATABASE_URL explicitly "
            "to a dedicated test database whose name ends in '_test'."
        )
    return url


TEST_DATABASE_URL = _test_database_url()

# Point the whole application at the test database before it is imported, so
# even code that opened its own session (instead of the get_db override below)
# could never reach the development database. Environment variables take
# precedence over backend/.env; this only affects the test process.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL.render_as_string(hide_password=False)
# Migrations prefer DIRECT_DATABASE_URL; point it at the test database too, so a
# direct URL in the developer's environment or .env can never be used by tests.
os.environ["DIRECT_DATABASE_URL"] = os.environ["DATABASE_URL"]
os.environ["APP_ENV"] = "test"
get_settings.cache_clear()

from app.core.rate_limit import limiter  # noqa: E402  (after the database URL is set)
from app.core.security import create_access_token  # noqa: E402
from app.db.session import engine as app_engine, get_db  # noqa: E402
from app.main import app  # noqa: E402

if app_engine.url.database != TEST_DATABASE_URL.database:
    raise RuntimeError("The application engine is not using the test database; refusing to run tests.")


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    """Each test starts with empty rate-limit counters (tests share one client address)."""
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(TEST_DATABASE_URL)
    with engine.connect() as connection:  # last check, against the server itself
        name = connection.execute(text("SELECT current_database()")).scalar()
    if not name.endswith("_test"):
        raise RuntimeError(f"Connected to {name!r}, not a test database; refusing to run tests.")
    # Bring namat_test to the latest schema using the real migrations.
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine) -> Iterator[Session]:
    connection = test_engine.connect()
    outer = connection.begin()
    # The app's commit() only releases a SAVEPOINT; everything is rolled back below.
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def make_user(client):
    """Register a synthetic user; returns an Authorization header for it.

    Login itself now answers with cookies (tested in test_auth.py). One test client
    holds one cookie jar, but many tests act as several users at once, so each user
    gets its own Bearer header instead, issued exactly as the API issues tokens.
    """

    def _make(email: str) -> dict[str, str]:
        response = client.post("/auth/register", json={"email": email, "password": TEST_PASSWORD})
        assert response.status_code == 201
        token, _ = create_access_token(uuid.UUID(response.json()["id"]))
        return {"Authorization": f"Bearer {token}"}

    return _make
