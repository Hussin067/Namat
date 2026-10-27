"""GET /analytics/dashboard. Run from backend/ with:  python -m pytest

Every scenario uses fixed, hand-picked timestamps so the expected numbers can
be checked by hand. All data is synthetic and rolled back after each test.
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import EpisodeSymptom, HeadacheEpisode, User

URL = "/analytics/dashboard"
SEPT = {"start_date": "2026-09-01", "end_date": "2026-09-30"}
NAUSEA, LIGHT = 1, 3  # ids from the seeded symptom catalog


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def user_id(db, email: str):
    return db.scalar(select(User.id).where(User.email == email))


def add_episode(db, owner, start, end=None, intensity=None, symptoms=()):
    episode = HeadacheEpisode(user_id=owner, started_at=start, ended_at=end, peak_intensity=intensity)
    episode.symptom_links = [EpisodeSymptom(symptom_id=s) for s in symptoms]
    db.add(episode)
    db.flush()
    return episode


@pytest.fixture
def september(client, db_session, make_user):
    """User A with a known September plus episodes just outside it; returns A's headers."""
    headers = make_user("analytics.a@example.com")
    a = user_id(db_session, "analytics.a@example.com")
    add_episode(db_session, a, utc(2026, 9, 5, 10), utc(2026, 9, 5, 13), 6, [NAUSEA, LIGHT])  # 180 min
    add_episode(db_session, a, utc(2026, 9, 5, 20), utc(2026, 9, 5, 21), 4, [NAUSEA])  # 60 min, same day
    add_episode(db_session, a, utc(2026, 9, 10, 23), utc(2026, 9, 11, 2), 8, [LIGHT])  # 180 min, crosses midnight
    add_episode(db_session, a, utc(2026, 9, 20, 8))  # ongoing, no intensity
    add_episode(db_session, a, utc(2026, 8, 31, 23, 59), utc(2026, 9, 1, 1), 9, [NAUSEA])  # starts before range
    add_episode(db_session, a, utc(2026, 10, 1, 0, 0), utc(2026, 10, 1, 1), 9, [NAUSEA])  # starts after range
    return headers


# --- Access ------------------------------------------------------------------

