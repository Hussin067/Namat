"""Which database URL the app and Alembic use. Run from backend/ with:  python -m pytest

- FastAPI always connects with DATABASE_URL (Neon's pooled URL in production).
- Alembic prefers DIRECT_DATABASE_URL (Neon's direct URL) and falls back to
  DATABASE_URL, e.g. in local development.

Nothing here connects to a database. Every URL is a made-up example on an
.invalid host (a reserved name that can never resolve), with a dummy password
that is never printed: assertions compare hosts and dialects only.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from app.core.config import Settings

BACKEND_DIR = Path(__file__).resolve().parents[1]
SECRET = "s" * 40  # a syntactically valid, fake JWT secret
POOLED = "postgresql+psycopg://app:dummy@pooled.namat.invalid:5432/namat_example"
DIRECT = "postgresql+psycopg://app:dummy@direct.namat.invalid:5432/namat_example"


@pytest.fixture(autouse=True)
def _no_database_env(monkeypatch):
    # conftest points DATABASE_URL and DIRECT_DATABASE_URL at namat_test for the
    # rest of the suite; these tests build Settings from explicit values only.
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DIRECT_DATABASE_URL", raising=False)


def settings(**values) -> Settings:
    # _env_file=None: ignore backend/.env so only these values count.
    return Settings(_env_file=None, jwt_secret_key=SECRET, **values)


def host(url: str) -> str:
    return make_url(url).host


# --- Settings ------------------------------------------------------------------------

def test_direct_url_is_preferred_for_migrations_when_configured():
    s = settings(database_url=POOLED, direct_database_url=DIRECT)
    assert host(s.migration_database_url) == "direct.namat.invalid"
    assert host(s.database_url.get_secret_value()) == "pooled.namat.invalid"  # the app's URL is unchanged


@pytest.mark.parametrize("direct", [None, "", "   "])
def test_database_url_is_the_fallback(direct):
    s = settings(database_url=POOLED, direct_database_url=direct)
    assert s.direct_database_url is None
    assert host(s.migration_database_url) == "pooled.namat.invalid"


def test_local_development_works_without_a_direct_url():
    s = settings(database_url="postgresql+psycopg://namat_app:dummy@localhost:5432/namat_dev")
    assert s.direct_database_url is None
    assert make_url(s.migration_database_url).database == "namat_dev"


def test_direct_url_stays_secret_when_settings_are_printed():
    s = settings(database_url=POOLED, direct_database_url=DIRECT)
    assert "dummy" not in repr(s) and "dummy" not in str(s.direct_database_url)


def test_jwt_secret_must_not_reuse_the_direct_url_password():
    with pytest.raises(ValueError, match="must not reuse the database password"):
        settings(database_url=POOLED, direct_database_url=f"postgresql+psycopg://app:{SECRET}@direct.namat.invalid/db")


def test_existing_validation_is_unchanged():
    with pytest.raises(ValueError, match="at least 32 characters"):
        Settings(_env_file=None, database_url=POOLED, jwt_secret_key="too-short")
    with pytest.raises(ValueError):
        Settings(_env_file=None, jwt_secret_key=SECRET)  # DATABASE_URL is still required


# --- The real app and the real Alembic env.py, in a separate process --------------------

def run_backend(code_or_args: list[str], *, database_url: str, direct_url: str | None) -> subprocess.CompletedProcess:
    """Run Python in a fresh process with only these database settings (no .env values for them)."""
    env = {k: v for k, v in os.environ.items() if k not in ("DATABASE_URL", "DIRECT_DATABASE_URL", "TEST_DATABASE_URL")}
    env |= {"DATABASE_URL": database_url, "JWT_SECRET_KEY": SECRET, "APP_ENV": "development", "PYTHONDONTWRITEBYTECODE": "1"}
    # An explicit empty value overrides any DIRECT_DATABASE_URL in backend/.env.
    env["DIRECT_DATABASE_URL"] = direct_url or ""
    return subprocess.run(
        [sys.executable, "-B", *code_or_args], cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=120
    )


def test_fastapi_engine_uses_database_url_not_the_direct_url():
    # Creating the engine doesn't connect, so the .invalid hosts are never contacted.
    result = run_backend(
        ["-c", "from app.db.session import engine; print(engine.url.host)"], database_url=POOLED, direct_url=DIRECT
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip() == "pooled.namat.invalid"


# Runs the real alembic/env.py through Alembic's own command, but intercepts the
# URL at the point where env.py hands it over (create_engine for online mode,
# context.configure(url=...) for offline mode) and stops there: no connection
# is ever opened. Only the host is printed, never the password.
CAPTURE_URL = """
import sys
import sqlalchemy
from alembic import command
from alembic.config import Config
from alembic.runtime.environment import EnvironmentContext
from sqlalchemy.engine import make_url

class Captured(Exception):
    pass

def capture(url):
    print(make_url(str(url)).host)
    raise Captured

mode = sys.argv[1]
if mode == "online":
    sqlalchemy.create_engine = lambda url, *a, **k: capture(url)
else:
    EnvironmentContext.configure = lambda self, *a, url=None, **k: capture(url)
try:
    command.upgrade(Config("alembic.ini"), "head", sql=(mode == "offline"))
except Captured:
    pass
"""


def alembic_host(mode: str, *, direct_url: str | None) -> str:
    result = run_backend(["-c", CAPTURE_URL, mode], database_url=POOLED, direct_url=direct_url)
    assert result.returncode == 0, result.stderr[-2000:]
    return result.stdout.strip().splitlines()[-1]


@pytest.mark.parametrize("mode", ["online", "offline"])
def test_alembic_prefers_the_direct_url(mode):
    assert alembic_host(mode, direct_url=DIRECT) == "direct.namat.invalid"


@pytest.mark.parametrize("mode", ["online", "offline"])
def test_alembic_falls_back_to_database_url(mode):
    assert alembic_host(mode, direct_url=None) == "pooled.namat.invalid"
