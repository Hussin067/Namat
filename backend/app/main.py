
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth
from app.core.config import get_settings

app = FastAPI(
    title="Namat - Migraine Tracker API",
    description="API for tracking migraine episodes and related factors.",
    version="0.1.0",
)

# Only the configured frontend origin may call the API from a browser.
# Credentials (cookies) are off: the token travels in the Authorization header.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_url.rstrip("/")],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)


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
