from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.user import User


class DailyFactor(TimestampMixin, Base):
    """Possible triggers for one day. Every factor is optional (NULL = not recorded)."""

    __tablename__ = "daily_factors"
    __table_args__ = (
        # Also serves as the index for "my factors by date".
        UniqueConstraint("user_id", "log_date"),
        CheckConstraint("stress_level BETWEEN 0 AND 10", name="stress_level_range"),
        CheckConstraint("caffeine_mg >= 0", name="caffeine_non_negative"),
        CheckConstraint("water_ml >= 0", name="water_non_negative"),
        CheckConstraint("alcohol_units >= 0", name="alcohol_non_negative"),
        CheckConstraint(
            "exercise_minutes BETWEEN 0 AND 1440", name="exercise_minutes_range"
        ),
    )

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    log_date: Mapped[date]
    stress_level: Mapped[int | None] = mapped_column(SmallInteger)  # 0 .. 10
    caffeine_mg: Mapped[int | None]
    water_ml: Mapped[int | None]
    alcohol_units: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    exercise_minutes: Mapped[int | None] = mapped_column(SmallInteger)
    skipped_meal: Mapped[bool | None]
    menstruating: Mapped[bool | None]
    notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="daily_factors")
