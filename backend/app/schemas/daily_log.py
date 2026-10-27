"""Request and response bodies for /sleep-logs and /daily-factors.

As with episodes, there is no user_id field anywhere and extra="forbid"
rejects one: the owner is always the user from the validated access token.

Every value in a daily-factor record is optional. A field that is left out
(NULL) means "not recorded", which is different from a recorded 0 or "no".
"""

import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.episode import NOTES_MAX_LENGTH, check_not_future, clean_text

MAX_SLEEP = timedelta(hours=24)  # same as the sleep_logs max_24_hours check
# A night's date is when it starts. Bedtime is usually that evening, or after
# midnight on the next day; the margin allows for any UTC offset (up to ±14 h).
BEDTIME_EARLIEST = timedelta(hours=-14)  # from 00:00 on the night's date (UTC)
BEDTIME_LATEST = timedelta(days=1, hours=12 + 14)  # until 12:00 the next day, plus the margin


def check_day_not_future(value: date | None, field: str) -> None:
    # One day of tolerance: "today" in the user's time zone can be tomorrow in UTC.
    if value is not None and value > datetime.now(timezone.utc).date() + timedelta(days=1):
        raise ValueError(f"{field} can't be in the future")


def check_sleep_times(sleep_date: date, bedtime: datetime, wake_time: datetime) -> None:
    """Rules shared by create and update; raises ValueError with a clear message."""
    if wake_time <= bedtime:
        raise ValueError("wake_time must be after bedtime")
    if wake_time - bedtime > MAX_SLEEP:
        raise ValueError("a night of sleep can't be longer than 24 hours")
    night_start = datetime.combine(sleep_date, time.min, timezone.utc)
    if not night_start + BEDTIME_EARLIEST <= bedtime <= night_start + BEDTIME_LATEST:
        raise ValueError("bedtime must be on the evening of sleep_date or early the next morning")


class _NotesMixin(BaseModel):
    @field_validator("notes", check_fields=False)
    @classmethod
    def _clean_notes(cls, value: str | None) -> str | None:
        return clean_text(value)


# --- Sleep ------------------------------------------------------------------

class _SleepFields(_NotesMixin):
    model_config = ConfigDict(extra="forbid")

    @field_validator("bedtime", "wake_time", check_fields=False)
    @classmethod
    def _not_future(cls, value: datetime | None, info) -> datetime | None:
        check_not_future(value, info.field_name)
        return value

    @field_validator("sleep_date", check_fields=False)
    @classmethod
    def _date_not_future(cls, value: date | None) -> date | None:
        check_day_not_future(value, "sleep_date")
        return value


class SleepLogCreate(_SleepFields):
    sleep_date: date = Field(description="The date the night started (the evening you went to bed).")
    bedtime: AwareDatetime
    wake_time: AwareDatetime
    quality: int | None = Field(default=None, ge=1, le=5)  # 1 very poor .. 5 very good
    awakenings: int | None = Field(default=None, ge=0, le=50)
    notes: str | None = Field(default=None, max_length=NOTES_MAX_LENGTH)

    @model_validator(mode="after")
    def _times(self) -> "SleepLogCreate":
        check_sleep_times(self.sleep_date, self.bedtime, self.wake_time)
        return self


class SleepLogUpdate(_SleepFields):
    """Partial update. The time rules are checked against stored values in the route."""

    sleep_date: date | None = None
    bedtime: AwareDatetime | None = None
    wake_time: AwareDatetime | None = None
    quality: int | None = Field(default=None, ge=1, le=5)
    awakenings: int | None = Field(default=None, ge=0, le=50)
    notes: str | None = Field(default=None, max_length=NOTES_MAX_LENGTH)

    @model_validator(mode="after")
    def _required_fields_stay_set(self) -> "SleepLogUpdate":
        for field in ("sleep_date", "bedtime", "wake_time"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} can't be null")
        return self


class SleepLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sleep_date: date
    bedtime: datetime
    wake_time: datetime
    duration_minutes: int
    quality: int | None
    awakenings: int | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class SleepLogList(BaseModel):
    items: list[SleepLogOut]
    total: int
    limit: int
    offset: int


# --- Daily factors ----------------------------------------------------------

FACTOR_FIELDS = (
    "stress_level",
    "caffeine_mg",
    "water_ml",
    "alcohol_units",
    "exercise_minutes",
    "skipped_meal",
    "menstruating",
)


class _FactorValues(_NotesMixin):
    model_config = ConfigDict(extra="forbid")

    stress_level: int | None = Field(default=None, ge=0, le=10)
    caffeine_mg: int | None = Field(default=None, ge=0, le=5000)
    water_ml: int | None = Field(default=None, ge=0, le=20000)
    alcohol_units: Decimal | None = Field(default=None, ge=0, le=99, max_digits=4, decimal_places=1)
    exercise_minutes: int | None = Field(default=None, ge=0, le=1440)
    skipped_meal: bool | None = None
    menstruating: bool | None = None
    notes: str | None = Field(default=None, max_length=NOTES_MAX_LENGTH)

    @field_validator("log_date", check_fields=False)
    @classmethod
    def _date_not_future(cls, value: date | None) -> date | None:
        check_day_not_future(value, "log_date")
        return value


class DailyFactorCreate(_FactorValues):
    log_date: date

    @model_validator(mode="after")
    def _something_recorded(self) -> "DailyFactorCreate":
        if all(getattr(self, f) is None for f in FACTOR_FIELDS) and self.notes is None:
            raise ValueError("record at least one factor or a note")
        return self


class DailyFactorUpdate(_FactorValues):
    """Partial update. Sending null for a factor clears it (back to "not recorded")."""

    log_date: date | None = None

    @model_validator(mode="after")
    def _date_stays_set(self) -> "DailyFactorUpdate":
        if "log_date" in self.model_fields_set and self.log_date is None:
            raise ValueError("log_date can't be null")
        return self


class DailyFactorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    log_date: date
    stress_level: int | None
    caffeine_mg: int | None
    water_ml: int | None
    alcohol_units: Decimal | None
    exercise_minutes: int | None
    skipped_meal: bool | None
    menstruating: bool | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class DailyFactorList(BaseModel):
    items: list[DailyFactorOut]
    total: int
    limit: int
    offset: int
