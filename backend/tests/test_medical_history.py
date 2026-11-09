"""/medical-history: conditions, allergies, procedures and additional notes,
plus the medical report's "Medical history (reported by you)" section.
Run from backend/ with:  python -m pytest

Synthetic example.com accounts only, written to namat_test inside a
rolled-back transaction.
"""

import logging
import re
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, func, select

from app.models import MedicalAllergy, MedicalCondition, MedicalNotes, MedicalProcedure, User
from tests.conftest import TEST_PASSWORD
from tests.test_reports import FORBIDDEN_AR, FORBIDDEN_EN, PDF, URL, pdf_text

BASE = "/medical-history"
CONDITION = {"condition_name": "Migraine with aura", "category": "headache_disorder", "status": "active", "confirmation": "clinician_confirmed"}
ALLERGY = {"name": "Penicillin", "type": "medication", "reaction": "Rash", "severity": "moderate"}
PROCEDURE = {"name": "Appendectomy", "procedure_date": "2015-04-02"}
BODIES = {"conditions": CONDITION, "allergies": ALLERGY, "procedures": PROCEDURE}
JUNE = {"start_date": "2026-06-01", "end_date": "2026-06-30"}
ORIGIN_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture
def alice(make_user):
    return make_user("mh.alice@example.com")


@pytest.fixture
def bob(make_user):
    return make_user("mh.bob@example.com")


