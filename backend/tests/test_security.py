"""Cross-cutting security checks: every route needs a token, response headers,
caching, CORS, safe error responses and the rate limiter. Run from backend/ with:  python -m pytest
"""

import re
import uuid

import pytest
from sqlalchemy.exc import OperationalError

from app.core.config import Settings, get_settings
from app.core.rate_limit import REPORT_PDFS_PER_USER, REPORTS_PER_USER, RateLimiter, Rule, limiter
from app.db.session import engine, get_db
from app.main import app

PUBLIC = {("GET", "/"), ("GET", "/health"), ("POST", "/auth/register"), ("POST", "/auth/login")}
ORIGIN = get_settings().cors_origins[0]


def protected_routes():
    # Every documented route (the OpenAPI schema lists them all, including nested routers).
    for path, operations in app.openapi()["paths"].items():
        for method in operations:
            if (method.upper(), path) not in PUBLIC:
                yield method.upper(), re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)


ROUTES = sorted(protected_routes())


def test_route_inventory_is_complete():
    # If this fails, a route was added: decide whether it is public, then update PUBLIC.
    assert len(ROUTES) == 22


@pytest.mark.parametrize("method, path", ROUTES)
def test_every_non_public_route_requires_a_token(client, method, path):
    response = client.request(method, path)
    assert response.status_code == 401, f"{method} {path} answered {response.status_code}"


@pytest.mark.parametrize("path", ["/episodes", "/sleep-logs", "/daily-factors", "/analytics/dashboard", "/insights", "/auth/me"])
def test_health_data_responses_are_never_cached_and_carry_security_headers(client, make_user, path):
    response = client.get(path, headers=make_user("headers@example.com"))
    assert response.status_code == 200
    assert "no-store" in response.headers["cache-control"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"


def test_errors_carry_the_same_headers(client):
    response = client.get("/episodes")
    assert response.status_code == 401
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"


def test_cors_allows_only_the_configured_origin(client):
    allowed = client.options("/episodes", headers={"Origin": ORIGIN, "Access-Control-Request-Method": "GET"})
    assert allowed.headers["access-control-allow-origin"] == ORIGIN
    other = client.options("/episodes", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in other.headers


def test_database_failure_gives_a_safe_500_that_the_browser_can_read(client, make_user):
    headers = make_user("dbdown@example.com")

    def broken_db():
        raise OperationalError("SELECT notes FROM headache_episodes", {"notes": "private-health-note"}, Exception("server down"))

    app.dependency_overrides[get_db] = broken_db
    response = client.get("/episodes", headers=headers | {"Origin": ORIGIN})
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error."}
    assert "private-health-note" not in response.text and "SELECT" not in response.text
    assert response.headers["access-control-allow-origin"] == ORIGIN  # the app can show a proper message
    assert response.headers["cache-control"] == "no-store"


def test_database_errors_never_include_values():
    assert engine.hide_parameters is True


def test_validation_errors_do_not_echo_other_users_data(client, make_user):
    response = client.post("/episodes", json={"started_at": "nonsense"}, headers=make_user("v@example.com"))
    assert response.status_code == 422
    assert "detail" in response.json()


def test_report_endpoints_are_rate_limited_per_user(client, make_user, db_session):
    headers = make_user("reports.limit@example.com")
    user_id = client.get("/auth/me", headers=headers).json()["id"]
    for _ in range(REPORT_PDFS_PER_USER.limit):
        limiter.record(REPORT_PDFS_PER_USER, user_id)
    for _ in range(REPORTS_PER_USER.limit):
        limiter.record(REPORTS_PER_USER, user_id)
    pdf = client.get("/reports/medical/pdf", headers=headers)
    assert pdf.status_code == 429 and "retry-after" in pdf.headers
    assert client.get("/reports/medical", headers=headers).status_code == 429
    # Another user is unaffected.
    assert client.get("/reports/medical", headers=make_user("reports.other@example.com")).status_code == 200


def test_rate_limiter_window_slides():
    now = [1000.0]
    rl = RateLimiter(clock=lambda: now[0])
    rule = Rule("t", 2, 60)
    rl.record(rule, "k")
    rl.record(rule, "k")
    assert rl.retry_after(rule, "k") == 60
    now[0] += 30
    assert rl.retry_after(rule, "k") == 30
    now[0] += 31
    assert rl.retry_after(rule, "k") is None  # the oldest hits have expired
    assert rl.retry_after(rule, "other") is None


def test_production_settings(monkeypatch):
    base = {"database_url": "postgresql+psycopg://localhost/example_test", "jwt_secret_key": "s" * 40}
    prod = Settings(_env_file=None, app_env="Production", frontend_url="https://a.example/, https://b.example", **base)
    assert prod.is_production
    assert prod.cors_origins == ["https://a.example", "https://b.example"]
    assert not Settings(_env_file=None, app_env="development", **base).is_production
    with pytest.raises(ValueError):
        Settings(_env_file=None, database_url=base["database_url"], jwt_secret_key="too-short")
