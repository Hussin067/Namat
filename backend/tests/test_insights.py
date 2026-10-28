"""GET /insights and the analysis engine. Run from backend/ with:  python -m pytest

All data is synthetic, written directly to namat_test inside a rolled-back
transaction. Dates are fixed (June 2026) so every expected number can be
checked by hand.
"""

import re
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import DailyFactor, EpisodeSymptom, HeadacheEpisode, MedicationDose, SleepLog, User
from app.services.analytics import resolve_range
from app.services.insights import THRESHOLDS, analyze, generate_insights

URL = "/insights"
JUNE = {"start_date": "2026-06-01", "end_date": "2026-06-30"}
NAUSEA, LIGHT, SOUND = 1, 3, 4

# Wording the insights must never use: causal, diagnostic or treatment claims.
FORBIDDEN = re.compile(
    r"\b(cause[sd]?|causing|diagnos\w*|chronic migraine|effective|ineffective|works?|should|stop taking|dosage|treat\w*|cure\w*)\b",
    re.IGNORECASE,
)


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


# --- Builders ----------------------------------------------------------------------

@pytest.fixture
def user(client, db_session, make_user):
    """A synthetic user (UTC); returns (User, auth headers)."""
    headers = make_user("insights.a@example.com")
    return db_session.scalar(select(User).where(User.email == "insights.a@example.com")), headers


def episode(db, owner, start, end=None, intensity=None, symptoms=()):
    e = HeadacheEpisode(user_id=owner.id, started_at=start, ended_at=end, peak_intensity=intensity)
    e.symptom_links = [EpisodeSymptom(symptom_id=s) for s in symptoms]
    db.add(e)
    db.flush()
    return e


def night(db, owner, sleep_date: date, hours: float):
    bed = datetime.combine(sleep_date, datetime.min.time(), timezone.utc) + timedelta(hours=23)
    db.add(SleepLog(user_id=owner.id, sleep_date=sleep_date, bedtime=bed, wake_time=bed + timedelta(hours=hours)))
    db.flush()


def factors(db, owner, day: date, **values):
    db.add(DailyFactor(user_id=owner.id, log_date=day, **values))
    db.flush()


def run(db, owner, start="2026-06-01", end="2026-06-30"):
    """Analysis + insights for a custom range, straight from the service."""
    rng = resolve_range(owner, "30d", date.fromisoformat(start), date.fromisoformat(end), None)
    result = analyze(db, owner, rng)
    return result, generate_insights(result)


def ids(report) -> list[str]:
    return [i["id"] for i in report["insights"]]


def gap_codes(report) -> set[str]:
    return {g["code"] for g in report["data_gaps"]}


# --- 1–3. Access -------------------------------------------------------------------

def test_authenticated_request_succeeds_and_is_not_cached(client, user):
    response = client.get(URL, params=JUNE, headers=user[1])
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, private"
    assert response.json()["period"]["start"] == "2026-06-01"


def test_unauthenticated_request_is_rejected(client):
    assert client.get(URL).status_code == 401
    assert client.get(URL, headers={"Authorization": "Bearer nonsense"}).status_code == 401


def test_users_cannot_see_each_others_insights(client, db_session, user, make_user):
    owner, a_headers = user
    for day in (3, 10, 17, 24):
        episode(db_session, owner, utc(2026, 6, day, 9), utc(2026, 6, day, 11), 6, [NAUSEA])
    b_headers = make_user("insights.b@example.com")

    a = client.get(URL, params=JUNE, headers=a_headers).json()
    b = client.get(URL, params=JUNE, headers=b_headers).json()
    sneaky = client.get(URL, params={**JUNE, "user_id": str(owner.id)}, headers=b_headers).json()
    assert a["summary"]["total_episodes"] == 4
    assert b["summary"]["total_episodes"] == 0 and b["insights"] == []
    assert sneaky["summary"]["total_episodes"] == 0  # a client-sent user id is ignored


# --- 4–5. Insufficient data -----------------------------------------------------------

