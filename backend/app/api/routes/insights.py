"""Personal pattern insights for the authenticated user (see app/services/insights.py)."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.analytics import Period
from app.schemas.insights import InsightsResponse
from app.services.analytics import AnalyticsRangeError, resolve_range
from app.services.insights import build_insights

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("", response_model=InsightsResponse)
def insights(
    user: CurrentUser,
    db: DbSession,
    response: Response,
    period: Annotated[Period, Query(description="Preset range ending today: 7d, 30d, 3m (90 days), 6m (180 days) or 12m (365 days)")] = "3m",
    start_date: Annotated[date | None, Query(description="Custom range start (inclusive). Overrides period.")] = None,
    end_date: Annotated[date | None, Query(description="Custom range end (inclusive). Required with start_date.")] = None,
) -> dict:
    """Observations from the user's own records, with the evidence behind each one.

    No user id is accepted: the data always belongs to the token's user.
    Insights are calculated on request and never stored.
    """
    try:
        rng = resolve_range(user, period, start_date, end_date, interval=None)
    except AnalyticsRangeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from None
    # Personal health information: never keep it in shared or browser caches.
    response.headers["Cache-Control"] = "no-store, private"
    return build_insights(db, user, rng)
