from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.daily_factor import DailyFactor
    from app.models.episode import HeadacheEpisode
    from app.models.medication import MedicationDose
    from app.models.sleep import SleepLog


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid_pk]
    email: Mapped[str] = mapped_column(String(320))
    # Only a one-way hash (Argon2/bcrypt) is ever stored, never the password.
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(100))
    # IANA name such as "Asia/Riyadh"; decides where the user's "day" starts.
    timezone: Mapped[str] = mapped_column(
        String(64), default="UTC", server_default="UTC"
    )
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))

    # Deleting a user deletes all their data. passive_deletes lets PostgreSQL's
    # ON DELETE CASCADE do the work instead of loading every row first.
    episodes: Mapped[list[HeadacheEpisode]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    medication_doses: Mapped[list[MedicationDose]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    sleep_logs: Mapped[list[SleepLog]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    daily_factors: Mapped[list[DailyFactor]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        # Deliberately leaves out password_hash so it never reaches logs.
        return f"<User id={self.id} email={self.email!r}>"


# Case-insensitive uniqueness: "Sara@x.com" and "sara@x.com" are the same account.
Index("uq_users_email_lower", func.lower(User.email), unique=True)
