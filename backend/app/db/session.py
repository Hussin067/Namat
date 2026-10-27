"""Database engine and session factory."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

engine = create_engine(
    get_settings().database_url.get_secret_value(),
    pool_pre_ping=True,  # drop dead connections instead of failing a request
    # Database errors then show the SQL but not the values (notes, dates ...),
    # so health data can't end up in logs or tracebacks.
    hide_parameters=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
