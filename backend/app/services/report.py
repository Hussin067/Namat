"""The medical report: one user's records for a period, as a document model.

build_report() returns
  - "data":     the raw numbers (counts, averages, sample sizes), and
  - "sections": the report itself, sections A–M, each a list of blocks
                (facts, paragraph, list, table, bars, episode, observation,
                callout) with every string already in the report's language.

The frontend preview and the PDF (app/reports/pdf.py) render the same
sections, so they can't disagree. Statistics come from the insights engine
(app/services/insights.py: analyze() and generate_insights()), so the report
uses the same rules, thresholds and chance filter as the dashboard insights.

Nothing here diagnoses, states a cause, judges whether a medication worked or
suggests a change; tests/test_reports.py scans the generated text for that.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import DailyFactor, EpisodeSymptom, HeadacheEpisode, MedicationDose, SleepLog, User
from app.models.episode import PAIN_LOCATIONS
from app.reports.text import DISCLAIMER_AR, DISCLAIMER_EN, OBSERVATIONS_AR, Lang
from app.services.analytics import DateRange
from app.services.insights import BOOLEAN_FACTORS, NUMERIC_FACTORS, THRESHOLDS, analyze, generate_insights

LANGUAGES = ("en", "ar")
SEVERE_FROM = 7  # "severe" band starts here (same bands as the app)
DURATION_BANDS = (("under_1h", 60), ("h1_4", 240), ("h4_12", 720), ("h12_24", 1440), ("over_24h", None))
SAMPLE_UNIT = {
    "frequency": "episodes",
    "intensity": "episodes",
    "timing": "episodes",
    "symptoms": "episodes",
    "sleep": "days",
    "factors": "days",
    "medication": "doses",
}


def _mean(values) -> float | None:
    values = [float(v) for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _band(value: int) -> str:
    if value == 0:
        return "none"
    if value <= 3:
        return "mild"
    if value <= 6:
        return "moderate"
    if value <= 8:
        return "severe"
    return "very_severe"


def _duration_band(minutes: int) -> str:
    return next(name for name, limit in DURATION_BANDS if limit is None or minutes < limit)


def _bucket(day: date, interval: str) -> date:
    if interval == "week":
        return day - timedelta(days=day.weekday())
    if interval == "month":
        return day.replace(day=1)
    return day


# ---------------------------------------------------------------------------
# Blocks (the document model shared by the preview and the PDF)
# ---------------------------------------------------------------------------

def facts(items: list[tuple[str, str]]) -> dict:
    return {"type": "facts", "items": [{"label": k, "value": v} for k, v in items]}


def paragraph(text: str, style: str = "body", user_text: bool = False) -> dict:
    # user_text: typed by the user, so its direction comes from its own content.
    return {"type": "paragraph", "text": text, "style": style, "user_text": user_text}


def bullet_list(items: list[str]) -> dict:
    return {"type": "list", "items": items}


def subheading(text: str) -> dict:
    return {"type": "subheading", "text": text}


def table(columns: list[tuple[str, float]], rows: list[list[str]], title: str | None = None) -> dict:
    """columns: (label, relative width). Every cell is text."""
    return {
        "type": "table",
        "title": title,
        "columns": [{"label": label, "width": width} for label, width in columns],
        "rows": rows,
    }


def bars(title: str, items: list[tuple[str, float, str]], unit_max: float | None = None) -> dict:
    """items: (label, value, displayed value). Bars are scaled to the largest value."""
    return {
        "type": "bars",
        "title": title,
        "max": unit_max or max([v for _, v, _ in items] + [0]) or 1,
        "items": [{"label": label, "value": value, "display": display} for label, value, display in items],
    }


def section(id_: str, L: Lang, blocks: list[dict]) -> dict:
    return {"id": id_, "title": L.t(f"sections.{id_}"), "blocks": blocks}


# ---------------------------------------------------------------------------
# Loading (only the token's user)
# ---------------------------------------------------------------------------

def _load(db: Session, user: User, rng: DateRange) -> dict:
    lower, upper = rng.utc_bounds()
    episodes = db.scalars(
        select(HeadacheEpisode)
        .where(HeadacheEpisode.user_id == user.id, HeadacheEpisode.started_at >= lower, HeadacheEpisode.started_at < upper)
        .order_by(HeadacheEpisode.started_at, HeadacheEpisode.id)
        .options(
            selectinload(HeadacheEpisode.symptom_links).selectinload(EpisodeSymptom.symptom),
            selectinload(HeadacheEpisode.medication_doses),
        )
    ).all()
    doses = db.scalars(
        select(MedicationDose)
        .where(MedicationDose.user_id == user.id, MedicationDose.taken_at >= lower, MedicationDose.taken_at < upper)
        .order_by(MedicationDose.taken_at, MedicationDose.id)
    ).all()
    sleep = db.scalars(
        select(SleepLog)
        .where(SleepLog.user_id == user.id, SleepLog.sleep_date >= rng.start, SleepLog.sleep_date <= rng.end)
        .order_by(SleepLog.sleep_date)
    ).all()
    factor_rows = db.scalars(
        select(DailyFactor)
        .where(DailyFactor.user_id == user.id, DailyFactor.log_date >= rng.start, DailyFactor.log_date <= rng.end)
        .order_by(DailyFactor.log_date)
    ).all()
    latest = {
        "episode": db.scalar(select(func.max(HeadacheEpisode.started_at)).where(HeadacheEpisode.user_id == user.id)),
        "sleep": db.scalar(select(func.max(SleepLog.sleep_date)).where(SleepLog.user_id == user.id)),
        "factors": db.scalar(select(func.max(DailyFactor.log_date)).where(DailyFactor.user_id == user.id)),
        "medication": db.scalar(select(func.max(MedicationDose.taken_at)).where(MedicationDose.user_id == user.id)),
    }
    return {"episodes": episodes, "doses": doses, "sleep": sleep, "factors": factor_rows, "latest": latest}


def _latest_entry(latest: dict, tz) -> tuple[str, date] | None:
    """The most recent record of any kind (by its own date), across all time."""
    candidates = []
    for kind, value in latest.items():
        if value is None:
            continue
        day = value.astimezone(tz).date() if isinstance(value, datetime) else value
        candidates.append((day, kind))
    if not candidates:
        return None
    day, kind = max(candidates)
    return kind, day


# ---------------------------------------------------------------------------
# Observations (from the insights engine) in the report's language
# ---------------------------------------------------------------------------

def _observation_text(ins: dict, L: Lang) -> tuple[str, str]:
    """Title and description. English is the engine's own text."""
    if not L.rtl:
        return ins["title"], ins["description"]
    e, iid, A = ins["evidence"], ins["id"], OBSERVATIONS_AR
    if iid.startswith("frequency_"):
        kind = iid.removeprefix("frequency_")
        return A[f"frequency_{kind}"], A["frequency_body"].format(
            current=L.count("episodes", e["current"]), previous=L.count("episodes", e["previous"]), days=e["days"]
        )
    if iid.startswith("intensity_"):
        return A[iid], A["intensity_body"].format(current=L.num(e["current"]), previous=L.num(e["previous"]), days=e["days"])
    if iid.startswith("time_of_day_"):
        part = L.t(f"part_names.{e['part_of_day']}")
        return A["time_title"].format(part=part), A["time_body"].format(count=e["count"], total=e["total"], part=part)
    if iid == "symptom_common":
        return A["symptom_common"], A["symptom_common_body"].format(symptom=L.symptom(e["symptom"]), count=e["count"], total=e["total"])
    if iid == "symptom_pair":
        a, b = (L.symptom(s) for s in e["symptoms"])
        return A["symptom_pair"], A["symptom_pair_body"].format(a=a, b=b, count=e["count"], total=e["total"])
    if iid.startswith("sleep_"):
        if e["comparison_type"] == "rate":
            body = A["sleep_rate_body"].format(
                a=L.pct(e["shorter_headache_rate"]), b=L.pct(e["other_headache_rate"]), hours=L.num(e["median_hours"])
            )
        else:
            body = A["sleep_intensity_body"].format(
                a=L.num(e["shorter_avg_intensity"]), b=L.num(e["other_avg_intensity"]), hours=L.num(e["median_hours"])
            )
        return A["sleep_title"], body
    if iid.startswith("factor_"):
        a, b = A["factor_groups"][e["factor"]]
        if e["comparison_type"] == "rate":
            body = A["factor_rate_body"].format(
                a=a, b=b, a_rate=L.pct(e["group_a_headache_rate"]), b_rate=L.pct(e["group_b_headache_rate"])
            )
        else:
            body = A["factor_intensity_body"].format(
                a=a, b=b, a_avg=L.num(e["group_a_avg_intensity"]), b_avg=L.num(e["group_b_avg_intensity"])
            )
        return A["factor_title"], body
    # medication_summary
    return A["medication_title"], A["medication_body"].format(
        doses=L.count("doses", e["doses"]),
        top=e["top_medication"],
        top_doses=e["top_medication_doses"],
        with_medication=e["episodes_with_medication"],
        total=e["total_episodes"],
    )


