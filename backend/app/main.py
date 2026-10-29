
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import analytics, auth, daily_factors, episodes, insights, reports, sleep, symptoms
from app.core.config import get_settings
from app.core.middleware import harden_responses

settings = get_settings()

app = FastAPI(
    title="Namat - Migraine Tracker API",
    description="API for tracking migraine episodes and related factors.",
    version="0.1.0",
    # The interactive API docs are for development; production doesn't publish them.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

# Middleware added last runs first. harden_responses sits inside CORS, so even
# an unexpected 500 reaches the browser with its CORS headers.
app.middleware("http")(harden_responses)

# Only the configured frontend origin(s) may call the API from a browser. In
# production the frontend reaches the API through its own site (Vercel /api
# rewrite), so CORS only matters for a direct cross-origin setup. Credentials
# are allowed so the session cookie is sent; origins are never a wildcard.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    # Lets the browser read the PDF's suggested (safe) file name, and how long
    # to wait after a 429.
    expose_headers=["Content-Disposition", "Retry-After"],
)

app.include_router(auth.router)
app.include_router(episodes.router)
app.include_router(symptoms.router)
app.include_router(analytics.router)
app.include_router(insights.router)
app.include_router(sleep.router)
app.include_router(daily_factors.router)
app.include_router(reports.router)


@app.get("/")
def home():
    return {
        "message": "Namat Migraine Tracker API is running!"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }
