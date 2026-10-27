"""GET /reports/medical and /reports/medical/pdf. Run from backend/ with:  python -m pytest

Synthetic data only, written to namat_test inside a rolled-back transaction.
Dates are fixed (June 2026) so every expected number can be checked by hand.
"""

import io
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
import uharfbuzz as hb
from pypdf import PdfReader
from sqlalchemy import select

from app.models import DailyFactor, EpisodeSymptom, HeadacheEpisode, MedicationDose, SleepLog, User
from app.reports.pdf import ReportPDF, merged_font
from app.reports.text import DISCLAIMER_AR, DISCLAIMER_EN

URL = "/reports/medical"
PDF = "/reports/medical/pdf"
JUNE = {"start_date": "2026-06-01", "end_date": "2026-06-30"}
SECTIONS = [
    "info", "overview", "history", "pain", "symptoms", "sleep", "factors",
    "medication", "observations", "summary", "questions", "limitations", "disclaimer",
]
NAUSEA, LIGHT = 1, 3

# Wording the generated text must never use (the required disclaimer is checked separately).
FORBIDDEN_EN = re.compile(
    r"\b(cause[sd]?|causing|caused by|diagnos\w*|migraine|effective|ineffective|works?|worked|should|"
    r"stop taking|recommend\w*|treat\w*|cure\w*|increase your|reduce your)\b",
    re.IGNORECASE,
)
FORBIDDEN_AR = ("يسبب", "يسبّب", "تسبب", "تسبّب", "تشخيص", "علاج", "توقف عن", "فعّال", "فعال", "صداع نصفي", "ننصح", "يُنصح")


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


@pytest.fixture
def user(client, db_session, make_user):
    headers = make_user("report.a@example.com")
    return db_session.scalar(select(User).where(User.email == "report.a@example.com")), headers


def episode(db, owner, start, end=None, intensity=None, symptoms=(), location=None, notes=None, aura=False):
    e = HeadacheEpisode(
        user_id=owner.id, started_at=start, ended_at=end, peak_intensity=intensity,
        pain_location=location, notes=notes, had_aura=aura,
    )
    e.symptom_links = [EpisodeSymptom(symptom_id=s) for s in symptoms]
    db.add(e)
    db.flush()
    return e


def dose(db, owner, ep, taken_at, name="Ibuprofen", amount="400", relief=None):
    db.add(MedicationDose(
        user_id=owner.id, episode_id=ep.id if ep else None, medication_name=name,
        dose_amount=Decimal(amount) if amount else None, dose_unit="mg", taken_at=taken_at, relief_rating=relief,
    ))
    db.flush()