def test_empty_user_gets_insufficient_response(client, user):
    body = client.get(URL, params=JUNE, headers=user[1]).json()
    assert body["data_status"] == "insufficient"
    assert body["insights"] == []
    assert {"code": "episodes", "needed": THRESHOLDS.min_episodes, "have": 0} in body["data_gaps"]
    assert {"sleep", "daily_factors"} <= {g["code"] for g in body["data_gaps"]}
    assert body["summary"]["average_intensity"] is None and body["summary"]["highest_intensity"] is None


def test_minimum_episode_threshold(db_session, user):
    owner = user[0]
    episode(db_session, owner, utc(2026, 6, 3, 9), intensity=5)
    episode(db_session, owner, utc(2026, 6, 9, 9), intensity=5)
    _, report = run(db_session, owner)
    assert report["data_status"] == "insufficient" and report["insights"] == []

    episode(db_session, owner, utc(2026, 6, 15, 9), intensity=5)
    _, report = run(db_session, owner)
    assert report["data_status"] != "insufficient"
    assert "episodes" not in gap_codes(report)


# --- 6–7. Sleep and daily-factor thresholds -----------------------------------------------

def test_minimum_sleep_threshold(db_session, user):
    owner = user[0]
    for i in range(6):
        night(db_session, owner, date(2026, 6, 1) + timedelta(days=i), 7)
    result, report = run(db_session, owner)
    assert result["sleep"]["usable_nights"] == 6
    assert {"code": "sleep", "needed": 7, "have": 6} in report["data_gaps"]

    night(db_session, owner, date(2026, 6, 7), 7)
    _, report = run(db_session, owner)
    assert "sleep" not in gap_codes(report)


def test_minimum_daily_factor_threshold(db_session, user):
    owner = user[0]
    for i in range(6):
        factors(db_session, owner, date(2026, 6, 1) + timedelta(days=i), stress_level=4)
    _, report = run(db_session, owner)
    assert {"code": "daily_factors", "needed": 7, "have": 6} in report["data_gaps"]

    factors(db_session, owner, date(2026, 6, 7), stress_level=4)
    _, report = run(db_session, owner)
    assert "daily_factors" not in gap_codes(report)


# --- 8–9. Missing values and zeros ------------------------------------------------------------

def test_missing_values_are_excluded(db_session, user):
    owner = user[0]
    for i in range(10):
        # Only stress is recorded on even days; caffeine is never recorded.
        factors(db_session, owner, date(2026, 6, 1) + timedelta(days=i), stress_level=5 if i % 2 == 0 else None)
    episode(db_session, owner, utc(2026, 6, 2, 9))  # no intensity
    episode(db_session, owner, utc(2026, 6, 4, 9), intensity=4)
    result, _ = run(db_session, owner)
    assert result["factors"]["by_factor"]["stress_level"]["recorded_days"] == 5
    assert result["factors"]["by_factor"]["caffeine_mg"]["recorded_days"] == 0
    assert result["intensity"]["rated_episodes"] == 1 and result["intensity"]["average"] == 4.0


def test_zero_is_a_value_not_missing(db_session, user):
    owner = user[0]
    for i in range(7):
        factors(db_session, owner, date(2026, 6, 1) + timedelta(days=i), caffeine_mg=0, water_ml=0)
    episode(db_session, owner, utc(2026, 6, 2, 9), intensity=0)
    episode(db_session, owner, utc(2026, 6, 3, 9), intensity=6)
    result, report = run(db_session, owner)
    assert result["factors"]["by_factor"]["caffeine_mg"]["recorded_days"] == 7
    assert result["factors"]["by_factor"]["water_ml"]["recorded_days"] == 7
    assert "alcohol_units" not in result["factors"]["by_factor"]  # no longer analysed
    assert "daily_factors" not in gap_codes(report)
    assert result["intensity"]["rated_episodes"] == 2 and result["intensity"]["average"] == 3.0  # (0 + 6) / 2
    assert result["intensity"]["distribution"] == {"none": 1, "moderate": 1}