def _observation_block(ins: dict, L: Lang) -> dict:
    title, description = _observation_text(ins, L)
    e, category, level = ins["evidence"], ins["category"], ins["evidence_level"]
    if "p_value" in e:
        test = "fisher" if e["comparison_type"] == "rate" else "permutation"
        statistic = L.t(f"observations.{test}", p=L.p_value(e["p_value"]))
    elif category == "frequency":
        statistic = L.t("observations.counts", a=L.count("episodes", e["current"]), b=L.count("episodes", e["previous"]))
    elif category == "intensity":
        statistic = L.t("observations.counts", a=f"{L.num(e['current'])}/10", b=f"{L.num(e['previous'])}/10")
    else:
        statistic = L.t("observations.descriptive")
    limitation = L.t("observations.limitation") if category != "medication" else L.t("medication.note")
    if level == "limited":
        limitation = f"{limitation} {L.t('observations.limitation_limited')}"
    return {
        "type": "observation",
        "id": ins["id"],
        "category": category,
        "level": level,
        "level_label": L.t(f"observations.levels.{level}"),
        "title": title,
        "description": description,
        "facts": [
            {"label": L.t("observations.level"), "value": f"{L.t(f'observations.levels.{level}')}: {L.t(f'observations.level_help.{level}')}"},
            {"label": L.t("observations.statistic"), "value": statistic},
            {"label": L.t("observations.sample"), "value": L.count(SAMPLE_UNIT[category], ins["sample_size"])},
        ],
        "limitation": limitation,
    }


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------