def get(client, headers, lang="en", **params):
    response = client.get(URL, params=JUNE | params | {"lang": lang}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def section(report, id_):
    return next(s for s in report["sections"] if s["id"] == id_)


def blocks(report, id_, kind):
    return [b for b in section(report, id_)["blocks"] if b["type"] == kind]


def generated_text(report) -> list[str]:
    """Every string the report wrote itself (not user-typed notes, not the disclaimer)."""
    out = [report["title"], report["subtitle"]]
    for s in report["sections"]:
        if s["id"] == "disclaimer":
            continue
        out.append(s["title"])
        for b in s["blocks"]:
            if b["type"] == "paragraph" and not b.get("user_text"):
                out.append(b["text"])
            elif b["type"] == "list":
                out += b["items"]
            elif b["type"] in ("facts",):
                out += [f"{i['label']} {i['value']}" for i in b["items"]]
            elif b["type"] == "table":
                out += [c["label"] for c in b["columns"]] + [cell for row in b["rows"] for cell in row]
            elif b["type"] == "observation":
                out += [b["title"], b["description"], b["limitation"]] + [f["value"] for f in b["facts"]]
            elif b["type"] == "episode":
                out += [b["heading"]] + [f"{f['label']} {f['value']}" for f in b["fields"]]
    return out


def pdf_text(content: bytes) -> list[str]:
    # pypdf adds control characters between some shaped Arabic glyphs; drop them.
    reader = PdfReader(io.BytesIO(content))
    return [
        "".join(ch for ch in unicodedata.normalize("NFKC", page.extract_text()) if unicodedata.category(ch) != "Cc")
        for page in reader.pages
    ]


@pytest.fixture
def busy_month(db_session, user):
    """June 2026: four episodes, sleep, factors and medication; plus May records."""
    owner = user[0]
    db = db_session
    may = episode(db, owner, utc(2026, 5, 20, 9), utc(2026, 5, 20, 11), 5)
    e1 = episode(db, owner, utc(2026, 6, 2, 8), utc(2026, 6, 2, 10), 6, [NAUSEA, LIGHT], "left", notes="Bright office lights.")
    e2 = episode(db, owner, utc(2026, 6, 10, 22), utc(2026, 6, 11, 4), 8, [NAUSEA], "right", aura=True)  # crosses midnight
    e3 = episode(db, owner, utc(2026, 6, 15, 14), None, None)  # ongoing, unrated, nothing else recorded
    e4 = episode(db, owner, utc(2026, 6, 25, 7), utc(2026, 6, 25, 8), 0, [LIGHT], "frontal")  # 0 is a real rating
    dose(db, owner, e1, utc(2026, 6, 2, 8, 30), relief=2)
    dose(db, owner, e2, utc(2026, 6, 10, 23), name="ibuprofen ", relief=None)
    dose(db, owner, None, utc(2026, 6, 20, 9), name="Paracetamol", amount=None)  # not linked
    dose(db, owner, may, utc(2026, 5, 20, 9, 30))  # previous period: not in June's history
    for i in range(5):
        night = date(2026, 6, 1) + timedelta(days=i)
        bed = datetime.combine(night, datetime.min.time(), timezone.utc) + timedelta(hours=23)
        db.add(SleepLog(user_id=owner.id, sleep_date=night, bedtime=bed, wake_time=bed + timedelta(hours=6 + i), quality=3 if i else None))
    db.add(DailyFactor(user_id=owner.id, log_date=date(2026, 6, 2), stress_level=7, caffeine_mg=0, skipped_meal=False))
    db.add(DailyFactor(user_id=owner.id, log_date=date(2026, 6, 3), stress_level=2))
    db.flush()
    return {"may": may, "june": [e1, e2, e3, e4]}


# --- Access, privacy, caching -------------------------------------------------------------

@pytest.mark.parametrize("path", [URL, PDF])
def test_requires_a_token(client, path):
    assert client.get(path, params=JUNE).status_code == 401


@pytest.mark.parametrize("path", [URL, PDF])
def test_responses_are_never_cached(client, user, path):
    response = client.get(path, params=JUNE, headers=user[1])
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, private"


def test_users_only_see_their_own_records(client, db_session, user, make_user, busy_month):
    bob_headers = make_user("report.b@example.com")
    bob = db_session.scalar(select(User).where(User.email == "report.b@example.com"))
    bob_episode = episode(db_session, bob, utc(2026, 6, 5, 9), utc(2026, 6, 5, 10), 9, notes="Bob's private note")

    alice_report = get(client, user[1])
    assert str(bob_episode.id) not in alice_report["data"]["episode_ids"]
    assert "Bob's private note" not in str(alice_report)

    # A user_id parameter is ignored: Bob still gets only his own report.
    bob_report = get(client, bob_headers, user_id=str(user[0].id))
    assert bob_report["data"]["episode_ids"] == [str(bob_episode.id)]
    assert bob_report["data"]["sleep"]["nights"] == 0


# --- Structure -----------------------------------------------------------------------------

@pytest.mark.parametrize("lang", ["en", "ar"])
def test_every_section_is_present_in_order(client, user, busy_month, lang):
    report = get(client, user[1], lang)
    assert [s["id"] for s in report["sections"]] == SECTIONS
    assert report["direction"] == ("rtl" if lang == "ar" else "ltr")
    assert all(s["title"] for s in report["sections"])


def test_exact_disclaimer_in_both_languages(client, user):
    en = section(get(client, user[1], "en"), "disclaimer")["blocks"][0]["text"]
    ar = section(get(client, user[1], "ar"), "disclaimer")["blocks"][0]["text"]
    assert en == DISCLAIMER_EN
    assert en.startswith("This report is generated from information recorded by the user in Namat.")
    assert en.endswith("should not replace professional medical assessment.")
    assert ar == DISCLAIMER_AR


# --- Calculations -----------------------------------------------------------------------------

def test_overview_matches_the_records(client, user, busy_month):
    report = get(client, user[1])
    ov = report["data"]["overview"]
    assert ov["total_episodes"] == 4
    assert ov["headache_days"] == 5  # 2, 10, 11 (crosses midnight), 15, 25 June
    assert ov["rated_episodes"] == 3
    assert ov["average_intensity"] == round((6 + 8 + 0) / 3, 1)
    assert ov["highest_intensity"] == 8
    assert ov["episodes_with_duration"] == 3  # the ongoing one is left out
    assert ov["average_duration_minutes"] == round((120 + 360 + 60) / 3)
    assert ov["median_duration_minutes"] == 120
    assert ov["ongoing_episodes"] == 1
    # Same headache-day rule as the dashboard.
    dashboard = client.get("/analytics/dashboard", params=JUNE, headers=user[1]).json()
    assert dashboard["summary"]["headache_days"] == ov["headache_days"]


def test_history_lists_every_episode_in_order(client, user, busy_month):
    report = get(client, user[1])
    june_ids = [str(e.id) for e in busy_month["june"]]
    assert report["data"]["episode_ids"] == june_ids  # oldest first, May excluded
    history = blocks(report, "history", "episode")
    assert [b["number"] for b in history] == [1, 2, 3, 4]
    assert [b["heading"] for b in history][0] == "Episode 1 · Tue 2 Jun 2026"


def test_history_separates_not_recorded_from_none(client, user, busy_month):
    history = blocks(get(client, user[1]), "history", "episode")
    fields = lambda b: {f["label"]: f["value"] for f in b["fields"] if f["label"]}  # noqa: E731
    ongoing = fields(history[2])
    assert ongoing["Ended"] == "No end time recorded"
    assert ongoing["Peak intensity"] == "Not recorded"
    assert ongoing["Pain location"] == "Not recorded"
    assert ongoing["Symptoms"] == "None recorded"
    assert ongoing["Medication"] == "None recorded"
    assert fields(history[3])["Peak intensity"] == "0/10 · None"  # a recorded zero
    first = fields(history[0])
    assert first["Symptoms"] == "Nausea, Sensitivity to light"
    assert history[0]["notes"] == "Bright office lights."
    assert fields(history[1])["End" if False else "Ended"] == "11 Jun 2026, 04:00"  # ends the next day
    assert fields(history[1])["Aura"] == "Yes"


def test_long_notes_are_kept_whole(client, db_session, user):
    note = "Detailed note. " * 130  # ~2,000 characters
    episode(db_session, user[0], utc(2026, 6, 3, 9), utc(2026, 6, 3, 10), 4, notes=note.strip())
    history = blocks(get(client, user[1]), "history", "episode")
    assert history[0]["notes"] == note.strip()


def test_previous_period_comparison_only_when_tracked(client, db_session, user, busy_month):
    # First record is 20 May: the previous 30 days (2–31 May) weren't tracked from the start.
    report = get(client, user[1])
    assert report["data"]["previous_period"]["tracked"] is False
    assert report["data"]["overview"]["previous_total_episodes"] is None
    assert any("don't cover that period" in b["text"] for b in blocks(report, "overview", "paragraph"))

    episode(db_session, user[0], utc(2026, 5, 2, 9), utc(2026, 5, 2, 10), 3)  # now tracked from 2 May
    report = get(client, user[1])
    assert report["data"]["previous_period"] == {"start": "2026-05-02", "end": "2026-05-31", "tracked": True}
    assert report["data"]["overview"]["previous_total_episodes"] == 2
    comparison = blocks(report, "overview", "paragraph")[0]["text"]
    assert "2 episodes" in comparison and "4 episodes" in comparison


def test_medication_history_is_descriptive(client, user, busy_month):
    report = get(client, user[1])
    assert report["data"]["medication"] == {"doses": 3, "days": 3, "unlinked": 1}
    summary, doses = blocks(report, "medication", "table")
    # "Ibuprofen" and "ibuprofen " are the same medication.
    assert summary["rows"][0][:4] == ["Ibuprofen", "2", "2", "2"]
    assert [row[3] for row in doses["rows"]] == ["Episode 1", "Episode 2", "Not linked"]
    assert [row[4] for row in doses["rows"]] == ["Good relief", "Not recorded", "Not recorded"]
    assert doses["rows"][2][2] == "Not recorded"  # no amount recorded
    note = blocks(report, "medication", "paragraph")[-1]["text"]
    assert "doesn't assess whether any medication helped" in note


def test_sleep_and_factor_sections_use_only_recorded_values(client, user, busy_month):
    report = get(client, user[1])
    assert report["data"]["sleep"] == {
        "nights": 5, "missing_nights": 25, "average_hours": 8.0, "quality_recorded": 4, "awakenings_recorded": 0,
    }
    sleep_facts = {i["label"]: i["value"] for i in blocks(report, "sleep", "facts")[0]["items"]}
    assert sleep_facts["Times woken during the night"] == "Not recorded"
    factor_rows = {row[0]: row for row in blocks(report, "factors", "table")[0]["rows"]}
    assert factor_rows["Stress (0–10)"][1] == "2"  # days recorded
    assert factor_rows["Caffeine (mg)"][2].startswith("average 0")  # a recorded zero
    assert factor_rows["Water (ml)"][1] == "0"
    assert factor_rows["Stress (0–10)"][4] == "Too few days to compare"
    by_day = blocks(report, "factors", "table")[1]
    assert [c["label"] for c in by_day["columns"]] == ["Date", "Stress (0–10)", "Caffeine (mg)", "Skipped a meal"]
    assert by_day["rows"][1] == ["3 Jun 2026", "2", "—", "—"]


def test_empty_period_still_produces_a_complete_report(client, user):
    report = get(client, user[1])
    assert [s["id"] for s in report["sections"]] == SECTIONS
    assert report["data"]["overview"]["total_episodes"] == 0
    assert blocks(report, "history", "paragraph")[-1]["text"] == "No episodes were recorded in this period."
    limitations = blocks(report, "limitations", "list")[0]["items"]
    assert any("fewer than 3 episodes" in item for item in limitations)


# --- Observations, summary, questions -------------------------------------------------------------

def test_observations_come_from_the_insights_engine(client, user, busy_month):
    report = get(client, user[1])
    insights = client.get("/insights", params=JUNE, headers=user[1]).json()
    assert report["data"]["observation_ids"] == [i["id"] for i in insights["insights"]]
    for b in blocks(report, "observations", "observation"):
        labels = [f["label"] for f in b["facts"]]
        assert labels == ["Evidence level", "Statistical check", "Based on"]
        assert b["limitation"]


@pytest.mark.parametrize("lang", ["en", "ar"])
def test_generated_text_has_no_unsupported_medical_claims(client, user, busy_month, lang):
    text = generated_text(get(client, user[1], lang))
    if lang == "en":
        bad = [t for t in text if FORBIDDEN_EN.search(t)]
    else:
        bad = [t for t in text if any(word in t for word in FORBIDDEN_AR)]
    assert bad == []


def test_questions_are_neutral_prompts(client, user, busy_month):
    items = blocks(get(client, user[1]), "questions", "list")[0]["items"]
    assert items and all(q.endswith("?") for q in items)
    assert any("aura" in q for q in items)
    assert any("8/10" not in q and "7/10 or higher" in q for q in items)


# --- Validation -----------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "params",
    [
        {"start_date": "2026-06-30", "end_date": "2026-06-01"},
        {"start_date": "2026-06-01"},
        {"start_date": "2025-01-01", "end_date": "2026-06-30"},
        {"period": "90d"},
        {"lang": "fr"},
    ],
)
def test_invalid_parameters_are_rejected(client, user, params):
    query = {"lang": "en"} | params
    assert client.get(URL, params=query, headers=user[1]).status_code == 422
    assert client.get(PDF, params=query, headers=user[1]).status_code == 422


