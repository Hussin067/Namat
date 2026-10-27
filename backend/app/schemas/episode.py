"""Request and response bodies for /episodes and /symptoms.

Ownership never comes from the request: there is no user_id field anywhere,
and extra="forbid" rejects one if a client sends it. The owner is always the
user from the validated access token (see app.api.deps.get_current_user).
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.episode import PAIN_LOCATIONS

# Same limits as the frontend form (frontend/src/features/episodes).
NOTES_MAX_LENGTH = 2000
MAX_SYMPTOMS = 13  # the size of the symptom catalog
MAX_MEDICATIONS = 10
# Small allowance for clock differences between the user's device and the server.
FUTURE_TOLERANCE = timedelta(minutes=5)

PainLocation = Literal[PAIN_LOCATIONS]  # type: ignore[valid-type]


def check_not_future(value: datetime | None, field: str) -> None:
    if value is not None and value > datetime.now(timezone.utc) + FUTURE_TOLERANCE:
        raise ValueError(f"{field} can't be in the future")


def clean_text(value: str | None) -> str | None:
    """Trim whitespace; an empty string means "no value"."""
    if value is None:
        return None
    value = value.strip()
    return value or None


# --- Symptoms ---------------------------------------------------------------

class SymptomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str


# --- Medication doses taken for an episode ----------------------------------

class MedicationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    medication_name: str = Field(min_length=1, max_length=120)
    dose_amount: Decimal | None = Field(default=None, gt=0, max_digits=8, decimal_places=2)
    dose_unit: str | None = Field(default=None, max_length=20)
    # Defaults to the episode's start time when omitted.
    taken_at: AwareDatetime | None = None
    relief_rating: int | None = Field(default=None, ge=0, le=3)  # 0 none .. 3 complete

    @field_validator("medication_name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        value = clean_text(value)
        if not value:
            raise ValueError("medication_name can't be blank")
        return value

    @field_validator("dose_unit")
    @classmethod
    def clean_unit(cls, value: str | None) -> str | None:
        return clean_text(value)

    @field_validator("taken_at")
    @classmethod
    def taken_not_future(cls, value: datetime | None) -> datetime | None:
        check_not_future(value, "taken_at")
        return value


class MedicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    medication_name: str
    dose_amount: Decimal | None
    dose_unit: str | None
    taken_at: datetime
    relief_rating: int | None


# --- Episodes ---------------------------------------------------------------

class _EpisodeFields(BaseModel):
    """Validation shared by create and update."""

    model_config = ConfigDict(extra="forbid")

    @field_validator("notes", check_fields=False)
    @classmethod
    def _clean_notes(cls, value: str | None) -> str | None:
        return clean_text(value)

    @field_validator("started_at", "ended_at", check_fields=False)
    @classmethod
    def _not_future(cls, value: datetime | None, info) -> datetime | None:
        check_not_future(value, info.field_name)
        return value

    @field_validator("symptom_ids", check_fields=False)
    @classmethod
    def _unique_symptoms(cls, value: list[int] | None) -> list[int] | None:
        if value is not None and len(set(value)) != len(value):
            raise ValueError("symptom_ids must not repeat")
        return value


class EpisodeCreate(_EpisodeFields):
    started_at: AwareDatetime
    ended_at: AwareDatetime | None = None  # None while the episode is ongoing
    peak_intensity: int = Field(ge=0, le=10)
    pain_location: PainLocation | None = None
    had_aura: bool = False
    notes: str | None = Field(default=None, max_length=NOTES_MAX_LENGTH)
    symptom_ids: list[int] = Field(default_factory=list, max_length=MAX_SYMPTOMS)
    medications: list[MedicationIn] = Field(default_factory=list, max_length=MAX_MEDICATIONS)

    @model_validator(mode="after")
    def _end_after_start(self) -> "EpisodeCreate":
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("ended_at can't be earlier than started_at")
        return self


class EpisodeUpdate(_EpisodeFields):
    """Partial update: only the fields that are sent change.

    symptom_ids and medications, when sent, replace the episode's whole list.
    The end-after-start rule is checked against the stored values in the route,
    because only one of the two times may be sent.
    """

    started_at: AwareDatetime | None = None
    ended_at: AwareDatetime | None = None
    peak_intensity: int | None = Field(default=None, ge=0, le=10)
    pain_location: PainLocation | None = None
    had_aura: bool | None = None
    notes: str | None = Field(default=None, max_length=NOTES_MAX_LENGTH)
    symptom_ids: list[int] | None = Field(default=None, max_length=MAX_SYMPTOMS)
    medications: list[MedicationIn] | None = Field(default=None, max_length=MAX_MEDICATIONS)

    @model_validator(mode="after")
    def _required_fields_stay_set(self) -> "EpisodeUpdate":
        # These may be left out, but can't be cleared: the episode needs them.
        for field in ("started_at", "peak_intensity", "had_aura", "symptom_ids", "medications"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} can't be null")
        return self


class EpisodeOut(BaseModel):
    id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None
    peak_intensity: int | None
    pain_location: str | None
    had_aura: bool
    notes: str | None
    symptoms: list[SymptomOut]
    medications: list[MedicationOut]
    created_at: datetime
    updated_at: datetime


class EpisodeList(BaseModel):
    items: list[EpisodeOut]
    total: int
    limit: int
    offset: int