# --- 10–11. Calendar days and time zones -------------------------------------------------

def test_headache_days_count_distinct_local_dates(client, db_session, user):
    owner, headers = user
    episode(db_session, owner, utc(2026, 6, 5, 8), utc(2026, 6, 5, 9), 4)
    episode(db_session, owner, utc(2026, 6, 5, 18), utc(2026, 6, 5, 19), 5)  # same day
    episode(db_session, owner, utc(2026, 6, 10, 23), utc(2026, 6, 11, 2), 6)  # crosses midnight
    body = client.get(URL, params=JUNE, headers=headers).json()
    assert body["summary"]["total_episodes"] == 3
    assert body["summary"]["headache_days"] == 3  # Jun 5, 10, 11
    # The same rule as the dashboard analytics.
    dashboard = client.get("/analytics/dashboard", params=JUNE, headers=headers).json()
    assert dashboard["summary"]["headache_days"] == body["summary"]["headache_days"]


def test_dates_and_times_use_the_users_timezone(db_session, user):
    owner = user[0]
    owner.timezone = "Asia/Riyadh"  # UTC+3
    episode(db_session, owner, utc(2026, 6, 4, 22, 30))  # 01:30 on Jun 5 locally: night
    episode(db_session, owner, utc(2026, 6, 30, 21, 30))  # 00:30 on Jul 1 locally: outside June
    result, report = run(db_session, owner)
    assert report["period"]["timezone"] == "Asia/Riyadh"
    assert result["frequency"]["total_episodes"] == 1
    assert result["time_of_day"]["night"] == 1


def test_time_of_day_respects_daylight_saving(db_session, user):
    owner = user[0]
    owner.timezone = "Europe/London"  # clocks go forward at 01:00 UTC on 29 Mar 2026
    episode(db_session, owner, utc(2026, 3, 29, 0, 30))  # 00:30 GMT: night
    episode(db_session, owner, utc(2026, 3, 29, 4, 30))  # 05:30 BST: morning (would be 04:30 without DST)
    result, _ = run(db_session, owner, "2026-03-01", "2026-03-31")
    assert result["time_of_day"] == {"morning": 1, "afternoon": 0, "evening": 0, "night": 1}


# --- 12–13. Sleep and daily-factor associations ------------------------------------------------

def test_sleep_is_matched_to_the_following_day(db_session, user):
    owner = user[0]
    # Nights Jun 1–10. Short nights (5 h) on odd dates, 8 h on even dates.
    for i in range(10):
        d = date(2026, 6, 1) + timedelta(days=i)
        night(db_session, owner, d, 5 if d.day % 2 else 8)
    # Headaches on the day AFTER each short night (Jun 2, 4, 6, 8, 10) ...
    for day in (2, 4, 6, 8, 10):
        episode(db_session, owner, utc(2026, 6, day, 9), utc(2026, 6, day, 11), 6)
    # ... and one on the same date as a long night (Jun 12 night -> counts for Jun 13, not Jun 12).
    night(db_session, owner, date(2026, 6, 12), 8)
    episode(db_session, owner, utc(2026, 6, 12, 9), utc(2026, 6, 12, 10), 3)

    result, report = run(db_session, owner)
    c = result["sleep"]["comparison"]
    assert result["sleep"]["usable_nights"] == 11
    assert c["median_hours"] == 8.0
    assert (c["a_days"], c["a_headache_days"]) == (5, 5)  # every short night followed by a headache day
    assert (c["b_days"], c["b_headache_days"]) == (6, 0)  # Jun 12's headache is not after the Jun 12 night
    sleep_insight = next(i for i in report["insights"] if i["category"] == "sleep")
    assert sleep_insight["id"] == "sleep_rate_higher"
    assert sleep_insight["evidence"]["shorter_headache_rate"] == 1.0
    assert sleep_insight["evidence"]["other_headache_rate"] == 0.0
    assert sleep_insight["sample_size"] == 11 and sleep_insight["evidence_level"] == "limited"


