"""Response body for GET /analytics/dashboard."""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

Period = Literal["7d", "30d", "3m", "6m", "12m"]
Interval = Literal["day", "week", "month"]


class AnalyticsRange(BaseModel):
    period: Literal["7d", "30d", "3m", "6m", "12m", "custom"]
    start_date: date  # inclusive, in `timezone`
    end_date: date  # inclusive, in `timezone`
    days: int
    interval: Interval
    timezone: str  # IANA name used for every calendar-day calculation


class LatestEpisode(BaseModel):
    id: uuid.UUID
    started_at: datetime
    peak_intensity: int | None


class Summary(BaseModel):
    total_episodes: int
    headache_days: int
    average_intensity: float | None  # 0–10, one decimal; None when nothing was rated
    rated_episodes: int  # episodes that have an intensity
    average_duration_minutes: int | None  # None when no episode has ended yet
    episodes_with_duration: int
    latest_episode: LatestEpisode | None


class FrequencyPoint(BaseModel):
    date: date  # start of the day / ISO week (Monday) / month
    count: int


class IntensityPoint(BaseModel):
    date: date
    average_intensity: float | None  # None (not 0) when the bucket has no rated episode
    rated_episodes: int


class SymptomCount(BaseModel):
    id: int
    name: str  # catalog name; the frontend translates it
    count: int  # number of the user's episodes in range with this symptom


class DashboardAnalytics(BaseModel):
    range: AnalyticsRange
    summary: Summary
    frequency: list[FrequencyPoint]
    intensity_trend: list[IntensityPoint]
    symptoms: list[SymptomCount]
