"""Response body for GET /insights."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel


class InsightPeriod(BaseModel):
    period: Literal["7d", "30d", "3m", "6m", "12m", "custom"]
    start: date  # inclusive, in `timezone`
    end: date  # inclusive, in `timezone`
    days: int
    timezone: str


class PreviousPeriod(BaseModel):
    start: date
    end: date


class InsightSummary(BaseModel):
    total_episodes: int
    headache_days: int
    episodes_per_week: float | None
    average_intensity: float | None  # None when nothing was rated
    highest_intensity: int | None
    rated_episodes: int
    intensity_distribution: dict[str, int]  # none / mild / moderate / severe / very_severe
    time_of_day: dict[str, int]  # morning / afternoon / evening / night
    average_sleep_hours: float | None
    sleep_nights: int
    factor_days: int


class DateSpan(BaseModel):
    start: date
    end: date


class Insight(BaseModel):
    id: str  # stable kind of insight, e.g. "sleep_rate_higher"; the frontend translates by it
    category: Literal["frequency", "intensity", "timing", "symptoms", "sleep", "factors", "medication"]
    title: str  # English fallback text; the UI uses its own translations
    description: str
    evidence: dict[str, Any]  # the numbers behind the observation
    sample_size: int
    evidence_level: Literal["limited", "observed"]
    date_range: DateSpan
    comparison: dict[str, Any] | None = None


class DataGap(BaseModel):
    code: Literal["episodes", "previous_period", "sleep", "sleep_variation", "daily_factors"]
    needed: int | None
    have: int | None


class InsightsResponse(BaseModel):
    period: InsightPeriod
    previous_period: PreviousPeriod
    data_status: Literal["insufficient", "partial", "sufficient"]
    summary: InsightSummary
    insights: list[Insight]
    data_gaps: list[DataGap]
    generated_at: datetime