def test_daily_factor_comparisons_use_the_right_days(db_session, user):
    owner = user[0]
    for i in range(14):
        d = date(2026, 6, 1) + timedelta(days=i)
        high = i % 2 == 0
        # Stress 8 on even-index days, 2 otherwise; skipped meal explicitly recorded both ways.
        factors(db_session, owner, d, stress_level=8 if high else 2, skipped_meal=high)
        if high:
            episode(db_session, owner, datetime.combine(d, datetime.min.time(), timezone.utc) + timedelta(hours=10), intensity=7)
    # A day with no factor record at all must not count as "no stress".
    episode(db_session, owner, utc(2026, 6, 25, 10), intensity=2)

    result, report = run(db_session, owner)
    stress = result["factors"]["by_factor"]["stress_level"]
    assert stress["recorded_days"] == 14 and stress["median"] == 5.0
    assert (stress["comparison"]["a_days"], stress["comparison"]["a_headache_days"]) == (7, 7)
    assert (stress["comparison"]["b_days"], stress["comparison"]["b_headache_days"]) == (7, 0)
    meal = result["factors"]["by_factor"]["skipped_meal"]["comparison"]
    assert (meal["a_days"], meal["b_days"]) == (7, 7)  # explicit True vs explicit False only
    found = ids(report)
    assert "factor_stress_level_rate_higher" in found and "factor_skipped_meal_rate_higher" in found
    card = next(i for i in report["insights"] if i["id"] == "factor_stress_level_rate_higher")
    assert card["evidence_level"] == "observed" and card["sample_size"] == 14


# --- 14–16. Symptoms, time of day, medication --------------------------------------------------

def test_symptoms_are_not_double_counted(db_session, user):
    owner = user[0]
    for day in (2, 6, 10, 14):
        episode(db_session, owner, utc(2026, 6, day, 9), intensity=5, symptoms=[NAUSEA, LIGHT])
    episode(db_session, owner, utc(2026, 6, 20, 9), intensity=5, symptoms=[SOUND])
    result, report = run(db_session, owner)
    counts = {s["name"]: s["count"] for s in result["symptoms"]["counts"]}
    assert counts == {"Nausea": 4, "Sensitivity to light": 4, "Sensitivity to sound": 1}
    assert result["symptoms"]["pairs"][0] == {"ids": [NAUSEA, LIGHT], "names": ["Nausea", "Sensitivity to light"], "count": 4}
    # Nausea only ever appears with light sensitivity: one card, not two saying the same thing.
    assert [i["id"] for i in report["insights"] if i["category"] == "symptoms"] == ["symptom_pair"]

    episode(db_session, owner, utc(2026, 6, 25, 9), intensity=5, symptoms=[NAUSEA])  # now Nausea also appears alone
    _, report = run(db_session, owner)
    common = next(i for i in report["insights"] if i["id"] == "symptom_common")
    assert (common["evidence"]["count"], common["evidence"]["total"]) == (5, 6)
    assert any(i["id"] == "symptom_pair" for i in report["insights"])


@pytest.mark.parametrize(
    ("hour", "minute", "part"),
    [(4, 59, "night"), (5, 0, "morning"), (11, 59, "morning"), (12, 0, "afternoon"), (17, 0, "evening"), (21, 0, "night")],
)
def test_time_of_day_boundaries(db_session, user, hour, minute, part):
    owner = user[0]
    episode(db_session, owner, utc(2026, 6, 10, hour, minute))
    result, _ = run(db_session, owner)
    assert result["time_of_day"][part] == 1


def test_time_of_day_insight_needs_a_clear_majority(db_session, user):
    owner = user[0]
    for day in (2, 5, 8, 11):
        episode(db_session, owner, utc(2026, 6, day, 19), intensity=5)  # evening
    episode(db_session, owner, utc(2026, 6, 14, 9), intensity=5)  # morning
    _, report = run(db_session, owner)
    card = next(i for i in report["insights"] if i["category"] == "timing")
    assert card["id"] == "time_of_day_evening" and card["evidence"]["count"] == 4


