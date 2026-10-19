from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.episode import HeadacheEpisode
    from app.models.user import User


class MedicationDose(TimestampMixin, Base):
    """A single dose taken, optionally linked to an episode."""

    __tablename__ = "medication_doses"
    __table_args__ = (
        # Composite FK: the linked episode must belong to the same user.
        # On episode delete, PostgreSQL 15+ nulls only episode_id (user_id stays).
        ForeignKeyConstraint(
            ["episode_id", "user_id"],
            ["headache_episodes.id", "headache_episodes.user_id"],
            ondelete="SET NULL (episode_id)",
        ),
        CheckConstraint("dose_amount > 0", name="dose_amount_positive"),
        CheckConstraint("relief_rating BETWEEN 0 AND 3", name="relief_rating_range"),
    )

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    # NULL for preventive doses that aren't tied to an attack.
    episode_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    medication_name: Mapped[str] = mapped_column(String(120))
    dose_amount: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    dose_unit: Mapped[str | None] = mapped_column(String(20))  # mg, ml, tablet ...
    taken_at: Mapped[datetime]
    # 0 none, 1 some, 2 good, 3 complete relief
    relief_rating: Mapped[int | None] = mapped_column(SmallInteger)
    notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="medication_doses")
    episode: Mapped[HeadacheEpisode | None] = relationship(
        back_populates="medication_doses",
        primaryjoin="and_(HeadacheEpisode.id == MedicationDose.episode_id, "
        "HeadacheEpisode.user_id == MedicationDose.user_id)",
        foreign_keys=[episode_id],
    )


Index(
    "ix_medication_doses_user_id_taken_at",
    MedicationDose.user_id,
    MedicationDose.taken_at.desc(),
)
