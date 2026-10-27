"""/sleep-logs and /daily-factors. Run from backend/ with:  python -m pytest

Synthetic example.com users only, inside a rolled-back transaction on namat_test.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

SLEEP = "/sleep-logs"
FACTORS = "/daily-factors"


def night(day: str, bed_hour: int = 23, hours: float = 7.5, **extra) -> dict:
    bed = datetime.fromisoformat(f"{day}T00:00:00+00:00") + timedelta(hours=bed_hour)
    return {
        "sleep_date": day,
        "bedtime": bed.isoformat(),
        "wake_time": (bed + timedelta(hours=hours)).isoformat(),
        **extra,
    }


@pytest.fixture
def alice(make_user):
    return make_user("daily.alice@example.com")


@pytest.fixture
def bob(make_user):
    return make_user("daily.bob@example.com")


# --- Access ------------------------------------------------------------------------

@pytest.mark.parametrize("path", [SLEEP, FACTORS])
def test_requires_a_token(client, path):
    assert client.get(path).status_code == 401
    assert client.post(path, json={}).status_code == 401


@pytest.mark.parametrize(
    "path, body",
    [(SLEEP, night("2026-06-01")), (FACTORS, {"log_date": "2026-06-01", "stress_level": 4})],
)
def test_users_never_see_or_change_each_others_records(client, alice, bob, path, body):
    created = client.post(path, json=body, headers=alice).json()
    url = f"{path}/{created['id']}"
    assert client.get(url, headers=bob).status_code == 404
    assert client.patch(url, json={"notes": "x"}, headers=bob).status_code == 404
    assert client.delete(url, headers=bob).status_code == 404
    assert client.get(path, headers=bob).json()["total"] == 0
    assert client.get(url, headers=alice).status_code == 200


@pytest.mark.parametrize(
    "path, body",
    [(SLEEP, night("2026-06-01")), (FACTORS, {"log_date": "2026-06-01", "stress_level": 4})],
)
def test_user_id_in_the_body_is_rejected(client, alice, path, body):
    response = client.post(path, json=body | {"user_id": "00000000-0000-0000-0000-000000000000"}, headers=alice)
    assert response.status_code == 422


# --- Sleep ----------------------------------------------------------------------------

def test_sleep_create_read_update_delete(client, alice):
    created = client.post(SLEEP, json=night("2026-06-01", quality=4, awakenings=0, notes="  slept well  "), headers=alice)
    assert created.status_code == 201
    log = created.json()
    assert log["duration_minutes"] == 450
    assert log["quality"] == 4 and log["awakenings"] == 0  # 0 is kept, not dropped
    assert log["notes"] == "slept well"

    updated = client.patch(f"{SLEEP}/{log['id']}", json={"quality": None, "awakenings": 2}, headers=alice).json()
    assert updated["quality"] is None and updated["awakenings"] == 2

    assert client.delete(f"{SLEEP}/{log['id']}", headers=alice).status_code == 204
    assert client.get(f"{SLEEP}/{log['id']}", headers=alice).status_code == 404


def test_bedtime_after_midnight_belongs_to_the_previous_night(client, alice):
    # Night of 1 June, asleep at 01:00 on 2 June.
    response = client.post(SLEEP, json=night("2026-06-01", bed_hour=25, hours=6), headers=alice)
    assert response.status_code == 201


def test_one_sleep_log_per_night(client, alice):
    assert client.post(SLEEP, json=night("2026-06-01"), headers=alice).status_code == 201
    assert client.post(SLEEP, json=night("2026-06-01", hours=5), headers=alice).status_code == 409
    other = client.post(SLEEP, json=night("2026-06-02"), headers=alice).json()
    assert client.patch(f"{SLEEP}/{other['id']}", json={"sleep_date": "2026-06-01"}, headers=alice).status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        night("2026-06-01", hours=-1),  # wakes before going to bed
        night("2026-06-01", hours=25),  # longer than 24 hours
        night("2026-06-01") | {"sleep_date": "2026-05-20"},  # bedtime far from the night's date
        night("2026-06-01", quality=6),
        night("2026-06-01", awakenings=-1),
        night((date.today() + timedelta(days=5)).isoformat()),  # in the future
    ],
)
def test_invalid_sleep_is_rejected(client, alice, body):
    assert client.post(SLEEP, json=body, headers=alice).status_code == 422


def test_sleep_update_checks_times_against_stored_values(client, alice):
    log = client.post(SLEEP, json=night("2026-06-01"), headers=alice).json()
    early = (datetime.fromisoformat(log["bedtime"]) - timedelta(hours=1)).isoformat()
    assert client.patch(f"{SLEEP}/{log['id']}", json={"wake_time": early}, headers=alice).status_code == 422


def test_sleep_list_is_newest_first_and_filterable(client, alice):
    for day in ("2026-06-01", "2026-06-03", "2026-06-02"):
        client.post(SLEEP, json=night(day), headers=alice)
    page = client.get(SLEEP, headers=alice).json()
    assert [i["sleep_date"] for i in page["items"]] == ["2026-06-03", "2026-06-02", "2026-06-01"]
    filtered = client.get(SLEEP, params={"start_date": "2026-06-02", "end_date": "2026-06-02"}, headers=alice).json()
    assert filtered["total"] == 1


# --- Daily factors ---------------------------------------------------------------------------

def test_factors_keep_zero_and_no_apart_from_not_recorded(client, alice):
    body = {"log_date": "2026-06-01", "caffeine_mg": 0, "skipped_meal": False, "alcohol_units": 1.5}
    record = client.post(FACTORS, json=body, headers=alice).json()
    assert record["caffeine_mg"] == 0  # recorded zero
    assert record["skipped_meal"] is False  # recorded "no"
    assert record["stress_level"] is None and record["menstruating"] is None  # not recorded
    assert float(record["alcohol_units"]) == 1.5


def test_factors_need_at_least_one_value(client, alice):
    assert client.post(FACTORS, json={"log_date": "2026-06-01"}, headers=alice).status_code == 422
    record = client.post(FACTORS, json={"log_date": "2026-06-01", "stress_level": 3}, headers=alice).json()
    # Clearing the only value would leave an empty record.
    assert client.patch(f"{FACTORS}/{record['id']}", json={"stress_level": None}, headers=alice).status_code == 422
    # Replacing it with another value is fine; null clears a factor back to "not recorded".
    updated = client.patch(f"{FACTORS}/{record['id']}", json={"stress_level": None, "water_ml": 1500}, headers=alice).json()
    assert updated["stress_level"] is None and updated["water_ml"] == 1500


@pytest.mark.parametrize(
    "values",
    [{"stress_level": 11}, {"caffeine_mg": -1}, {"exercise_minutes": 1441}, {"alcohol_units": 1.25}, {"water_ml": "lots"}],
)
def test_invalid_factors_are_rejected(client, alice, values):
    assert client.post(FACTORS, json={"log_date": "2026-06-01"} | values, headers=alice).status_code == 422


def test_one_factor_record_per_day(client, alice):
    assert client.post(FACTORS, json={"log_date": "2026-06-01", "stress_level": 2}, headers=alice).status_code == 201
    assert client.post(FACTORS, json={"log_date": "2026-06-01", "water_ml": 900}, headers=alice).status_code == 409


def test_factor_delete(client, alice):
    record = client.post(FACTORS, json={"log_date": "2026-06-01", "menstruating": True}, headers=alice).json()
    assert client.delete(f"{FACTORS}/{record['id']}", headers=alice).status_code == 204
    assert client.get(FACTORS, headers=alice).json()["total"] == 0


# --- The logged records feed the existing insights ----------------------------------------------

def test_logged_sleep_and_factors_reach_the_insights(client, alice):
    for i in range(8):
        day = (date(2026, 6, 1) + timedelta(days=i)).isoformat()
        assert client.post(SLEEP, json=night(day, hours=6 + i % 3), headers=alice).status_code == 201
        assert client.post(FACTORS, json={"log_date": day, "stress_level": i}, headers=alice).status_code == 201
    summary = client.get("/insights", params={"start_date": "2026-06-01", "end_date": "2026-06-30"}, headers=alice).json()["summary"]
    assert summary["sleep_nights"] == 8  # nights 1–8 June, each matched to the following day
    assert summary["factor_days"] == 8


def test_timestamps_are_utc_aware(client, alice):
    log = client.post(SLEEP, json=night("2026-06-01"), headers=alice).json()
    assert datetime.fromisoformat(log["bedtime"]).tzinfo is not None
    assert datetime.fromisoformat(log["bedtime"]).astimezone(timezone.utc).hour == 23
