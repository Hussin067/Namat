"""Medical history the user reports about themselves.

Everything here is self-reported context for a clinician: Namat never checks
it, never uses it in the statistical analysis, and never draws conclusions
from it. `confirmation` records what the user says about each item
(confirmed by a clinician, self-reported, or unsure).
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.user import User

CONDITION_CATEGORIES = ("chronic_disease", "headache_disorder", "associated_condition", "serious_history")
CONDITION_STATUSES = ("active", "resolved", "monitoring")
CONFIRMATIONS = ("clinician_confirmed", "self_reported", "unsure")
ALLERGY_TYPES = ("medication", "food", "environmental", "other")
ALLERGY_SEVERITIES = ("mild", "moderate", "severe", "unknown")


def _one_of(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class MedicalCondition(TimestampMixin, Base):
    __tablename__ = "medical_conditions"
    __table_args__ = (
        CheckConstraint(_one_of("category", CONDITION_CATEGORIES), name="category_valid"),
        CheckConstraint(_one_of("status", CONDITION_STATUSES), name="status_valid"),
        CheckConstraint(_one_of("confirmation", CONFIRMATIONS), name="confirmation_valid"),
        Index("ix_medical_conditions_user_id_category", "user_id", "category"),
    )

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    condition_name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20))
    confirmation: Mapped[str] = mapped_column(String(30))
    diagnosis_date: Mapped[date | None]
    notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="medical_conditions")


class MedicalAllergy(TimestampMixin, Base):
    __tablename__ = "medical_allergies"
    __table_args__ = (
        CheckConstraint(_one_of("type", ALLERGY_TYPES), name="type_valid"),
        CheckConstraint(_one_of("severity", ALLERGY_SEVERITIES), name="severity_valid"),
        Index("ix_medical_allergies_user_id", "user_id"),
    )

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(20))
    reaction: Mapped[str | None] = mapped_column(String(200))
    severity: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="medical_allergies")


class MedicalProcedure(TimestampMixin, Base):
    __tablename__ = "medical_procedures"
    __table_args__ = (Index("ix_medical_procedures_user_id", "user_id"),)

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    procedure_date: Mapped[date | None]
    notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="medical_procedures")


class MedicalNotes(TimestampMixin, Base):
    """Free-text additional notes: at most one row per user."""

    __tablename__ = "medical_notes"

    id: Mapped[uuid_pk]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    notes: Mapped[str] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="medical_notes")