def post(client, headers, kind, body):
    response = client.post(f"{BASE}/{kind}", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# --- Access -----------------------------------------------------------------------------------

@pytest.mark.parametrize("method, path", [
    ("GET", BASE), ("GET", f"{BASE}/conditions"), ("POST", f"{BASE}/allergies"),
    ("PATCH", f"{BASE}/procedures/{uuid.uuid4()}"), ("GET", f"{BASE}/notes"), ("PUT", f"{BASE}/notes"),
])
def test_requires_authentication(client, method, path):
    assert client.request(method, path, json={}).status_code == 401


@pytest.mark.parametrize("kind", ["conditions", "allergies", "procedures"])
def test_users_never_see_or_change_each_others_items(client, alice, bob, kind):
    item = post(client, alice, kind, BODIES[kind])
    item_url = f"{BASE}/{kind}/{item['id']}"
    assert client.get(item_url, headers=bob).status_code == 404
    assert client.patch(item_url, json={"notes": "x"}, headers=bob).status_code == 404
    assert client.delete(item_url, headers=bob).status_code == 404
    assert client.get(f"{BASE}/{kind}", headers=bob).json() == []
    assert client.get(BASE, headers=bob).json()[kind] == []
    # Alice's item is untouched.
    assert client.get(item_url, headers=alice).json()["notes"] is None


def test_notes_are_private_to_each_user(client, alice, bob):
    assert client.put(f"{BASE}/notes", json={"notes": "Alice's private note"}, headers=alice).status_code == 200
    assert client.get(f"{BASE}/notes", headers=bob).json() == {"notes": None, "updated_at": None}


@pytest.mark.parametrize("kind", ["conditions", "allergies", "procedures"])
def test_user_id_in_the_body_is_rejected(client, alice, kind):
    body = BODIES[kind] | {"user_id": str(uuid.uuid4())}
    assert client.post(f"{BASE}/{kind}", json=body, headers=alice).status_code == 422


def test_cookie_session_needs_the_csrf_header(client):
    assert client.post("/auth/register", json={"email": "mh.cookie@example.com", "password": TEST_PASSWORD}).status_code == 201
    assert client.post("/auth/login", data={"username": "mh.cookie@example.com", "password": TEST_PASSWORD}).status_code == 200
    assert client.put(f"{BASE}/notes", json={"notes": "x"}).status_code == 403
    from app.core.config import get_settings

    csrf = client.cookies.get(get_settings().csrf_cookie_name)
    assert client.put(f"{BASE}/notes", json={"notes": "x"}, headers={"X-CSRF-Token": csrf}).status_code == 200


def test_cors_allows_put_from_the_app(client):
    from app.core.config import get_settings

    origin = get_settings().cors_origins[0]
    response = client.options(f"{BASE}/notes", headers={"Origin": origin, "Access-Control-Request-Method": "PUT"})
    assert response.status_code == 200
    assert "PUT" in response.headers["access-control-allow-methods"]


# --- CRUD -------------------------------------------------------------------------------------

def test_condition_create_read_update_delete(client, alice):
    item = post(client, alice, "conditions", CONDITION | {"diagnosis_date": "2020-03-01", "notes": "  Since my twenties.  "})
    assert item["condition_name"] == "Migraine with aura"
    assert item["confirmation"] == "clinician_confirmed"
    assert item["notes"] == "Since my twenties."  # trimmed
    url = f"{BASE}/conditions/{item['id']}"
    assert client.get(url, headers=alice).json() == item

    updated = client.patch(url, json={"status": "monitoring", "diagnosis_date": None, "notes": ""}, headers=alice).json()
    assert updated["status"] == "monitoring"
    assert updated["diagnosis_date"] is None and updated["notes"] is None  # null and empty clear
    assert updated["condition_name"] == "Migraine with aura"  # untouched fields stay

    assert client.delete(url, headers=alice).status_code == 204
    assert client.get(url, headers=alice).status_code == 404


def test_condition_defaults_and_nullable_fields(client, alice):
    item = post(client, alice, "conditions", {"condition_name": "Asthma", "category": "chronic_disease"})
    assert item["status"] == "active"
    assert item["confirmation"] == "self_reported"
    assert item["diagnosis_date"] is None and item["notes"] is None


def test_conditions_can_be_filtered_by_category(client, alice):
    post(client, alice, "conditions", CONDITION)
    post(client, alice, "conditions", {"condition_name": "Meningitis", "category": "serious_history", "status": "resolved"})
    post(client, alice, "conditions", {"condition_name": "Sinusitis", "category": "associated_condition"})
    names = lambda c: [i["condition_name"] for i in client.get(f"{BASE}/conditions", params={"category": c}, headers=alice).json()]  # noqa: E731
    assert names("serious_history") == ["Meningitis"]
    assert names("associated_condition") == ["Sinusitis"]
    assert len(client.get(f"{BASE}/conditions", headers=alice).json()) == 3
    assert client.get(f"{BASE}/conditions", params={"category": "nope"}, headers=alice).status_code == 422


def test_allergy_create_update_delete(client, alice):
    item = post(client, alice, "allergies", ALLERGY)
    assert item["severity"] == "moderate"
    url = f"{BASE}/allergies/{item['id']}"
    updated = client.patch(url, json={"reaction": None, "severity": "severe"}, headers=alice).json()
    assert updated["reaction"] is None and updated["severity"] == "severe"
    assert client.delete(url, headers=alice).status_code == 204
    assert client.get(f"{BASE}/allergies", headers=alice).json() == []


def test_allergy_severity_defaults_to_unknown(client, alice):
    item = post(client, alice, "allergies", {"name": "Peanuts", "type": "food"})
    assert item["severity"] == "unknown" and item["reaction"] is None


def test_procedure_create_update_delete(client, alice):
    item = post(client, alice, "procedures", PROCEDURE)
    assert item["procedure_date"] == "2015-04-02"
    url = f"{BASE}/procedures/{item['id']}"
    assert client.patch(url, json={"procedure_date": None}, headers=alice).json()["procedure_date"] is None
    assert client.delete(url, headers=alice).status_code == 204


def test_procedure_date_is_optional(client, alice):
    assert post(client, alice, "procedures", {"name": "Tonsillectomy"})["procedure_date"] is None


def test_summary_returns_everything_oldest_first(client, alice):
    first = post(client, alice, "conditions", CONDITION)
    second = post(client, alice, "conditions", {"condition_name": "Diabetes", "category": "chronic_disease"})
    post(client, alice, "allergies", ALLERGY)
    post(client, alice, "procedures", PROCEDURE)
    client.put(f"{BASE}/notes", json={"notes": "Family history of headaches."}, headers=alice)
    body = client.get(BASE, headers=alice).json()
    assert [c["id"] for c in body["conditions"]] == [first["id"], second["id"]]
    assert len(body["allergies"]) == 1 and len(body["procedures"]) == 1
    assert body["notes"]["notes"] == "Family history of headaches."


def test_notes_put_replaces_and_empty_removes(client, alice, db_session):
    assert client.get(f"{BASE}/notes", headers=alice).json() == {"notes": None, "updated_at": None}
    first = client.put(f"{BASE}/notes", json={"notes": "First"}, headers=alice).json()
    assert first["notes"] == "First" and first["updated_at"]
    assert client.put(f"{BASE}/notes", json={"notes": "Second"}, headers=alice).json()["notes"] == "Second"
    assert db_session.scalar(select(func.count()).select_from(MedicalNotes)) == 1  # one row per user
    assert client.put(f"{BASE}/notes", json={"notes": "   "}, headers=alice).json() == {"notes": None, "updated_at": None}
    assert db_session.scalar(select(func.count()).select_from(MedicalNotes)) == 0
    assert client.put(f"{BASE}/notes", json={"notes": None}, headers=alice).status_code == 200


# --- Validation -------------------------------------------------------------------------------

TOMORROW_PLUS = (date.today() + timedelta(days=3)).isoformat()


@pytest.mark.parametrize("kind, body", [
    ("conditions", CONDITION | {"category": "diagnosis"}),
    ("conditions", CONDITION | {"status": "cured"}),
    ("conditions", CONDITION | {"confirmation": "doctor"}),
    ("conditions", CONDITION | {"condition_name": "   "}),
    ("conditions", CONDITION | {"condition_name": "x" * 121}),
    ("conditions", CONDITION | {"diagnosis_date": TOMORROW_PLUS}),
    ("conditions", CONDITION | {"diagnosis_date": "1850-01-01"}),
    ("conditions", CONDITION | {"notes": "x" * 2001}),
    ("conditions", {"condition_name": "No category"}),
    ("allergies", ALLERGY | {"type": "pollen"}),
    ("allergies", ALLERGY | {"severity": "extreme"}),
    ("allergies", ALLERGY | {"reaction": "x" * 201}),
    ("allergies", {"name": "No type"}),
    ("procedures", PROCEDURE | {"procedure_date": TOMORROW_PLUS}),
    ("procedures", {"name": ""}),
    ("procedures", PROCEDURE | {"surgeon": "unknown"}),
])
def test_invalid_items_are_rejected(client, alice, kind, body):
    assert client.post(f"{BASE}/{kind}", json=body, headers=alice).status_code == 422


@pytest.mark.parametrize("kind, field", [
    ("conditions", "condition_name"), ("conditions", "category"), ("conditions", "status"), ("conditions", "confirmation"),
    ("allergies", "name"), ("allergies", "type"), ("allergies", "severity"), ("procedures", "name"),
])
def test_required_fields_cannot_be_cleared(client, alice, kind, field):
    item = post(client, alice, kind, BODIES[kind])
    assert client.patch(f"{BASE}/{kind}/{item['id']}", json={field: None}, headers=alice).status_code == 422


def test_notes_have_a_length_limit_and_reject_extra_fields(client, alice):
    assert client.put(f"{BASE}/notes", json={"notes": "x" * 4001}, headers=alice).status_code == 422
    assert client.put(f"{BASE}/notes", json={"notes": "ok", "user_id": "x"}, headers=alice).status_code == 422
    assert client.put(f"{BASE}/notes", json={}, headers=alice).status_code == 422


def test_invalid_id_is_rejected(client, alice):
    assert client.get(f"{BASE}/conditions/not-a-uuid", headers=alice).status_code == 422


def test_each_list_has_a_ceiling(client, alice, monkeypatch):
    from app.api.routes import medical_history

    monkeypatch.setattr(medical_history, "MAX_ITEMS_PER_LIST", 2)
    post(client, alice, "procedures", {"name": "One"})
    post(client, alice, "procedures", {"name": "Two"})
    assert client.post(f"{BASE}/procedures", json={"name": "Three"}, headers=alice).status_code == 409


# --- Database ---------------------------------------------------------------------------------

def test_deleting_a_user_deletes_their_medical_history(client, alice, db_session):
    post(client, alice, "conditions", CONDITION)
    post(client, alice, "allergies", ALLERGY)
    post(client, alice, "procedures", PROCEDURE)
    client.put(f"{BASE}/notes", json={"notes": "x"}, headers=alice)
    db_session.execute(delete(User).where(User.email == "mh.alice@example.com"))
    db_session.flush()
    for model in (MedicalCondition, MedicalAllergy, MedicalProcedure, MedicalNotes):
        assert db_session.scalar(select(func.count()).select_from(model)) == 0


def test_migrations_match_the_models(test_engine):
    """`alembic check`: the latest migration creates exactly what the models describe."""
    config = Config(str(ORIGIN_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(ORIGIN_DIR / "alembic"))
    with test_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.check(config)


def test_health_details_are_never_logged(client, alice, caplog):
    secret = "Synthetic private history note 7f3a"
    with caplog.at_level(logging.DEBUG):
        post(client, alice, "conditions", CONDITION | {"notes": secret})
        client.put(f"{BASE}/notes", json={"notes": secret}, headers=alice)
        client.get(BASE, headers=alice)
    assert secret not in caplog.text
    assert "Migraine with aura" not in caplog.text


# --- Medical report ---------------------------------------------------------------------------

@pytest.fixture
def history(client, alice):
    post(client, alice, "conditions", CONDITION | {"diagnosis_date": "2019-05-10", "notes": "Aura is visual."})
    post(client, alice, "conditions", {"condition_name": "My own condition", "category": "chronic_disease", "status": "monitoring", "confirmation": "unsure"})
    post(client, alice, "conditions", {"condition_name": "High blood pressure", "category": "associated_condition"})
    post(client, alice, "conditions", {"condition_name": "Meningitis", "category": "serious_history", "status": "resolved", "confirmation": "clinician_confirmed"})
    post(client, alice, "allergies", ALLERGY)
    post(client, alice, "procedures", PROCEDURE)
    client.put(f"{BASE}/notes", json={"notes": "Family history of headaches."}, headers=alice)
    return alice


def report(client, headers, lang):
    response = client.get(URL, params=JUNE | {"lang": lang}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def mh_section(rep):
    return next(s for s in rep["sections"] if s["id"] == "medical_history")


def generated_strings(section) -> list[str]:
    """Every string the report wrote itself in this section (not the user's own words)."""
    out = [section["title"]]
    for b in section["blocks"]:
        if b["type"] == "paragraph" and not b.get("user_text"):
            out.append(b["text"])
        elif b["type"] == "subheading":
            out.append(b["text"])
        elif b["type"] == "history_item":
            out += [f"{f['label']} {f['value']}" for f in b["fields"]] + [d["label"] for d in b["details"]]
    return out


@pytest.mark.parametrize("lang, title", [("en", "Medical history (reported by you)"), ("ar", "التاريخ المرضي (كما أبلغت عنه)")])
def test_report_has_the_section_in_both_languages(client, history, lang, title):
    rep = report(client, history, lang)
    ids = [s["id"] for s in rep["sections"]]
    assert ids[:3] == ["info", "medical_history", "overview"]  # apart from the records and the analysis
    section = mh_section(rep)
    assert section["title"] == title
    items = [b for b in section["blocks"] if b["type"] == "history_item"]
    assert len(items) == 6
    assert rep["data"]["medical_history"] == {"conditions": 4, "allergies": 1, "procedures": 1, "notes": True}


def test_report_shows_status_and_confirmation_for_each_item(client, history):
    section = mh_section(report(client, history, "en"))
    items = {b["name"]: b for b in section["blocks"] if b["type"] == "history_item"}
    fields = lambda name: {f["label"]: f["value"] for f in items[name]["fields"]}  # noqa: E731
    assert fields("Migraine with aura") == {
        "Status": "Active", "Confirmation": "Confirmed by a clinician (as you reported)", "Date": "10 May 2019",
    }
    assert fields("My own condition") == {"Status": "Being monitored", "Confirmation": "Unsure"}
    assert fields("High blood pressure")["Confirmation"] == "Self-reported (not confirmed by a clinician)"
    assert fields("Penicillin") == {"Type": "Medication", "Severity": "Moderate"}
    assert items["Penicillin"]["details"] == [{"label": "Reaction", "text": "Rash"}]
    assert items["Migraine with aura"]["details"] == [{"label": "Notes", "text": "Aura is visual."}]
    headings = [b["text"] for b in section["blocks"] if b["type"] == "subheading"]
    assert headings == [
        "Long-term conditions", "Headache disorders", "Other conditions you listed", "Serious past illnesses",
        "Allergies", "Surgeries and procedures", "Additional notes",
    ]
    # Meningitis is a serious past illness, never listed with the headache-related conditions.
    blocks = section["blocks"]
    serious = next(i for i, b in enumerate(blocks) if b.get("text") == "Serious past illnesses")
    assert blocks[serious + 1]["name"] == "Meningitis"


def test_arabic_report_translates_predefined_names_and_keeps_typed_ones(client, history):
    section = mh_section(report(client, history, "ar"))
    names = [b["name"] for b in section["blocks"] if b["type"] == "history_item"]
    assert "الصداع النصفي مع هالة" in names
    assert "ارتفاع ضغط الدم" in names
    assert "My own condition" in names and "Penicillin" in names  # typed text stays as typed
    values = [f["value"] for b in section["blocks"] if b["type"] == "history_item" for f in b["fields"]]
    assert "أكّدها طبيب (حسب ما ذكرت)" in values
    assert "10 مايو 2019" in values
    # No ISO dates inside Arabic text (a right-to-left paragraph would reverse them).
    assert not any(re.search(r"\d{4}-\d{2}-\d{2}", v) for v in values)


def test_empty_history_still_has_the_section(client, alice):
    section = mh_section(report(client, alice, "en"))
    assert [b["text"] for b in section["blocks"] if b["type"] == "paragraph"][-1] == "No medical history was entered."
    assert report(client, alice, "en")["data"]["medical_history"]["conditions"] == 0


@pytest.mark.parametrize("lang", ["en", "ar"])
def test_section_wording_is_descriptive_only(client, history, lang):
    text = generated_strings(mh_section(report(client, history, lang)))
    assert text
    if lang == "en":
        assert [t for t in text if FORBIDDEN_EN.search(t)] == []
    else:
        assert [t for t in text if any(word in t for word in FORBIDDEN_AR)] == []


def test_report_lists_the_limitation(client, history):
    limits = next(s for s in report(client, history, "en")["sections"] if s["id"] == "limitations")["blocks"][0]["items"]
    assert any("Medical history is shown as you entered it" in item for item in limits)


def test_report_never_includes_another_users_history(client, history, bob):
    rep = report(client, bob, "en")
    assert "Penicillin" not in str(rep) and "Family history of headaches." not in str(rep)


def test_english_pdf_contains_the_section(client, history):
    pages = pdf_text(client.get(PDF, params=JUNE | {"lang": "en"}, headers=history).content)
    whole = "\n".join(pages)
    for text in ("Medical history (reported by you)", "Migraine with aura", "Penicillin", "Rash",
                 "Confirmed by a clinician (as you reported)", "Family history of headaches."):
        assert text in whole


def test_arabic_pdf_renders_the_section(client, history):
    response = client.get(PDF, params=JUNE | {"lang": "ar"}, headers=history)
    assert response.status_code == 200
    whole = "\n".join(pdf_text(response.content))
    # Latin text typed by the user keeps its own left-to-right order in the Arabic PDF.
    assert "Penicillin" in whole and "My own condition" in whole
