from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.user import User


class SleepLog(TimestampMixin, Base):
    """One night of sleep. At most one log per user per night."""

    __tablename__ = "sleep_logs"
    __table_args__ = (
        # Also serves as the index for "my sleep logs by date".
        UniqueConstraint("user_id", "sleep_date"),
        CheckConstraint("wake_time > bedtime", name="wake_after_bed"),
        CheckConstraint(
            "wake_time - bedtime <= INTERVAL '24 hours'", name="max_24_hours"
        ),
        CheckConstraint("quality BETWEEN 1 AND 5", name="quality_range"),
        CheckConstraint("awakenings >= 0", name="awakenings_non_negative"),
    )

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    sleep_date: Mapped[date]  
    bedtime: Mapped[datetime]
    wake_time: Mapped[datetime]
    quality: Mapped[int | None] = mapped_column(SmallInteger) 
    awakenings: Mapped[int | None] = mapped_column(SmallInteger)
    notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="sleep_logs")

    @property
    def duration_minutes(self) -> int:
        # Derived, not stored, so it can never disagree with bedtime/wake_time.
        return int((self.wake_time - self.bedtime).total_seconds() // 60)