def test_medication_summary_is_descriptive_only(db_session, user):
    owner = user[0]
    eps = [episode(db_session, owner, utc(2026, 6, d, 9), utc(2026, 6, d, 12), 6) for d in (3, 9, 15, 21)]
    for e in eps[:3]:
        db_session.add(MedicationDose(user_id=owner.id, episode_id=e.id, medication_name="Sample reliever", taken_at=e.started_at))
    db_session.add(MedicationDose(user_id=owner.id, medication_name="Sample preventive", taken_at=utc(2026, 6, 1, 8)))
    db_session.flush()
    _, report = run(db_session, owner)
    med = next(i for i in report["insights"] if i["category"] == "medication")
    assert med["evidence"]["doses"] == 4
    assert med["evidence"]["top_medication"] == "Sample reliever" and med["evidence"]["top_medication_doses"] == 3
    assert med["evidence"]["episodes_with_medication"] == 3
    assert not set(med["evidence"]) & {"relief", "effective", "effectiveness", "improvement"}


def test_no_insight_uses_causal_diagnostic_or_treatment_language(db_session, user):
    """Build data that triggers every kind of insight, then scan all generated text."""
    owner = user[0]
    for i in range(30):
        d = date(2026, 5, 2) + timedelta(days=i)  # previous period: tracked, few episodes
        if i in (5, 12, 20):  # 3 rated episodes: enough for an intensity comparison
            episode(db_session, owner, datetime.combine(d, datetime.min.time(), timezone.utc) + timedelta(hours=10), intensity=3)
    for i in range(14):
        d = date(2026, 6, 1) + timedelta(days=i)
        night(db_session, owner, d - timedelta(days=1), 5 if i % 2 == 0 else 8)
        factors(db_session, owner, d, stress_level=8 if i % 2 == 0 else 1, skipped_meal=i % 2 == 0)
        if i % 2 == 0:
            e = episode(db_session, owner, datetime.combine(d, datetime.min.time(), timezone.utc) + timedelta(hours=19),
                        datetime.combine(d, datetime.min.time(), timezone.utc) + timedelta(hours=22), 8, [NAUSEA, LIGHT])
            db_session.add(MedicationDose(user_id=owner.id, episode_id=e.id, medication_name="Sample reliever", taken_at=e.started_at))
    db_session.flush()
    _, report = run(db_session, owner)
    categories = {i["category"] for i in report["insights"]}
    assert categories >= {"frequency", "intensity", "timing", "symptoms", "sleep", "factors", "medication"}
    for insight in report["insights"]:
        text = f"{insight['title']} {insight['description']}"
        assert not FORBIDDEN.search(text), text
    assert report["data_status"] == "sufficient"


# --- 17–19. Date filters and previous-period comparison -------------------------------------

def test_preset_periods(client, user):
    for period, days in (("7d", 7), ("30d", 30), ("3m", 90), ("6m", 180), ("12m", 365)):
        body = client.get(URL, params={"period": period}, headers=user[1]).json()
        assert body["period"]["period"] == period and body["period"]["days"] == days


@pytest.mark.parametrize(
    "params",
    [
        {"start_date": "2026-06-30", "end_date": "2026-06-01"},
        {"start_date": "2026-06-01"},
        {"start_date": "2024-01-01", "end_date": "2026-01-01"},
        {"start_date": "1999-12-31", "end_date": "2000-01-02"},
        {"period": "90d"},
        {"start_date": "not-a-date", "end_date": "2026-06-01"},
    ],
)
def test_invalid_ranges_are_rejected(client, user, params):
    assert client.get(URL, params=params, headers=user[1]).status_code == 422