def test_presets_work(client, user):
    for period in ("7d", "30d", "3m", "6m", "12m"):
        response = client.get(URL, params={"period": period}, headers=user[1])
        assert response.status_code == 200
        assert response.json()["data"]["period"]["period"] == period


# --- PDF ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("lang", ["en", "ar"])
def test_pdf_file_basics(client, user, busy_month, lang):
    response = client.get(PDF, params=JUNE | {"lang": lang}, headers=user[1])
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"] == (
        f'attachment; filename="namat-medical-report-2026-06-01-to-2026-06-30-{lang}.pdf"'
    )
    assert re.fullmatch(r'attachment; filename="[a-z0-9-]+\.pdf"', response.headers["content-disposition"])
    assert response.content.startswith(b"%PDF-")


def test_english_pdf_has_every_section_and_page_numbers(client, user, busy_month):
    pages = pdf_text(client.get(PDF, params=JUNE | {"lang": "en"}, headers=user[1]).content)
    whole = "\n".join(pages)
    for title in ("Report information", "Headache overview", "Episode history", "Pain characteristics",
                  "Associated symptoms", "Sleep history", "Daily factors", "Medication history", "Key observations",
                  "Summary for discussion with a doctor", "Questions to discuss with a doctor",
                  "Missing information and limitations", "Medical disclaimer"):
        assert title in whole
    assert "Bright office lights." in whole
    assert "do not establish causation" in whole
    for n, page in enumerate(pages, start=1):
        assert f"Page {n} of {len(pages)}" in page


