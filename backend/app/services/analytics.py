"""Dashboard analytics, aggregated in PostgreSQL for one user.

Definitions:
- Time zone: the user's `timezone` (IANA name); UTC if it's missing or unknown.
  Every calendar-day rule below uses it.
- Range: inclusive local dates [start_date, end_date]. An episode belongs to
  the range when its start time falls on one of those dates.
- Headache days: distinct local dates in the range touched by an episode,
  from its start date to its end date. An ongoing episode counts only its
  start date, because its end is unknown.
- Average duration: episodes that have ended (end >= start) only.
- Average intensity: rated episodes only (NULL intensities are skipped).
- Buckets: day, ISO week (Monday start) or calendar month, by start time.
  The API returns every bucket in the range, with count 0 / no average for
  empty ones, so charts get a continuous series.
- Symptoms: number of the user's in-range episodes linked to each symptom.
  (episode_id, symptom_id) is the primary key, so nothing is double counted.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, bindparam, func, select, text
from sqlalchemy.orm import Session

from app.models import EpisodeSymptom, HeadacheEpisode, Symptom, User

PERIOD_DAYS = {"7d": 7, "30d": 30, "3m": 90, "6m": 180, "12m": 365}
MAX_RANGE_DAYS = 366
EARLIEST_DATE = date(2000, 1, 1)


class AnalyticsRangeError(ValueError):
    """Invalid date filters; the route turns this into a 422."""


@dataclass(frozen=True)
class DateRange:
    period: str
    start: date
    end: date
    interval: str
    tz_name: str
    tz: ZoneInfo

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def utc_bounds(self) -> tuple[datetime, datetime]:
        """[start, end) as UTC instants: local midnight of start → local midnight after end."""
        lower = datetime.combine(self.start, time.min, self.tz).astimezone(timezone.utc)
        upper = datetime.combine(self.end + timedelta(days=1), time.min, self.tz).astimezone(timezone.utc)
        return lower, upper


def user_timezone(user: User) -> tuple[str, ZoneInfo]:
    try:
        return user.timezone, ZoneInfo(user.timezone)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return "UTC", ZoneInfo("UTC")


def resolve_range(
    user: User,
    period: str,
    start_date: date | None,
    end_date: date | None,
    interval: str | None,
    today: date | None = None,
) -> DateRange:
    tz_name, tz = user_timezone(user)
    if (start_date is None) != (end_date is None):
        raise AnalyticsRangeError("start_date and end_date must be sent together")

    if start_date is not None:  # a custom range wins over the preset
        if start_date > end_date:
            raise AnalyticsRangeError("start_date must be on or before end_date")
        if start_date < EARLIEST_DATE:
            raise AnalyticsRangeError(f"start_date must be {EARLIEST_DATE.isoformat()} or later")
        if (end_date - start_date).days + 1 > MAX_RANGE_DAYS:
            raise AnalyticsRangeError(f"a custom range can cover at most {MAX_RANGE_DAYS} days")
        label, start, end = "custom", start_date, end_date
    else:
        end = today or datetime.now(tz).date()
        start = end - timedelta(days=PERIOD_DAYS[period] - 1)
        label = period

    days = (end - start).days + 1
    if interval is None:  # readable defaults: ≤ 31 points for short ranges, ~26 for 6 months
        interval = "day" if days <= 31 else "week" if days <= 190 else "month"
    return DateRange(label, start, end, interval, tz_name, tz)


def _bucket_start(day: date, interval: str) -> date:
    if interval == "week":
        return day - timedelta(days=day.weekday())  # Monday
    if interval == "month":
        return day.replace(day=1)
    return day


def _next_bucket(day: date, interval: str) -> date:
    if interval == "week":
        return day + timedelta(days=7)
    if interval == "month":
        return (day.replace(day=28) + timedelta(days=4)).replace(day=1)
    return day + timedelta(days=1)


def _round1(value) -> float | None:
    return None if value is None else round(float(value), 1)


def build_dashboard(db: Session, user: User, rng: DateRange) -> dict:
    lower, upper = rng.utc_bounds()
    in_range = and_(
        HeadacheEpisode.user_id == user.id,  # every query is scoped to the token's user
        HeadacheEpisode.started_at >= lower,
        HeadacheEpisode.started_at < upper,
    )
    ended = and_(HeadacheEpisode.ended_at.is_not(None), HeadacheEpisode.ended_at >= HeadacheEpisode.started_at)
    minutes = func.extract("epoch", HeadacheEpisode.ended_at - HeadacheEpisode.started_at) / 60

    # 1. Summary counts and averages: one aggregate query.
    totals = db.execute(
        select(
            func.count(),
            func.avg(HeadacheEpisode.peak_intensity),
            func.count(HeadacheEpisode.peak_intensity),
            func.avg(minutes).filter(ended),
            func.count().filter(ended),
        ).where(in_range)
    ).one()

    latest = db.execute(
        select(HeadacheEpisode.id, HeadacheEpisode.started_at, HeadacheEpisode.peak_intensity)
        .where(in_range)
        .order_by(HeadacheEpisode.started_at.desc(), HeadacheEpisode.id.desc())
        .limit(1)
    ).first()

    # 2. Headache days: each episode's local dates from start to end, de-duplicated.
    headache_days = db.execute(
        text(
            """
            SELECT count(DISTINCT d::date)
            FROM headache_episodes e,
                 generate_series(
                     (e.started_at AT TIME ZONE :tz)::date,
                     (COALESCE(e.ended_at, e.started_at) AT TIME ZONE :tz)::date,
                     interval '1 day'
                 ) AS d
            WHERE e.user_id = :user_id
              AND e.started_at >= :lower AND e.started_at < :upper
              AND d::date BETWEEN :start AND :end
            """
        ).bindparams(
            bindparam("tz", rng.tz_name),
            bindparam("user_id", user.id),
            bindparam("lower", lower),
            bindparam("upper", upper),
            bindparam("start", rng.start),
            bindparam("end", rng.end),
        )
    ).scalar_one()

    # 3. Frequency and intensity per bucket: one grouped query, zero-filled below.
    local_start = func.timezone(rng.tz_name, HeadacheEpisode.started_at)
    bucket = func.date_trunc(rng.interval, local_start).label("bucket")
    rows = db.execute(
        select(
            bucket,
            func.count(),
            func.avg(HeadacheEpisode.peak_intensity),
            func.count(HeadacheEpisode.peak_intensity),
        )
        .where(in_range)
        .group_by(bucket)
    ).all()
    by_bucket = {row[0].date(): row for row in rows}

    frequency, intensity = [], []
    cursor = _bucket_start(rng.start, rng.interval)
    while cursor <= rng.end:
        row = by_bucket.get(cursor)
        frequency.append({"date": cursor, "count": row[1] if row else 0})
        intensity.append(
            {"date": cursor, "average_intensity": _round1(row[2]) if row else None, "rated_episodes": row[3] if row else 0}
        )
        cursor = _next_bucket(cursor, rng.interval)

    # 4. Symptom counts for in-range episodes, most frequent first.
    symptom_rows = db.execute(
        select(Symptom.id, Symptom.name, func.count())
        .join(EpisodeSymptom, EpisodeSymptom.symptom_id == Symptom.id)
        .join(HeadacheEpisode, HeadacheEpisode.id == EpisodeSymptom.episode_id)
        .where(in_range)
        .group_by(Symptom.id, Symptom.name)
        .order_by(func.count().desc(), Symptom.id)
    ).all()

    return {
        "range": {
            "period": rng.period,
            "start_date": rng.start,
            "end_date": rng.end,
            "days": rng.days,
            "interval": rng.interval,
            "timezone": rng.tz_name,
        },
        "summary": {
            "total_episodes": totals[0],
            "headache_days": headache_days,
            "average_intensity": _round1(totals[1]),
            "rated_episodes": totals[2],
            "average_duration_minutes": None if totals[3] is None else round(float(totals[3])),
            "episodes_with_duration": totals[4],
            "latest_episode": (
                {"id": latest[0], "started_at": latest[1], "peak_intensity": latest[2]} if latest else None
            ),
        },
        "frequency": frequency,
        "intensity_trend": intensity,
        "symptoms": [{"id": r[0], "name": r[1], "count": r[2]} for r in symptom_rows],
    }
