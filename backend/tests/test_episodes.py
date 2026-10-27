"""/episodes (with symptoms and medication) and /symptoms. Run from backend/ with:  python -m pytest

Synthetic example.com users only; every test is rolled back.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.models import EpisodeSymptom, MedicationDose

URL = "/episodes"
NAUSEA, LIGHT, SOUND = 1, 3, 4


def iso(*args) -> str:
    return datetime(*args, tzinfo=timezone.utc).isoformat()


def body(**overrides) -> dict:
    return {
        "started_at": iso(2026, 6, 1, 8),
        "ended_at": iso(2026, 6, 1, 11),
        "peak_intensity": 6,
        "pain_location": "left",
        "had_aura": False,
        "notes": "Synthetic note.",
        "symptom_ids": [NAUSEA, LIGHT],
        "medications": [{"medication_name": "Ibuprofen", "dose_amount": 400, "dose_unit": "mg", "relief_rating": 2}],
    } | overrides


@pytest.fixture
def alice(make_user):
    return make_user("episodes.alice@example.com")


@pytest.fixture
def bob(make_user):
    return make_user("episodes.bob@example.com")


def create(client, headers, **overrides) -> dict:
    response = client.post(URL, json=body(**overrides), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# --- Create, read, list -------------------------------------------------------------------

def test_create_with_symptoms_and_medication(client, alice):
    episode = create(client, alice)
    assert [s["id"] for s in episode["symptoms"]] == [NAUSEA, LIGHT]
    dose = episode["medications"][0]
    assert dose["medication_name"] == "Ibuprofen" and float(dose["dose_amount"]) == 400
    assert dose["taken_at"] == episode["started_at"]  # defaults to the episode start
    assert client.get(f"{URL}/{episode['id']}", headers=alice).json() == episode


def test_list_is_newest_first_and_paginated(client, alice):
    for day in (1, 3, 2):
        create(client, alice, started_at=iso(2026, 6, day, 8), ended_at=None)
    page = client.get(URL, params={"limit": 2}, headers=alice).json()
    assert page["total"] == 3 and page["limit"] == 2
    assert [e["started_at"][:10] for e in page["items"]] == ["2026-06-03", "2026-06-02"]
    rest = client.get(URL, params={"limit": 2, "offset": 2}, headers=alice).json()
    assert [e["started_at"][:10] for e in rest["items"]] == ["2026-06-01"]
    assert client.get(URL, params={"limit": 101}, headers=alice).status_code == 422


def test_ongoing_episode_and_zero_intensity(client, alice):
    episode = create(client, alice, ended_at=None, peak_intensity=0, pain_location=None, symptom_ids=[], medications=[])
    assert episode["ended_at"] is None
    assert episode["peak_intensity"] == 0
    assert episode["symptoms"] == [] and episode["medications"] == []


def test_text_is_stored_literally(client, alice):
    tricky = "'; DROP TABLE headache_episodes; -- <script>alert(1)</script> صداع"
    episode = create(client, alice, notes=tricky, medications=[{"medication_name": "x'); --"}])
    assert episode["notes"] == tricky
    assert episode["medications"][0]["medication_name"] == "x'); --"
    assert client.get(URL, headers=alice).json()["total"] == 1  # table still there


# --- Update and delete ------------------------------------------------------------------------

def test_partial_update_replaces_lists_only_when_sent(client, alice):
    episode = create(client, alice)
    url = f"{URL}/{episode['id']}"
    updated = client.patch(url, json={"peak_intensity": 3}, headers=alice).json()
    assert updated["peak_intensity"] == 3
    assert [s["id"] for s in updated["symptoms"]] == [NAUSEA, LIGHT]  # untouched
    assert len(updated["medications"]) == 1

    updated = client.patch(url, json={"symptom_ids": [SOUND], "medications": []}, headers=alice).json()
    assert [s["id"] for s in updated["symptoms"]] == [SOUND]
    assert updated["medications"] == []


def test_update_checks_end_against_stored_start(client, alice):
    episode = create(client, alice)
    response = client.patch(f"{URL}/{episode['id']}", json={"ended_at": iso(2026, 5, 31, 23)}, headers=alice)
    assert response.status_code == 422


def test_required_fields_cannot_be_cleared(client, alice):
    episode = create(client, alice)
    for field in ("started_at", "peak_intensity", "symptom_ids"):
        assert client.patch(f"{URL}/{episode['id']}", json={field: None}, headers=alice).status_code == 422


def test_delete_leaves_no_orphaned_symptoms_or_doses(client, db_session, alice):
    episode = create(client, alice)
    episode_id = uuid.UUID(episode["id"])
    assert client.delete(f"{URL}/{episode_id}", headers=alice).status_code == 204
    assert client.get(f"{URL}/{episode_id}", headers=alice).status_code == 404
    links = db_session.scalar(select(func.count()).select_from(EpisodeSymptom).where(EpisodeSymptom.episode_id == episode_id))
    doses = db_session.scalar(select(func.count()).select_from(MedicationDose).where(MedicationDose.episode_id == episode_id))
    orphans = db_session.scalar(select(func.count()).select_from(MedicationDose).where(MedicationDose.episode_id.is_(None)))
    assert (links, doses, orphans) == (0, 0, 0)


# --- Validation ---------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "overrides",
    [
        {"symptom_ids": [999]},  # unknown symptom
        {"symptom_ids": [NAUSEA, NAUSEA]},  # repeated
        {"ended_at": iso(2026, 6, 1, 7)},  # ends before it starts
        {"started_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(), "ended_at": None},  # future
        {"started_at": "2026-06-01T08:00:00"},  # no time zone
        {"peak_intensity": 11},
        {"peak_intensity": -1},
        {"pain_location": "everywhere"},
        {"notes": "x" * 2001},
        {"medications": [{"medication_name": "   "}]},
        {"medications": [{"medication_name": "A", "relief_rating": 4}]},
        {"medications": [{"medication_name": "A", "dose_amount": 0}]},
        {"user_id": str(uuid.uuid4())},  # ownership can't be set by the client
    ],
)
def test_invalid_episodes_are_rejected(client, alice, overrides):
    assert client.post(URL, json=body(**overrides), headers=alice).status_code == 422


# --- Isolation ------------------------------------------------------------------------------------

def test_other_users_episodes_and_medication_are_invisible_and_untouchable(client, alice, bob):
    episode = create(client, alice)
    url = f"{URL}/{episode['id']}"
    assert client.get(url, headers=bob).status_code == 404
    assert client.patch(url, json={"notes": "changed by bob", "medications": []}, headers=bob).status_code == 404
    assert client.delete(url, headers=bob).status_code == 404
    assert client.get(URL, headers=bob).json()["total"] == 0
    # A user_id in the query is ignored, not obeyed.
    assert client.get(URL, params={"user_id": "anything"}, headers=bob).json()["total"] == 0
    # Alice's episode, notes and medication are unchanged.
    still = client.get(url, headers=alice).json()
    assert still["notes"] == "Synthetic note." and len(still["medications"]) == 1


def test_unknown_or_malformed_ids(client, alice):
    assert client.get(f"{URL}/{uuid.uuid4()}", headers=alice).status_code == 404
    assert client.get(f"{URL}/not-a-uuid", headers=alice).status_code == 422


# --- Symptoms ---------------------------------------------------------------------------------------

def test_symptom_catalog_requires_login(client, alice):
    assert client.get("/symptoms").status_code == 401
    catalog = client.get("/symptoms", headers=alice).json()
    assert len(catalog) == 13
    assert catalog[0] == {"id": 1, "name": "Nausea", "category": catalog[0]["category"]}
