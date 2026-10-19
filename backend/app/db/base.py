"""Declarative base and column helpers shared by all SQLAlchemy models."""

import uuid
from datetime import datetime
from typing import Annotated

from sqlalchemy import DateTime, MetaData, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Predictable constraint names, so Alembic can find and alter them later.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # Every datetime column is TIMESTAMPTZ: stored in UTC, never ambiguous.
    type_annotation_map = {datetime: DateTime(timezone=True)}


# UUID primary key. Python generates it (so it's known before INSERT);
# the server default covers rows inserted with raw SQL.
uuid_pk = Annotated[
    uuid.UUID,
    mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    ),
]


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