def test_long_history_flows_over_many_pages_with_repeated_headers(client, db_session, user):
    owner = user[0]
    for i in range(30):
        start = utc(2026, 6, 1 + i % 30, 6 + i % 12)
        e = episode(db_session, owner, start, start + timedelta(hours=2), i % 11, [NAUSEA],
                    notes=("A long note about this episode. " * 60) if i % 5 == 0 else None)
        dose(db_session, owner, e, start + timedelta(minutes=20))
    content = client.get(PDF, params=JUNE | {"lang": "en"}, headers=user[1]).content
    pages = pdf_text(content)
    assert len(pages) >= 8
    # The 30-row dose table continues onto a second page with its header row repeated.
    with_header = [p for p in pages if "Date and time" in p and "Relief you recorded" in p]
    assert len(with_header) >= 2
    assert "Episode 30" in "\n".join(pages)


def test_arabic_pdf_is_shaped_right_to_left_and_complete(client, user, busy_month):
    content = client.get(PDF, params=JUNE | {"lang": "ar"}, headers=user[1]).content
    reader = PdfReader(io.BytesIO(content))
    pages = pdf_text(content)
    # PDF text extraction of shaped Arabic is lossy (some joined letter forms
    # come back as other characters), so only phrases that extract cleanly are
    # checked here; the layout itself was checked by rendering the pages.
    # They come back in reading order, i.e. not reversed.
    assert pages[0].startswith("التقرير الطبي للصداع")
    assert "معلومات التقرير" in pages[0]
    for page in pages:
        assert "صفحة" in page and str(len(pages)) in page
    # One embedded font that covers both scripts (no fallback switching).
    fonts = {f.get_object()["/BaseFont"] for p in reader.pages for f in p["/Resources"]["/Font"].values()}
    assert fonts and all("NotoSansArabic" in str(f) for f in fonts)
    assert reader.metadata.get("/Title") == "التقرير الطبي للصداع"


def test_arabic_report_uses_shaping_and_rtl(client, user):
    report = get(client, user[1], "ar")
    pdf = ReportPDF(report)
    assert pdf.text_shaping["use_shaping_engine"] is True
    assert str(pdf.text_shaping["direction"].value).lower() == "rtl"
    # The embedded font joins Arabic letters: shaping gives contextual forms,
    # not the isolated letters the characters map to on their own.
    font = hb.Font(hb.Face(hb.Blob.from_file_path(str(merged_font("arabic", "Regular")))))
    buf = hb.Buffer()
    buf.add_str("صداع")
    buf.guess_segment_properties()
    hb.shape(font, buf)
    shaped = [g.codepoint for g in buf.glyph_infos]
    isolated = [font.get_nominal_glyph(ord(c)) for c in reversed("صداع")]
    assert buf.direction == "rtl"
    assert shaped != isolated
