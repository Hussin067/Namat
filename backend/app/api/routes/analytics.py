"""Dashboard analytics for the authenticated user (see app/services/analytics.py)."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.analytics import DashboardAnalytics, Interval, Period
from app.services.analytics import AnalyticsRangeError, build_dashboard, resolve_range

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=DashboardAnalytics)
def dashboard(
    user: CurrentUser,
    db: DbSession,
    period: Annotated[Period, Query(description="Preset range ending today: 7d, 30d, 3m (90 days), 6m (180 days) or 12m (365 days)")] = "30d",
    start_date: Annotated[date | None, Query(description="Custom range start (inclusive). Overrides period.")] = None,
    end_date: Annotated[date | None, Query(description="Custom range end (inclusive). Required with start_date.")] = None,
    interval: Annotated[Interval | None, Query(description="day, week or month; chosen from the range length when omitted")] = None,
) -> dict:
    """Summary, frequency, intensity trend and symptom counts for one date range.

    No user id is accepted: the data always belongs to the token's user.
    """
    try:
        rng = resolve_range(user, period, start_date, end_date, interval)
    except AnalyticsRangeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from None
    return build_dashboard(db, user, rng)