def test_previous_period_uses_the_equivalent_dates(db_session, user):
    owner = user[0]
    # Previous period for June (30 days) is May 2 – May 31.
    episode(db_session, owner, utc(2026, 5, 1, 12), intensity=5)  # tracking began before May 2; outside both periods
    episode(db_session, owner, utc(2026, 5, 2, 0, 30), intensity=5)  # first day of the previous period
    episode(db_session, owner, utc(2026, 5, 31, 23, 30), intensity=5)  # last moment of the previous period
    for day in (3, 6, 9, 12, 15, 18):
        episode(db_session, owner, utc(2026, 6, day, 9), intensity=5)
    result, report = run(db_session, owner)
    assert result["previous_range"] == (date(2026, 5, 2), date(2026, 5, 31))
    assert result["frequency"]["previous_total_episodes"] == 2
    card = next(i for i in report["insights"] if i["category"] == "frequency")
    assert card["id"] == "frequency_increase"
    assert (card["evidence"]["current"], card["evidence"]["previous"]) == (6, 2)
    assert card["comparison"]["previous_start"] == date(2026, 5, 2)


def test_no_comparison_when_tracking_started_recently(db_session, user):
    owner = user[0]
    for day in (10, 14, 18, 22):
        episode(db_session, owner, utc(2026, 6, day, 9), intensity=5)
    _, report = run(db_session, owner)
    assert "previous_period" in gap_codes(report)
    assert not any(i["category"] == "frequency" for i in report["insights"])


# --- 20. Values come from the records, never from examples ------------------------------------

def test_values_come_from_the_records(client, db_session, user):
    owner, headers = user
    episode(db_session, owner, utc(2026, 6, 8, 9), utc(2026, 6, 8, 10), 2)
    episode(db_session, owner, utc(2026, 6, 16, 9), utc(2026, 6, 16, 10), 9)
    episode(db_session, owner, utc(2026, 6, 24, 9), utc(2026, 6, 24, 10), 4)
    body = client.get(URL, params=JUNE, headers=headers).json()
    assert body["summary"]["total_episodes"] == 3
    assert body["summary"]["average_intensity"] == 5.0  # (2 + 9 + 4) / 3
    assert body["summary"]["highest_intensity"] == 9
    assert body["summary"]["episodes_per_week"] == 0.7  # 3 / (30 / 7)
    assert body["summary"]["intensity_distribution"] == {"mild": 1, "very_severe": 1, "moderate": 1}
    # The illustrative numbers from the specification must not appear.
    assert body["summary"]["average_intensity"] != 5.8 and body["summary"]["total_episodes"] != 12


# --- Chance filter ------------------------------------------------------------------------

def test_fisher_exact_matches_known_values():
    from app.services.insights import fisher_exact_p

    assert round(fisher_exact_p(3, 4, 1, 4), 4) == 0.4857  # classic 2x2 example [[3, 1], [1, 3]]
    assert round(fisher_exact_p(7, 7, 0, 7), 4) == 0.0006
    assert fisher_exact_p(2, 4, 2, 4) == pytest.approx(1.0)  # identical groups: no evidence of a difference


def test_differences_that_could_be_chance_are_not_reported(db_session, user):
    owner = user[0]
    # Stress high on 7 days (3 headache days) vs low on 7 days (1 headache day):
    # a 29-point gap, but with 14 days that is well within chance (p ~ 0.56).
    for i in range(14):
        d = date(2026, 6, 1) + timedelta(days=i)
        high = i < 7
        factors(db_session, owner, d, stress_level=8 if high else 2)
        if (high and i < 3) or (not high and i == 7):
            episode(db_session, owner, datetime.combine(d, datetime.min.time(), timezone.utc) + timedelta(hours=10), intensity=5)
    result, report = run(db_session, owner)
    c = result["factors"]["by_factor"]["stress_level"]["comparison"]
    assert (c["a_headache_days"], c["b_headache_days"]) == (3, 1)
    assert c["rate_p_value"] > THRESHOLDS.max_p_value_shown
    assert not any(i["category"] == "factors" for i in report["insights"])
