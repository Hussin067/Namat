"""Response hardening applied to every API response.

- An unexpected error becomes a plain JSON 500 ("Internal server error.") that
  never includes the exception, a traceback or any record. Because this runs
  inside the CORS middleware, the browser still receives CORS headers and the
  app can show "the server had a problem" instead of "can't reach the server".
- Security headers suited to a JSON API.
- Cache-Control: no-store by default: almost every response carries personal
  health data, and none of it may be kept by browsers or shared caches.
  Endpoints that set their own Cache-Control keep it.

Only the error type and the request path are logged (paths hold ids, never
health data). Full tracebacks are logged outside production only.
"""

import logging

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


async def harden_responses(request: Request, call_next):
    try:
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