def build_report(db: Session, user: User, rng: DateRange, lang: str, now: datetime | None = None) -> dict:
    L = Lang(lang)
    tz, t = rng.tz, THRESHOLDS
    now = now or datetime.now(timezone.utc)
    result = analyze(db, user, rng)
    insights = generate_insights(result)
    rec = _load(db, user, rng)
    episodes, doses = rec["episodes"], rec["doses"]
    freq, inten = result["frequency"], result["intensity"]
    prev_start, prev_end = result["previous_range"]
    total = len(episodes)
    local = lambda dt: dt.astimezone(tz)  # noqa: E731
    number_of = {e.id: i for i, e in enumerate(episodes, start=1)}
    insight_ids = [i["id"] for i in insights["insights"]]
    gap_codes = {g["code"] for g in insights["data_gaps"]}

    # --- Numbers ----------------------------------------------------------------
    durations = [
        int((e.ended_at - e.started_at).total_seconds() // 60) for e in episodes if e.ended_at and e.ended_at >= e.started_at
    ]
    ongoing = sum(1 for e in episodes if e.ended_at is None)
    rated = [e.peak_intensity for e in episodes if e.peak_intensity is not None]
    severe = sum(1 for v in rated if v >= SEVERE_FROM)
    aura = sum(1 for e in episodes if e.had_aura)
    no_symptoms = sum(1 for e in episodes if not e.symptom_links)
    locations = Counter(e.pain_location or "not_recorded" for e in episodes)

    sleep_logs = rec["sleep"]
    sleep_hours = [log.duration_minutes / 60 for log in sleep_logs]
    qualities = [log.quality for log in sleep_logs if log.quality is not None]
    awakenings = [log.awakenings for log in sleep_logs if log.awakenings is not None]

    factor_rows = rec["factors"]
    dose_days = {local(d.taken_at).date() for d in doses}
    unlinked = sum(1 for d in doses if d.episode_id is None or d.episode_id not in number_of)

    data = {
        "language": lang,
        "period": {"period": rng.period, "start": rng.start, "end": rng.end, "days": rng.days, "timezone": rng.tz_name},
        "previous_period": {"start": prev_start, "end": prev_end, "tracked": freq["previous_tracked"]},
        "overview": {
            "total_episodes": total,
            "headache_days": freq["headache_days"],
            "episodes_per_week": freq["episodes_per_week"],
            "rated_episodes": len(rated),
            "average_intensity": inten["average"],
            "highest_intensity": inten["highest"],
            "episodes_with_duration": len(durations),
            "average_duration_minutes": round(_mean(durations)) if durations else None,
            "median_duration_minutes": round(median(durations)) if durations else None,
            "ongoing_episodes": ongoing,
            "previous_total_episodes": freq["previous_total_episodes"] if freq["previous_tracked"] else None,
            "previous_headache_days": freq["previous_headache_days"] if freq["previous_tracked"] else None,
        },
        "episode_ids": [str(e.id) for e in episodes],
        "sleep": {
            "nights": len(sleep_logs),
            "missing_nights": rng.days - len(sleep_logs),
            "average_hours": round(_mean(sleep_hours), 1) if sleep_hours else None,
            "quality_recorded": len(qualities),
            "awakenings_recorded": len(awakenings),
        },
        "factors": {"days": len(factor_rows), "missing_days": rng.days - len(factor_rows)},
        "medication": {"doses": len(doses), "days": len(dose_days), "unlinked": unlinked},
        "observation_ids": insight_ids,
        "data_status": insights["data_status"],
    }

    sections = []

    # --- A. Report information --------------------------------------------------
    latest = _latest_entry(rec["latest"], tz)
    latest_text = L.t(f"info.latest_{latest[0]}", date=L.date(latest[1])) if latest else L.t("info.latest_none")
    rated_text = L.count("episodes", len(rated))
    ended_text = L.count("episodes", len(durations))
    sections.append(section("info", L, [
        facts([
            (L.t("info.generated"), L.datetime(now.astimezone(tz))),
            (L.t("info.period"), L.period(rng.start, rng.end)),
            (L.t("info.days"), L.count("days", rng.days)),
            (L.t("info.timezone"), rng.tz_name),
            (L.t("info.language"), L.t(f"language_names.{lang}")),
            (L.t("info.latest"), latest_text),
        ]),
        table(
            [(L.t("info.col_type"), 3), (L.t("info.col_count"), 2), (L.t("info.col_note"), 5)],
            [
                [L.t("info.type_episodes"), str(total), L.t("info.note_episodes", rated=rated_text, ended=ended_text)],
                [L.t("info.type_sleep"), str(len(sleep_logs)), L.t("info.note_sleep", missing=rng.days - len(sleep_logs), days=rng.days)],
                [L.t("info.type_factors"), str(len(factor_rows)), L.t("info.note_factors", missing=rng.days - len(factor_rows), days=rng.days)],
                [L.t("info.type_medication"), str(len(doses)), L.t("info.note_medication", linked=L.count("doses", len(doses) - unlinked))],
            ],
            title=L.t("info.availability"),
        ),
        paragraph(L.t("info.about"), "muted"),
    ]))

    # --- B. Overview ----------------------------------------------------------------
    ov = data["overview"]
    latest_ep = episodes[-1] if episodes else None
    latest_ep_text = (
        f"{L.datetime(local(latest_ep.started_at))} · "
        + (f"{latest_ep.peak_intensity}/10" if latest_ep.peak_intensity is not None else L.t("not_recorded"))
        if latest_ep
        else L.t("not_available")
    )
    prev_range = L.period(prev_start, prev_end)
    if freq["previous_tracked"]:
        comparison = L.t(
            "overview.comparison",
            days=rng.days,
            range=prev_range,
            prev=L.count("episodes", freq["previous_total_episodes"]),
            prev_days=freq["previous_headache_days"],
            cur=L.count("episodes", total),
            cur_days=freq["headache_days"],
        )
    else:
        comparison = L.t("overview.comparison_none", days=rng.days, range=prev_range)
    sections.append(section("overview", L, [
        facts([
            (L.t("overview.episodes"), str(total)),
            (L.t("overview.headache_days"), str(freq["headache_days"])),
            (L.t("overview.per_week"), L.num(freq["episodes_per_week"])),
            (
                L.t("overview.average_intensity"),
                L.t("overview.intensity_value", value=L.num(ov["average_intensity"]), rated=L.count("rated", len(rated)))
                if rated else L.t("not_available"),
            ),
            (L.t("overview.highest_intensity"), f"{ov['highest_intensity']}/10" if rated else L.t("not_available")),
            (
                L.t("overview.average_duration"),
                L.t("overview.duration_value", value=L.duration(ov["average_duration_minutes"]), count=L.count("episodes", len(durations)))
                if durations else L.t("not_available"),
            ),
            (L.t("overview.median_duration"), L.duration(ov["median_duration_minutes"]) if durations else L.t("not_available")),
            (L.t("overview.ongoing"), str(ongoing)),
            (L.t("overview.latest"), latest_ep_text),
        ]),
        paragraph(comparison),
        paragraph(L.t("overview.headache_days_note"), "muted"),
    ]))

    # --- C. Episode history -----------------------------------------------------------
    history = [paragraph(L.t("history.legend"), "muted")]
    if not episodes:
        history.append(paragraph(L.t("history.empty")))
    for e in episodes:
        start = local(e.started_at)
        if e.ended_at is None:
            end_text, duration_text = L.t("history.ongoing"), L.t("not_available")
        else:
            end = local(e.ended_at)
            end_text = L.time(end) if end.date() == start.date() else L.datetime(end)
            duration_text = L.duration(int((e.ended_at - e.started_at).total_seconds() // 60))
        intensity = (
            f"{e.peak_intensity}/10 · {L.t('bands.' + _band(e.peak_intensity)).split(' (')[0]}"
            if e.peak_intensity is not None
            else L.t("not_recorded")
        )
        symptoms = sorted((link.symptom for link in e.symptom_links), key=lambda s: s.id)
        meds = []
        for d in sorted(e.medication_doses, key=lambda d: d.taken_at):
            amount = f"{L.num(d.dose_amount, 2)} {L.unit(d.dose_unit)}".strip() if d.dose_amount is not None else L.t("not_recorded")
            details = L.t("history.dose", amount=amount, time=L.time(local(d.taken_at)))
            if d.relief_rating is not None:
                details += " · " + L.t("history.relief", value=L.t(f"medication.relief.{d.relief_rating}"))
            # The name (typed by the user, in any language) gets its own row, so its
            # writing direction can't reorder the numbers after it.
            meds += [d.medication_name.strip(), details]
        history.append({
            "type": "episode",
            "number": number_of[e.id],
            "heading": L.t("history.heading", number=number_of[e.id], date=L.day(start.date())),
            "fields": [
                {"label": L.t("history.start"), "value": L.time(start)},
                {"label": L.t("history.end"), "value": end_text},
                {"label": L.t("history.duration"), "value": duration_text},
                {"label": L.t("history.intensity"), "value": intensity},
                {"label": L.t("history.location"), "value": L.t(f"locations.{e.pain_location or 'not_recorded'}")},
                {"label": L.t("history.aura"), "value": L.t("yes" if e.had_aura else "no")},
                {"label": L.t("history.symptoms"), "value": ("، " if L.rtl else ", ").join(L.symptom(s.name) for s in symptoms) or L.t("none_recorded")},
            ] + [
                {"label": L.t("history.medication") if i == 0 else "", "value": line}
                for i, line in enumerate(meds or [L.t("none_recorded")])
            ],
            "notes_label": L.t("history.notes"),
            "notes": e.notes,
        })
    sections.append(section("history", L, history))

    # --- D. Pain characteristics ---------------------------------------------------------
    def share(n: int) -> str:
        return L.t("pain.bar_value", count=n, pct=L.pct(n / total if total else None))

    if episodes:
        band_counts = Counter(_band(v) for v in rated)
        dur_counts = Counter(_duration_band(m) for m in durations)
        pain = [
            bars(L.t("pain.location"), [
                (L.t(f"locations.{k}"), locations[k], share(locations[k]))
                for k in (*PAIN_LOCATIONS, "not_recorded") if locations[k]
            ]),
            bars(L.t("pain.intensity"), [
                (L.t(f"bands.{k}"), n, share(n))
                for k, n in [(b, band_counts[b]) for b in ("none", "mild", "moderate", "severe", "very_severe")] + [("not_rated", total - len(rated))]
                if n
            ]),
            paragraph(L.t("pain.rated_note"), "muted"),
            bars(L.t("pain.duration"), [
                (L.t(f"durations.{k}"), n, share(n))
                for k, n in [(b, dur_counts[b]) for b, _ in DURATION_BANDS] + [("ongoing", ongoing)]
                if n
            ]),
            bars(L.t("pain.time_of_day"), [
                (L.t(f"parts.{k}"), n, share(n)) for k, n in result["time_of_day"].items()
            ]),
        ]
    else:
        pain = [paragraph(L.t("pain.empty"))]
    sections.append(section("pain", L, pain))

    # --- E. Symptoms ------------------------------------------------------------------------
    counts = result["symptoms"]["counts"]
    sym_blocks = []
    if counts:
        columns = [(L.t("symptoms.col_symptom"), 4), (L.t("symptoms.col_count"), 2), (L.t("symptoms.col_share"), 2)]
        if freq["previous_tracked"]:
            columns.append((L.t("symptoms.col_previous", days=rng.days), 2))
        rows = []
        for s in counts:
            row = [L.symptom(s["name"]), str(s["count"]), L.pct(s["count"] / total)]
            if freq["previous_tracked"]:
                row.append(str(s["previous_count"]))
            rows.append(row)
        sym_blocks.append(table(columns, rows))
        if not freq["previous_tracked"]:
            sym_blocks.append(paragraph(L.t("symptoms.no_previous"), "muted"))
        pairs = [p for p in result["symptoms"]["pairs"] if p["count"] >= t.symptom_min_count]
        if pairs:
            joiner = " + "
            sym_blocks.append(table(
                [(L.t("symptoms.col_pair"), 6), (L.t("symptoms.col_count"), 2), (L.t("symptoms.col_share"), 2)],
                [[joiner.join(L.symptom(n) for n in p["names"]), str(p["count"]), L.pct(p["count"] / total)] for p in pairs],
                title=L.t("symptoms.combinations", min=t.symptom_min_count),
            ))
        else:
            sym_blocks.append(paragraph(L.t("symptoms.no_pairs", min=t.symptom_min_count), "muted"))
    else:
        sym_blocks.append(paragraph(L.t("symptoms.none")))
    if episodes:
        sym_blocks.append(paragraph(L.t("symptoms.without", count=no_symptoms, total=L.count("episodes", total)), "muted"))
    sections.append(section("symptoms", L, sym_blocks))

    # --- F. Sleep -----------------------------------------------------------------------------
    if sleep_logs:
        trend = {}
        for log, hours in zip(sleep_logs, sleep_hours):
            trend.setdefault(_bucket(log.sleep_date, rng.interval), []).append(hours)
        sleep_facts = [
            (L.t("sleep.nights"), L.count("nights", len(sleep_logs))),
            (L.t("sleep.missing"), L.count("nights", rng.days - len(sleep_logs))),
            (L.t("sleep.average"), L.hours(_mean(sleep_hours))),
            (L.t("sleep.median"), L.hours(median(sleep_hours))),
            (L.t("sleep.shortest"), L.hours(min(sleep_hours))),
            (L.t("sleep.longest"), L.hours(max(sleep_hours))),
            (
                L.t("sleep.quality"),
                L.t("sleep.quality_value", value=L.num(_mean(qualities)), count=L.count("nights", len(qualities)))
                if qualities else L.t("not_recorded"),
            ),
            (
                L.t("sleep.awakenings"),
                L.t("sleep.awakenings_value", value=L.num(_mean(awakenings)), count=L.count("nights", len(awakenings)))
                if awakenings else L.t("not_recorded"),
            ),
        ]
        sleep_blocks = [
            facts(sleep_facts),
            bars(
                L.t("sleep.trend", interval=L.t(f"sleep.intervals.{rng.interval}")),
                [
                    (L.date(day), round(_mean(h), 2), L.t("sleep.trend_value", hours=L.hours(_mean(h)), count=L.count("nights", len(h))))
                    for day, h in sorted(trend.items())
                ],
            ),
        ]
    else:
        sleep_blocks = [paragraph(L.t("sleep.none"))]
    sleep_blocks.append(subheading(L.t("sleep.comparison_title")))
    sleep_blocks.append(paragraph(L.t("sleep.matching"), "muted"))
    comparison = result["sleep"]["comparison"]
    if comparison:
        sleep_blocks.append(paragraph(L.t(
            "sleep.comparison",
            median=L.hours(comparison["median_hours"]),
            a_hits=comparison["a_headache_days"], a_n=comparison["a_days"], a_rate=L.pct(comparison["a_rate"]),
            b_hits=comparison["b_headache_days"], b_n=comparison["b_days"], b_rate=L.pct(comparison["b_rate"]),
        )))
        listed = any(i.startswith("sleep_") for i in insight_ids)
        sleep_blocks.append(paragraph(L.t("sleep.status_listed" if listed else "sleep.status_unclear"), "muted"))
    else:
        sleep_blocks.append(paragraph(L.t("sleep.comparison_too_few", min=t.min_sleep_nights, have=result["sleep"]["usable_nights"])))
    if sleep_logs:
        sleep_blocks.append(table(
            [(L.t("sleep.col_night"), 3), (L.t("sleep.col_bed"), 2), (L.t("sleep.col_wake"), 2),
             (L.t("sleep.col_length"), 2), (L.t("sleep.col_quality"), 2), (L.t("sleep.col_awakenings"), 2)],
            [
                [
                    L.date(log.sleep_date),
                    L.time(local(log.bedtime)),
                    L.time(local(log.wake_time)),
                    L.duration(log.duration_minutes),
                    L.t(f"sleep.qualities.{log.quality}") if log.quality is not None else L.t("dash"),
                    str(log.awakenings) if log.awakenings is not None else L.t("dash"),
                ]
                for log in sleep_logs
            ],
            title=L.t("sleep.records"),
        ))
        sleep_blocks.append(paragraph(L.t("factors.records_legend"), "muted"))
    sections.append(section("sleep", L, sleep_blocks))

    # --- G. Daily factors -------------------------------------------------------------------------
    by_factor = result["factors"]["by_factor"]
    if factor_rows:
        rows = []
        for name in NUMERIC_FACTORS + BOOLEAN_FACTORS:
            values = [getattr(r, name) for r in factor_rows if getattr(r, name) is not None]
            if name in NUMERIC_FACTORS:
                summary = L.t(
                    "factors.numeric_values",
                    avg=L.num(_mean(values)), median=L.num(median(float(v) for v in values)),
                    min=L.num(min(values)), max=L.num(max(values)),
                ) if values else L.t("dash")
            else:
                summary = L.t(
                    "factors.boolean_values",
                    yes=L.count("days", sum(1 for v in values if v)), no=L.count("days", sum(1 for v in values if not v)),
                ) if values else L.t("dash")
            c = by_factor[name]["comparison"]
            if c:
                key = "factors.numeric_groups" if name in NUMERIC_FACTORS else "factors.boolean_groups"
                groups = L.t(
                    key, median=L.num(by_factor[name].get("median")),
                    a_hits=c["a_headache_days"], a_n=c["a_days"], a_rate=L.pct(c["a_rate"]),
                    b_hits=c["b_headache_days"], b_n=c["b_days"], b_rate=L.pct(c["b_rate"]),
                )
                if c["a_avg_intensity"] is not None:
                    groups += "; " + L.t("factors.intensity_groups", a_avg=L.num(c["a_avg_intensity"]), b_avg=L.num(c["b_avg_intensity"]))
                listed = any(i.startswith(f"factor_{name}_") for i in insight_ids)
                status = L.t("factors.result_listed" if listed else "factors.result_unclear")
            else:
                groups, status = L.t("dash"), L.t("factors.result_too_few")
            rows.append([L.t(f"factors.names.{name}"), str(len(values)), summary, groups, status])
        factor_blocks = [
            paragraph(L.t("factors.logged", days=len(factor_rows), total=rng.days)),
            table(
                [(L.t("factors.col_factor"), 3), (L.t("factors.col_days"), 1.6), (L.t("factors.col_values"), 4),
                 (L.t("factors.col_comparison"), 5), (L.t("factors.col_result"), 2.6)],
                rows,
            ),
            paragraph(L.t("factors.rule"), "muted"),
        ]
        recorded = [n for n in NUMERIC_FACTORS + BOOLEAN_FACTORS if any(getattr(r, n) is not None for r in factor_rows)]

        def cell(r, n):
            v = getattr(r, n)
            if v is None:
                return L.t("dash")
            return L.t("yes" if v else "no") if n in BOOLEAN_FACTORS else L.num(v)

        factor_blocks.append(table(
            [(L.t("factors.col_date"), 3)] + [(L.t(f"factors.names.{n}"), 2) for n in recorded],
            [[L.date(r.log_date)] + [cell(r, n) for n in recorded] for r in factor_rows],
            title=L.t("factors.records"),
        ))
        factor_blocks.append(paragraph(L.t("factors.records_legend"), "muted"))
        notes = [r for r in factor_rows if r.notes]
        for r in notes:
            factor_blocks.append(paragraph(f"{L.date(r.log_date)}:", "label"))
            factor_blocks.append(paragraph(r.notes, user_text=True))
    else:
        factor_blocks = [paragraph(L.t("factors.none"))]
    sections.append(section("factors", L, factor_blocks))

    # --- H. Medication ---------------------------------------------------------------------------------
    if doses:
        groups: dict[str, list[MedicationDose]] = {}
        for d in doses:
            groups.setdefault(d.medication_name.strip().casefold(), []).append(d)
        summary_rows = []
        for items in sorted(groups.values(), key=lambda g: (-len(g), g[0].medication_name.casefold())):
            summary_rows.append([
                items[0].medication_name.strip(),
                str(len(items)),
                str(len({local(d.taken_at).date() for d in items})),
                str(sum(1 for d in items if d.episode_id in number_of)),
                L.date(local(items[0].taken_at).date()),
                L.date(local(items[-1].taken_at).date()),
            ])
        dose_rows = []
        for d in doses:
            amount = f"{L.num(d.dose_amount, 2)} {L.unit(d.dose_unit)}".strip() if d.dose_amount is not None else L.t("not_recorded")
            dose_rows.append([
                L.datetime(local(d.taken_at)),
                d.medication_name.strip(),
                amount,
                L.t("medication.episode_ref", number=number_of[d.episode_id]) if d.episode_id in number_of else L.t("medication.not_linked"),
                L.t(f"medication.relief.{d.relief_rating}") if d.relief_rating is not None else L.t("not_recorded"),
            ])
        med_blocks = [
            table(
                [(L.t("medication.col_name"), 4), (L.t("medication.col_doses"), 1.5), (L.t("medication.col_days"), 1.5),
                 (L.t("medication.col_linked"), 2), (L.t("medication.col_first"), 2.5), (L.t("medication.col_last"), 2.5)],
                summary_rows,
                title=L.t("medication.summary"),
            ),
            table(
                [(L.t("medication.col_when"), 3.4), (L.t("medication.col_name"), 3), (L.t("medication.col_amount"), 2),
                 (L.t("medication.col_episode"), 2), (L.t("medication.col_relief"), 2.4)],
                dose_rows,
                title=L.t("medication.doses"),
            ),
            paragraph(L.t("medication.note"), "muted"),
        ]
    else:
        med_blocks = [paragraph(L.t("medication.none"))]
    sections.append(section("medication", L, med_blocks))

    # --- I. Key observations -------------------------------------------------------------------------------
    obs_blocks = [paragraph(L.t("observations.intro"), "muted")]
    if total < t.min_episodes:
        obs_blocks.append(paragraph(L.t("observations.insufficient", min=t.min_episodes, have=total)))
    elif not insights["insights"]:
        obs_blocks.append(paragraph(L.t("observations.none")))
    obs_blocks += [_observation_block(i, L) for i in insights["insights"]]
    sections.append(section("observations", L, obs_blocks))

    # --- J. Summary for the doctor ---------------------------------------------------------------------------
    patterns = [i for i in insights["insights"] if i["category"] != "medication"]
    summary = []
    if total:
        summary.append(L.t(
            "summary.period", start=L.date(rng.start), end=L.date(rng.end), days=L.count("days", rng.days),
            episodes=L.count("episodes", total), headache_days=freq["headache_days"], per_week=L.num(freq["episodes_per_week"]),
        ))
        if freq["previous_tracked"]:
            summary.append(L.t("summary.previous", days=rng.days, prev=L.count("episodes", freq["previous_total_episodes"])))
        if rated:
            summary.append(L.t("summary.intensity", avg=L.num(inten["average"]), max=inten["highest"], rated=L.count("rated", len(rated))))
        if durations:
            summary.append(L.t(
                "summary.duration", median=L.duration(round(median(durations))), avg=L.duration(round(_mean(durations))),
                count=L.count("episodes", len(durations)),
            ))
        top_part, top_n = max(result["time_of_day"].items(), key=lambda kv: kv[1])
        if top_n and sorted(result["time_of_day"].values())[-2] < top_n:
            summary.append(L.t("summary.timing", part=L.t(f"part_names.{top_part}"), count=top_n, total=total))
        recorded_locations = {k: n for k, n in locations.items() if k != "not_recorded"}
        if recorded_locations:
            loc, n = max(recorded_locations.items(), key=lambda kv: kv[1])
            location = L.t(f"locations.{loc}")
            summary.append(L.t(
                "summary.location", location=location if L.rtl else location.lower(), count=n, total=sum(recorded_locations.values())
            ))
        if counts:
            summary.append(L.t("summary.symptom", symptom=L.symptom(counts[0]["name"]), count=counts[0]["count"], total=total))
        if aura:
            summary.append(L.t("summary.aura", count=aura, total=total))
    else:
        summary.append(L.t("summary.none", start=L.date(rng.start), end=L.date(rng.end), days=L.count("days", rng.days)))
    if doses:
        summary.append(L.t("summary.medication", doses=L.count("doses", len(doses)), days=L.count("days", len(dose_days))))
    if patterns:
        top = patterns[0]
        summary.append(L.t(
            "summary.observation", level=L.t(f"observations.levels.{top['evidence_level']}"), text=_observation_text(top, L)[1]
        ))
    sections.append(section("summary", L, [paragraph(s) for s in summary]))

    # --- K. Questions ------------------------------------------------------------------------------------------
    questions = []
    if total:
        questions.append(L.t(
            "questions.frequency", episodes=L.count("episodes", total), headache_days=freq["headache_days"], days=L.count("days", rng.days)
        ))
    change = next((i for i in insight_ids if i in ("frequency_increase", "frequency_decrease")), None)
    if change:
        questions.append(L.t(
            "questions.change", cur=L.count("episodes", total),
            prev=L.count("episodes", freq["previous_total_episodes"]), days=rng.days,
        ))
    if severe:
        questions.append(L.t("questions.intensity", count=severe, min=SEVERE_FROM))
    if len(dose_days) >= 2:
        questions.append(L.t("questions.medication_days", days=L.count("days", len(dose_days)), period_days=L.count("days", rng.days)))
    if aura:
        questions.append(L.t("questions.aura", count=L.count("episodes", aura)))
    for ins in patterns[:2]:
        questions.append(L.t("questions.observation", text=_observation_text(ins, L)[1]))
    if ongoing:
        questions.append(L.t("questions.ongoing", count=L.count("episodes", ongoing)))
    if len(sleep_logs) < t.min_sleep_nights:
        questions.append(L.t("questions.missing_sleep"))
    if len(factor_rows) < t.min_factor_days:
        questions.append(L.t("questions.missing_factors"))
    questions.append(L.t("questions.general"))
    sections.append(section("questions", L, [paragraph(L.t("questions.intro"), "muted"), bullet_list(questions)]))

    # --- L. Missing information and limitations ------------------------------------------------------------------
    limits = [L.t("limitations.self_reported")]
    if total < t.min_episodes:
        limits.append(L.t("limitations.insufficient", min=t.min_episodes))
    if total - len(rated):
        limits.append(L.t("limitations.unrated", count=L.count("episodes", total - len(rated))))
    if ongoing:
        limits.append(L.t("limitations.ongoing", count=L.count("episodes", ongoing)))
    if episodes and no_symptoms:
        limits.append(L.t("limitations.no_symptoms", count=L.count("episodes", no_symptoms)))
    if rng.days - len(sleep_logs):
        limits.append(L.t("limitations.sleep_missing", missing=rng.days - len(sleep_logs), days=rng.days))
    if "sleep_variation" in gap_codes:
        limits.append(L.t("limitations.sleep_variation"))
    if rng.days - len(factor_rows):
        limits.append(L.t("limitations.factors_missing", missing=rng.days - len(factor_rows), days=rng.days))
    if not freq["previous_tracked"]:
        limits.append(L.t("limitations.previous", days=rng.days))
    if unlinked:
        limits.append(L.t("limitations.medication"))
    limits.append(L.t("limitations.statistics"))
    limits.append(L.t("limitations.timezone", timezone=rng.tz_name))
    sections.append(section("limitations", L, [bullet_list(limits)]))

    # --- M. Disclaimer ----------------------------------------------------------------------------------------------
    sections.append(section("disclaimer", L, [{"type": "callout", "text": DISCLAIMER_AR if L.rtl else DISCLAIMER_EN}]))

    return {
        "language": lang,
        "direction": L.direction,
        "title": L.t("title"),
        "subtitle": L.t("subtitle"),
        "period_label": L.period(rng.start, rng.end),
        "generated_at": now,
        "generated_label": L.date(now.astimezone(tz).date()),
        "data": data,
        "sections": sections,
    }
