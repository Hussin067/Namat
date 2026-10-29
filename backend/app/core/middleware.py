"""Response hardening applied to every API response.

- An unexpected error becomes a plain JSON 500 ("Internal server error.") that
  never includes the exception, a traceback or any record. Because this runs
  inside the CORS middleware, the browser still receives CORS headers and the
  app can show "the server had a problem" instead of "can't reach the server".
- Security headers suited to a JSON API.
- Cache-Control: no-store by default: almost every response carries personal
  health data, and none of it may be kept by browsers or shared caches.
  Endpoints that set their own Cache-Control keep it.
- Origin check (CSRF defence in depth): a browser request that changes data
  (POST, PUT, PATCH, DELETE) is refused with 403 unless its Origin header is the
  API itself or one of the allowed frontend origins (FRONTEND_URL). This also
  covers login, registration and logout, which have no session to protect them.
  Requests without an Origin header (API clients, tests) are unaffected; browsers
  always send it on cross-site requests that change data.

Only the error type and the request path are logged (paths hold ids, never
health data). Full tracebacks are logged outside production only.
"""

import logging
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings

logger = logging.getLogger("namat")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-site",
}
# The API serves JSON and PDFs only: nothing may load or frame it. The
# interactive docs (development only) load their own scripts, so they're skipped.
API_CSP = "default-src 'none'; frame-ancestors 'none'"
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def origin_allowed(request: Request) -> bool:
    origin = request.headers.get("origin")
    if origin is None:
        return True
    origin = origin.rstrip("/")
    if origin in get_settings().cors_origins:
        return True
    # The API's own pages (e.g. the development /docs) are same-origin.
    return urlsplit(origin).netloc == request.headers.get("host", "")


async def harden_responses(request: Request, call_next):
    try:
        if request.method in UNSAFE_METHODS and not origin_allowed(request):
            response = JSONResponse({"detail": "Request origin not allowed."}, status_code=403)
        else:
            response = await call_next(request)
    except Exception as exc:  # anything a route didn't turn into an HTTP error
        logger.error(
            "Unhandled %s on %s %s",
            type(exc).__name__,
            request.method,
            request.url.path,
            exc_info=not get_settings().is_production,
        )
        response = JSONResponse({"detail": "Internal server error."}, status_code=500)

    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    if not request.url.path.startswith(DOCS_PATHS):
        response.headers.setdefault("Content-Security-Policy", API_CSP)
    response.headers.setdefault("Cache-Control", "no-store")
    return response
