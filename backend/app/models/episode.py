from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.medication import MedicationDose
    from app.models.user import User

PAIN_LOCATIONS = (
    "left",
    "right",
    "bilateral",
    "frontal",
    "occipital",
    "behind_eye",
    "other",
)


class HeadacheEpisode(TimestampMixin, Base):
    """One migraine/headache attack."""

    __tablename__ = "headache_episodes"
    __table_args__ = (
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at", name="ended_after_started"
        ),
        CheckConstraint(
            "peak_intensity BETWEEN 0 AND 10", name="peak_intensity_range"
        ),
        CheckConstraint(
            "pain_location IN (" + ", ".join(f"'{p}'" for p in PAIN_LOCATIONS) + ")",
            name="pain_location_valid",
        ),
        # Target for medication_doses' composite FK (episode_id, user_id),
        # which guarantees a dose and its episode belong to the same user.
        UniqueConstraint("id", "user_id"),
    )

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    started_at: Mapped[datetime]
    ended_at: Mapped[datetime | None]  # NULL while the episode is ongoing
    peak_intensity: Mapped[int | None] = mapped_column(SmallInteger)
    pain_location: Mapped[str | None] = mapped_column(String(30))
    had_aura: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="episodes")
    symptom_links: Mapped[list[EpisodeSymptom]] = relationship(
        back_populates="episode", cascade="all, delete-orphan", passive_deletes=True
    )
    # Join on both columns; only episode_id is written through this
    # relationship, so unlinking a dose never touches its user_id.
    medication_doses: Mapped[list[MedicationDose]] = relationship(
        back_populates="episode",
        primaryjoin="and_(HeadacheEpisode.id == MedicationDose.episode_id, "
        "HeadacheEpisode.user_id == MedicationDose.user_id)",
        foreign_keys="MedicationDose.episode_id",
        passive_deletes=True,
    )


# "My episodes, newest first" is the most common query.
Index(
    "ix_headache_episodes_user_id_started_at",
    HeadacheEpisode.user_id,
    HeadacheEpisode.started_at.desc(),
)


class Symptom(Base):
    """Shared catalog of symptoms (nausea, light sensitivity, ...)."""

    __tablename__ = "symptoms"

    id: Mapped[int] = mapped_column(SmallInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    category: Mapped[str] = mapped_column(String(30))

    def __repr__(self) -> str:
        return f"<Symptom {self.name!r}>"


class EpisodeSymptom(Base):
    """Which symptoms occurred during an episode (many-to-many link)."""

    __tablename__ = "episode_symptoms"
    __table_args__ = (
        CheckConstraint("severity BETWEEN 1 AND 3", name="severity_range"),
    )

    # Composite primary key: the same symptom can't be added twice to one episode.
    episode_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("headache_episodes.id", ondelete="CASCADE"), primary_key=True
    )
    # RESTRICT: a symptom still in use can't be removed from the catalog.
    symptom_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("symptoms.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    )
    severity: Mapped[int | None] = mapped_column(SmallInteger)  # 1 mild .. 3 severe

    episode: Mapped[HeadacheEpisode] = relationship(back_populates="symptom_links")
    symptom: Mapped[Symptom] = relationship()