def test_requires_authentication(client):
    assert client.get(URL).status_code == 401
    assert client.get(URL, headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_empty_user_gets_empty_statistics(client, make_user):
    body = client.get(URL, headers=make_user("analytics.empty@example.com")).json()
    assert body["summary"] == {
        "total_episodes": 0,
        "headache_days": 0,
        "average_intensity": None,
        "rated_episodes": 0,
        "average_duration_minutes": None,
        "episodes_with_duration": 0,
        "latest_episode": None,
    }
    assert body["range"]["period"] == "30d" and body["range"]["interval"] == "day"
    assert len(body["frequency"]) == 30 and all(p["count"] == 0 for p in body["frequency"])
    assert all(p["average_intensity"] is None for p in body["intensity_trend"])
    assert body["symptoms"] == []


# --- Summary -----------------------------------------------------------------

def test_summary_metrics(client, september):
    s = client.get(URL, params=SEPT, headers=september).json()["summary"]
    assert s["total_episodes"] == 4  # the two episodes outside September are excluded
    assert s["headache_days"] == 4  # Sep 5 (twice), 10, 11 (crossing midnight), 20
    assert s["average_intensity"] == 6.0  # (6 + 4 + 8) / 3; the unrated episode is skipped
    assert s["rated_episodes"] == 3
    assert s["average_duration_minutes"] == 140  # (180 + 60 + 180) / 3; ongoing excluded
    assert s["episodes_with_duration"] == 3
    assert s["latest_episode"]["started_at"].startswith("2026-09-20")


def test_partial_data_is_unavailable_not_zero(client, db_session, make_user):
    headers = make_user("analytics.partial@example.com")
    add_episode(db_session, user_id(db_session, "analytics.partial@example.com"), utc(2026, 9, 3, 9))  # ongoing, unrated
    body = client.get(URL, params=SEPT, headers=headers).json()
    assert body["summary"]["total_episodes"] == 1
    assert body["summary"]["average_intensity"] is None
    assert body["summary"]["average_duration_minutes"] is None
    assert body["symptoms"] == []


# --- Time series ---------------------------------------------------------------

def test_daily_frequency_and_intensity_are_zero_filled(client, september):
    body = client.get(URL, params=SEPT, headers=september).json()
    freq = {p["date"]: p["count"] for p in body["frequency"]}
    trend = {p["date"]: p for p in body["intensity_trend"]}
    assert body["range"]["interval"] == "day" and len(freq) == 30
    assert list(freq) == sorted(freq)  # chronological
    assert freq["2026-09-05"] == 2 and freq["2026-09-10"] == 1 and freq["2026-09-20"] == 1
    assert sum(freq.values()) == 4
    assert trend["2026-09-05"]["average_intensity"] == 5.0  # (6 + 4) / 2
    assert trend["2026-09-20"] == {"date": "2026-09-20", "average_intensity": None, "rated_episodes": 0}
    assert trend["2026-09-15"]["average_intensity"] is None  # no episode: no invented value


def test_weekly_buckets_start_on_monday(client, september):
    body = client.get(URL, params={**SEPT, "interval": "week"}, headers=september).json()
    starts = [date.fromisoformat(p["date"]) for p in body["frequency"]]
    assert all(d.weekday() == 0 for d in starts)
    assert all(b - a == timedelta(days=7) for a, b in zip(starts, starts[1:]))
    assert starts[0] <= date(2026, 9, 1) and starts[-1] <= date(2026, 9, 30)
    week_of = lambda d: (d - timedelta(days=d.weekday())).isoformat()
    counts = {p["date"]: p["count"] for p in body["frequency"]}
    assert counts[week_of(date(2026, 9, 5))] == 2
    assert sum(counts.values()) == 4


def test_monthly_buckets(client, september):
    params = {"start_date": "2026-08-01", "end_date": "2026-10-31", "interval": "month"}
    body = client.get(URL, params=params, headers=september).json()
    assert [(p["date"], p["count"]) for p in body["frequency"]] == [
        ("2026-08-01", 1),
        ("2026-09-01", 4),
        ("2026-10-01", 1),
    ]
    assert body["intensity_trend"][1]["average_intensity"] == 6.0


def test_symptom_distribution(client, september):
    symptoms = client.get(URL, params=SEPT, headers=september).json()["symptoms"]
    # Both appear on two September episodes; ties are ordered by catalog id.
    assert symptoms == [
        {"id": NAUSEA, "name": "Nausea", "count": 2},
        {"id": LIGHT, "name": "Sensitivity to light", "count": 2},
    ]


# --- Date filters --------------------------------------------------------------

def test_preset_periods(client, db_session, make_user):
    headers = make_user("analytics.presets@example.com")
    owner = user_id(db_session, "analytics.presets@example.com")
    now = datetime.now(timezone.utc)
    add_episode(db_session, owner, now - timedelta(days=1), intensity=3)
    add_episode(db_session, owner, now - timedelta(days=20), intensity=5)
    add_episode(db_session, owner, now - timedelta(days=100), intensity=7)
    totals = {
        period: client.get(URL, params={"period": period}, headers=headers).json()
        for period in ("7d", "30d", "3m", "6m")
    }
    assert [totals[p]["summary"]["total_episodes"] for p in ("7d", "30d", "3m", "6m")] == [1, 2, 2, 3]
    assert [totals[p]["range"]["days"] for p in ("7d", "30d", "3m", "6m")] == [7, 30, 90, 180]
    assert totals["6m"]["range"]["interval"] == "week"


def test_custom_range_overrides_period(client, september):
    body = client.get(URL, params={"period": "7d", **SEPT}, headers=september).json()
    assert body["range"]["period"] == "custom"
    assert body["range"]["start_date"] == "2026-09-01" and body["range"]["days"] == 30


@pytest.mark.parametrize(
    "params",
    [
        {"start_date": "2026-09-30", "end_date": "2026-09-01"},  # start after end
        {"start_date": "2026-09-01"},  # end missing
        {"end_date": "2026-09-01"},  # start missing
        {"start_date": "2024-01-01", "end_date": "2026-01-01"},  # longer than 366 days
        {"start_date": "1999-12-31", "end_date": "2000-01-05"},  # before 2000
        {"start_date": "2026-13-01", "end_date": "2026-09-01"},  # not a date
        {"period": "1y"},  # unknown preset
        {"interval": "hour"},  # unknown interval
    ],
)
def test_invalid_filters_rejected(client, make_user, params):
    response = client.get(URL, params=params, headers=make_user("analytics.invalid@example.com"))
    assert response.status_code == 422


def test_dates_use_the_users_timezone(client, db_session, make_user):
    headers = make_user("analytics.riyadh@example.com")
    owner = db_session.scalar(select(User).where(User.email == "analytics.riyadh@example.com"))
    owner.timezone = "Asia/Riyadh"  # UTC+3
    add_episode(db_session, owner.id, utc(2026, 9, 5, 22, 30), utc(2026, 9, 5, 23, 30), 5)  # 01:30 on Sep 6 locally
    add_episode(db_session, owner.id, utc(2026, 9, 30, 21, 30), intensity=5)  # 00:30 on Oct 1 locally: outside
    body = client.get(URL, params=SEPT, headers=headers).json()
    freq = {p["date"]: p["count"] for p in body["frequency"]}
    assert body["range"]["timezone"] == "Asia/Riyadh"
    assert freq["2026-09-06"] == 1 and freq["2026-09-05"] == 0
    assert body["summary"]["total_episodes"] == 1


# --- Isolation -----------------------------------------------------------------

def test_users_only_see_their_own_analytics(client, db_session, september, make_user):
    b_headers = make_user("analytics.b@example.com")
    b = user_id(db_session, "analytics.b@example.com")
    add_episode(db_session, b, utc(2026, 9, 7, 12), utc(2026, 9, 7, 14), 10, [NAUSEA])

    a_body = client.get(URL, params=SEPT, headers=september).json()
    b_body = client.get(URL, params=SEPT, headers=b_headers).json()
    assert a_body["summary"]["total_episodes"] == 4  # B's episode not included
    assert b_body["summary"]["total_episodes"] == 1 and b_body["summary"]["average_intensity"] == 10.0
    assert b_body["symptoms"] == [{"id": NAUSEA, "name": "Nausea", "count": 1}]

    # A client-supplied user id is ignored: identity only comes from the token.
    a_id = user_id(db_session, "analytics.a@example.com")
    sneaky = client.get(URL, params={**SEPT, "user_id": str(a_id)}, headers=b_headers).json()
    assert sneaky["summary"]["total_episodes"] == 1


def test_response_contains_no_personal_details(client, september):
    text = client.get(URL, params=SEPT, headers=september).text
    assert "analytics.a@example.com" not in text and "password" not in text and "user_id" not in text
