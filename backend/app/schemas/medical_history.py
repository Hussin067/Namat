"""Request and response bodies for /medical-history.

As everywhere else, there is no user_id field and extra="forbid" rejects one:
the owner is always the user from the validated session.

Updates are partial (PATCH): a required field can be changed but not cleared;
sending null for an optional field (a date, notes, a reaction) clears it.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.medical_history import (
    ALLERGY_SEVERITIES,
    ALLERGY_TYPES,
    CONDITION_CATEGORIES,
    CONDITION_STATUSES,
    CONFIRMATIONS,
)
from app.schemas.episode import NOTES_MAX_LENGTH, clean_text

NAME_MAX_LENGTH = 120
REACTION_MAX_LENGTH = 200
ADDITIONAL_NOTES_MAX_LENGTH = 4000
EARLIEST_DATE = date(1900, 1, 1)

Category = Literal[CONDITION_CATEGORIES]  # type: ignore[valid-type]
Status = Literal[CONDITION_STATUSES]  # type: ignore[valid-type]
Confirmation = Literal[CONFIRMATIONS]  # type: ignore[valid-type]
AllergyType = Literal[ALLERGY_TYPES]  # type: ignore[valid-type]
Severity = Literal[ALLERGY_SEVERITIES]  # type: ignore[valid-type]


def check_past_date(value: date | None, field: str) -> date | None:
    # One day of tolerance: "today" in the user's time zone can be tomorrow in UTC.
    if value is None:
        return None
    if value > datetime.now(timezone.utc).date() + timedelta(days=1):
        raise ValueError(f"{field} can't be in the future")
    if value < EARLIEST_DATE:
        raise ValueError(f"{field} is too far in the past")
    return value


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Fields that can't be null once set (checked on partial updates).
    required_fields: ClassVar[tuple[str, ...]] = ()

    @field_validator("condition_name", "name", check_fields=False)
    @classmethod
    def _name_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = clean_text(value)
        if not value:
            raise ValueError("name can't be blank")
        return value

    @field_validator("notes", "reaction", check_fields=False)
    @classmethod
    def _clean(cls, value: str | None) -> str | None:
        return clean_text(value)

    @field_validator("diagnosis_date", "procedure_date", check_fields=False)
    @classmethod
    def _date(cls, value: date | None, info) -> date | None:
        return check_past_date(value, info.field_name)

    @model_validator(mode="after")
    def _required_stay_set(self):
        for field in self.required_fields:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} can't be null")
        return self


# --- Conditions -------------------------------------------------------------

class ConditionCreate(_Body):
    condition_name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    category: Category
    status: Status = "active"
    confirmation: Confirmation = "self_reported"
    diagnosis_date: date | None = None
    notes: str | None = Field(default=None, max_length=NOTES_MAX_LENGTH)


class ConditionUpdate(_Body):
    required_fields = ("condition_name", "category", "status", "confirmation")

    condition_name: str | None = Field(default=None, min_length=1, max_length=NAME_MAX_LENGTH)
    category: Category | None = None
    status: Status | None = None
    confirmation: Confirmation | None = None
    diagnosis_date: date | None = None
    notes: str | None = Field(default=None, max_length=NOTES_MAX_LENGTH)


class ConditionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    condition_name: str
    category: str
    status: str
    confirmation: str
    diagnosis_date: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


# --- Allergies --------------------------------------------------------------

class AllergyCreate(_Body):
    name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    type: AllergyType
    reaction: str | None = Field(default=None, max_length=REACTION_MAX_LENGTH)
    severity: Severity = "unknown"
    notes: str | None = Field(default=None, max_length=NOTES_MAX_LENGTH)


class AllergyUpdate(_Body):
    required_fields = ("name", "type", "severity")

    name: str | None = Field(default=None, min_length=1, max_length=NAME_MAX_LENGTH)
    type: AllergyType | None = None
    reaction: str | None = Field(default=None, max_length=REACTION_MAX_LENGTH)
    severity: Severity | None = None
    notes: str | None = Field(default=None, max_length=NOTES_MAX_LENGTH)


class AllergyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type: str
    reaction: str | None
    severity: str
    notes: str | None
    created_at: datetime
    updated_at: datetime


# --- Procedures -------------------------------------------------------------

class ProcedureCreate(_Body):
    name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    procedure_date: date | None = None
    notes: str | None = Field(default=None, max_length=NOTES_MAX_LENGTH)


class ProcedureUpdate(_Body):
    required_fields = ("name",)

    name: str | None = Field(default=None, min_length=1, max_length=NAME_MAX_LENGTH)
    procedure_date: date | None = None
    notes: str | None = Field(default=None, max_length=NOTES_MAX_LENGTH)


class ProcedureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    procedure_date: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


# --- Additional notes -------------------------------------------------------

class NotesIn(_Body):
    """Replaces the notes. Null or an empty text removes them."""

    notes: str | None = Field(max_length=ADDITIONAL_NOTES_MAX_LENGTH)


class NotesOut(BaseModel):
    notes: str | None
    updated_at: datetime | None


# --- Everything at once -----------------------------------------------------

class MedicalHistoryOut(BaseModel):
    conditions: list[ConditionOut]
    allergies: list[AllergyOut]
    procedures: list[ProcedureOut]
    notes: NotesOut
