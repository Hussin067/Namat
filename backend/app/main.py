
from fastapi import FastAPI

app = FastAPI(
    title="Namat - Migraine Tracker API",
    description="API for tracking migraine episodes and related factors.",
    version="0.1.0",
)


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
