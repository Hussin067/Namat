"""Insights: deterministic pattern analysis of one user's own records.

Two separate steps:
  1. analyze()            -> numbers only (counts, rates, averages, sample sizes)
  2. generate_insights()  -> turns those numbers into a few careful, structured
                             observations, or explains which data is missing

No AI service, no machine learning: plain descriptive statistics with fixed,
documented thresholds (THRESHOLDS below). Results describe
associations in the user's own records. They never state a cause, a
diagnosis, or anything about treatment or medication effectiveness.

Shared rules with /analytics/dashboard (app/services/analytics.py):
- dates use the user's time zone (UTC fallback) and an inclusive date range;
- an episode belongs to a range when it STARTS on one of its dates;
- a "headache day" is any local date an episode touches, from its start date
  to its end date (an ongoing episode counts only its start date).
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from itertools import combinations
from math import comb
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DailyFactor, EpisodeSymptom, HeadacheEpisode, MedicationDose, SleepLog, Symptom, User
from app.services.analytics import DateRange


@dataclass(frozen=True)
class Thresholds:
    """Every limit the analysis uses, in one place."""

    min_episodes: int = 3  # below this, no pattern analysis at all
    min_sleep_nights: int = 7  # usable sleep records needed for a sleep comparison
    min_factor_days: int = 7  # days with a value recorded, per factor
    min_group_size: int = 3  # each side of any comparison
    observed_min_group: int = 5  # each side, for "observed" rather than "limited"
    observed_min_total: int = 14  # total days compared, for "observed"
    min_rate_difference: float = 0.15  # headache-day rate gap (15 percentage points)
    min_intensity_difference: float = 1.0  # points on the 0–10 scale
    min_rated_per_group: int = 2  # rated episodes per side for an intensity comparison
    # Chance filter for sleep and daily-factor comparisons (Fisher's exact test for
    # headache-day rates, a permutation test for average intensity). Many factors
    # are compared at once, so a difference by chance alone is likely without it.
    max_p_value_shown: float = 0.10  # weaker differences are not reported at all
    max_p_value_observed: float = 0.05  # needed (with enough days) for "observed"
    permutation_rounds: int = 4000  # fixed seed below, so results are repeatable
    frequency_min_change: int = 2  # episodes, and ...
    frequency_min_relative_change: float = 0.25  # ... 25% versus the previous period
    observed_min_episodes: int = 10  # episodes (both periods together) for "observed" trends
    time_of_day_min_episodes: int = 5
    time_of_day_min_share: float = 0.4
    symptom_min_count: int = 2
    symptom_min_share: float = 0.3  # of episodes in the period
    tracking_grace_days: int = 7  # first record may start this long after the previous period began


THRESHOLDS = Thresholds()

# Local start time → part of the day (hours, 24 h clock).
TIME_OF_DAY = (("night", 0, 5), ("morning", 5, 12), ("afternoon", 12, 17), ("evening", 17, 21), ("night", 21, 24))

# The daily_factors columns and how they are compared.
NUMERIC_FACTORS = ("stress_level", "caffeine_mg", "water_ml", "exercise_minutes")
BOOLEAN_FACTORS = ("skipped_meal", "menstruating")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _round(value: float | None, digits: int = 1) -> float | None:
    return None if value is None else round(float(value), digits)


def _mean(values) -> float | None:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _rate(hits: int, total: int) -> float | None:
    return hits / total if total else None


def fisher_exact_p(a_hits: int, a_n: int, b_hits: int, b_n: int) -> float:
    """Two-sided Fisher's exact test for two proportions (exact for small samples)."""
    hits, total = a_hits + b_hits, a_n + b_n

    def prob(x: int) -> float:
        return comb(hits, x) * comb(total - hits, a_n - x) / comb(total, a_n)

    observed = prob(a_hits)
    possible = range(max(0, hits - b_n), min(hits, a_n) + 1)
    return min(1.0, sum(p for p in map(prob, possible) if p <= observed * (1 + 1e-9)))


def permutation_p(a: list[float], b: list[float], rounds: int, seed: int = 20260601) -> float:
    """Two-sided permutation test for a difference in means; seeded, so repeatable."""
    observed = abs(sum(a) / len(a) - sum(b) / len(b))
    pooled, n, rnd, extreme = list(a) + list(b), len(a), random.Random(seed), 0
    for _ in range(rounds):
        rnd.shuffle(pooled)
        left, right = pooled[:n], pooled[n:]
        if abs(sum(left) / n - sum(right) / len(right)) >= observed - 1e-12:
            extreme += 1
    return (extreme + 1) / (rounds + 1)


def _part_of_day(hour: int) -> str:
    return next(name for name, lo, hi in TIME_OF_DAY if lo <= hour < hi)


def _intensity_band(value: int) -> str:
    # Same bands as the frontend's intensity labels.
    if value == 0:
        return "none"
    if value <= 3:
        return "mild"
    if value <= 6:
        return "moderate"
    if value <= 8:
        return "severe"
    return "very_severe"


@dataclass
class _Episode:
    id: object
    start_local: datetime
    end_local: datetime | None
    intensity: int | None

    @property
    def start_date(self) -> date:
        return self.start_local.date()

    def touched_days(self) -> list[date]:
        last = (self.end_local or self.start_local).date()
        days, day = [], self.start_date
        while day <= last and len(days) < 366:
            days.append(day)
            day += timedelta(days=1)
        return days


def _headache_days(episodes: list[_Episode], start: date, end: date) -> set[date]:
    return {d for e in episodes for d in e.touched_days() if start <= d <= end}


# ---------------------------------------------------------------------------
# 1. Data collection (only the token's user; only the columns needed)
# ---------------------------------------------------------------------------

def _load_episodes(db: Session, user: User, lower: datetime, upper: datetime, tz) -> list[_Episode]:
    rows = db.execute(
        select(HeadacheEpisode.id, HeadacheEpisode.started_at, HeadacheEpisode.ended_at, HeadacheEpisode.peak_intensity)
        .where(HeadacheEpisode.user_id == user.id, HeadacheEpisode.started_at >= lower, HeadacheEpisode.started_at < upper)
        .order_by(HeadacheEpisode.started_at)
    ).all()
    return [
        _Episode(r[0], r[1].astimezone(tz), r[2].astimezone(tz) if r[2] else None, r[3])
        for r in rows
    ]


def _load_symptoms(db: Session, episode_ids: list) -> dict[object, set[tuple[int, str]]]:
    if not episode_ids:
        return {}
    rows = db.execute(
        select(EpisodeSymptom.episode_id, Symptom.id, Symptom.name)
        .join(Symptom, Symptom.id == EpisodeSymptom.symptom_id)
        .where(EpisodeSymptom.episode_id.in_(episode_ids))
    ).all()
    by_episode: dict[object, set[tuple[int, str]]] = {}
    for episode_id, symptom_id, name in rows:
        by_episode.setdefault(episode_id, set()).add((symptom_id, name))  # a set: never double counted
    return by_episode


# ---------------------------------------------------------------------------
# 2. Analysis
# ---------------------------------------------------------------------------

def _previous_range(rng: DateRange) -> tuple[date, date]:
    """The equivalent period immediately before: same number of days."""
    end = rng.start - timedelta(days=1)
    return end - timedelta(days=rng.days - 1), end


def _compare_groups(group_a: list[tuple[bool, list[int]]], group_b: list[tuple[bool, list[int]]], t: Thresholds) -> dict | None:
    """Each item: (was a headache day, intensities of episodes that started that day).

    Returns rates, intensity averages and sample sizes, or None when either
    side is smaller than the minimum group size.
    """
    if len(group_a) < t.min_group_size or len(group_b) < t.min_group_size:
        return None
    a_hits, b_hits = sum(1 for h, _ in group_a if h), sum(1 for h, _ in group_b if h)
    a_int = [i for _, ints in group_a for i in ints]
    b_int = [i for _, ints in group_b for i in ints]
    comparable_intensity = len(a_int) >= t.min_rated_per_group and len(b_int) >= t.min_rated_per_group
    return {
        "rate_p_value": round(fisher_exact_p(a_hits, len(group_a), b_hits, len(group_b)), 4),
        "intensity_p_value": round(permutation_p(a_int, b_int, t.permutation_rounds), 4) if comparable_intensity else None,
        "a_days": len(group_a),
        "b_days": len(group_b),
        "a_headache_days": a_hits,
        "b_headache_days": b_hits,
        "a_rate": _round(_rate(a_hits, len(group_a)), 2),
        "b_rate": _round(_rate(b_hits, len(group_b)), 2),
        "a_avg_intensity": _round(_mean(a_int)) if comparable_intensity else None,
        "b_avg_intensity": _round(_mean(b_int)) if comparable_intensity else None,
        "a_rated": len(a_int),
        "b_rated": len(b_int),
    }


def analyze(db: Session, user: User, rng: DateRange, t: Thresholds = THRESHOLDS) -> dict:
    tz = rng.tz
    lower, upper = rng.utc_bounds()
    prev_start, prev_end = _previous_range(rng)
    prev_rng = DateRange(rng.period, prev_start, prev_end, rng.interval, rng.tz_name, tz)
    prev_lower, _ = prev_rng.utc_bounds()

    # One query covers both periods.
    all_eps = _load_episodes(db, user, prev_lower, upper, tz)
    current = [e for e in all_eps if e.start_local >= lower.astimezone(tz)]
    previous = [e for e in all_eps if e.start_local < lower.astimezone(tz)]
    symptoms = _load_symptoms(db, [e.id for e in all_eps])

    # Was the user already tracking during the previous period? Otherwise a
    # "change" would only reflect when they started using Namat.
    first_record = db.scalar(select(func.min(HeadacheEpisode.started_at)).where(HeadacheEpisode.user_id == user.id))
    previous_tracked = bool(first_record) and first_record.astimezone(tz).date() <= prev_start + timedelta(days=t.tracking_grace_days)

    # --- Frequency -----------------------------------------------------------
    headache_days = _headache_days(current, rng.start, rng.end)
    weeks = rng.days / 7
    frequency = {
        "total_episodes": len(current),
        "headache_days": len(headache_days),
        "episodes_per_week": _round(len(current) / weeks) if weeks else None,
        "previous_total_episodes": len(previous),
        "previous_headache_days": len(_headache_days(previous, prev_start, prev_end)),
        "previous_tracked": previous_tracked,
    }

    # --- Intensity -------------------------------------------------------------
    rated = [e.intensity for e in current if e.intensity is not None]  # 0 is a real rating
    prev_rated = [e.intensity for e in previous if e.intensity is not None]
    intensity = {
        "rated_episodes": len(rated),
        "average": _round(_mean(rated)),
        "highest": max(rated) if rated else None,
        "distribution": dict(Counter(_intensity_band(v) for v in rated)),
        "previous_rated_episodes": len(prev_rated),
        "previous_average": _round(_mean(prev_rated)),
    }

    # --- Time of day (local start time) ---------------------------------------
    time_of_day = Counter(_part_of_day(e.start_local.hour) for e in current)

    # --- Symptoms --------------------------------------------------------------
    sym_counts, prev_sym_counts, pair_counts, names = Counter(), Counter(), Counter(), {}
    for e in current:
        ids = sorted(sid for sid, _ in symptoms.get(e.id, ()))
        sym_counts.update(ids)
        pair_counts.update(combinations(ids, 2))
        names.update({sid: name for sid, name in symptoms.get(e.id, ())})
    for e in previous:
        for sid, name in symptoms.get(e.id, ()):
            prev_sym_counts[sid] += 1
            names.setdefault(sid, name)
    symptom_analysis = {
        "episodes_with_symptoms": sum(1 for e in current if symptoms.get(e.id)),
        "counts": [
            {"id": sid, "name": names[sid], "count": n, "previous_count": prev_sym_counts.get(sid, 0)}
            for sid, n in sorted(sym_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        "pairs": [
            {"ids": list(pair), "names": [names[pair[0]], names[pair[1]]], "count": n}
            for pair, n in sorted(pair_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
    }

    # Per local day: was it a headache day, and which intensities started that day.
    intensities_by_day: dict[date, list[int]] = {}
    for e in current:
        if e.intensity is not None:
            intensities_by_day.setdefault(e.start_date, []).append(e.intensity)

    def day_outcome(day: date) -> tuple[bool, list[int]]:
        return day in headache_days, intensities_by_day.get(day, [])

    # --- Sleep: night N (sleep_date) is matched to the following local day N+1 ---
    sleep_rows = db.execute(
        select(SleepLog.sleep_date, SleepLog.bedtime, SleepLog.wake_time).where(
            SleepLog.user_id == user.id,
            SleepLog.sleep_date >= rng.start - timedelta(days=1),
            SleepLog.sleep_date <= rng.end - timedelta(days=1),
        )
    ).all()
    nights = [
        (night + timedelta(days=1), (wake - bed).total_seconds() / 3600)
        for night, bed, wake in sleep_rows
        if wake is not None and bed is not None and wake > bed
    ]
    sleep = {"usable_nights": len(nights), "average_hours": _round(_mean(h for _, h in nights)), "comparison": None}
    if len(nights) >= t.min_sleep_nights:
        cut = median(h for _, h in nights)
        shorter = [day_outcome(day) for day, h in nights if h < cut]
        longer = [day_outcome(day) for day, h in nights if h >= cut]
        comparison = _compare_groups(shorter, longer, t)
        if comparison:
            sleep["comparison"] = comparison | {"median_hours": _round(cut)}

    # --- Daily factors: only days where that factor has a value -----------------
    factor_rows = db.execute(
        select(DailyFactor).where(
            DailyFactor.user_id == user.id, DailyFactor.log_date >= rng.start, DailyFactor.log_date <= rng.end
        )
    ).scalars().all()
    factors = {"logged_days": len(factor_rows), "by_factor": {}}
    for name in NUMERIC_FACTORS + BOOLEAN_FACTORS:
        recorded = [(row.log_date, getattr(row, name)) for row in factor_rows if getattr(row, name) is not None]
        entry = {"recorded_days": len(recorded), "kind": "numeric" if name in NUMERIC_FACTORS else "boolean", "comparison": None}
        if len(recorded) >= t.min_factor_days:
            if name in NUMERIC_FACTORS:
                cut = median(float(v) for _, v in recorded)
                high = [day_outcome(d) for d, v in recorded if float(v) > cut]  # zero is a real value
                low = [day_outcome(d) for d, v in recorded if float(v) <= cut]
                entry["median"] = _round(cut)
            else:
                high = [day_outcome(d) for d, v in recorded if v is True]  # recorded as present
                low = [day_outcome(d) for d, v in recorded if v is False]  # recorded as absent
            entry["comparison"] = _compare_groups(high, low, t)
        factors["by_factor"][name] = entry

    # --- Medication (descriptive only) ----------------------------------------
    doses = db.execute(
        select(MedicationDose.medication_name, MedicationDose.episode_id).where(
            MedicationDose.user_id == user.id, MedicationDose.taken_at >= lower, MedicationDose.taken_at < upper
        )
    ).all()
    current_ids = {e.id for e in current}
    name_counts = Counter(n.strip().casefold() for n, _ in doses)
    display = {}
    for n, _ in doses:
        display.setdefault(n.strip().casefold(), n.strip())
    top = name_counts.most_common(1)
    medication = {
        "doses": len(doses),
        "top_medication": display[top[0][0]] if top else None,
        "top_medication_doses": top[0][1] if top else 0,
        "episodes_with_medication": len({ep for _, ep in doses if ep in current_ids}),
    }

    return {
        "range": rng,
        "previous_range": (prev_start, prev_end),
        "frequency": frequency,
        "intensity": intensity,
        "time_of_day": {k: time_of_day.get(k, 0) for k in ("morning", "afternoon", "evening", "night")},
        "symptoms": symptom_analysis,
        "sleep": sleep,
        "factors": factors,
        "medication": medication,
    }


# ---------------------------------------------------------------------------
# 3. Insight generation
# ---------------------------------------------------------------------------

FACTOR_LABELS = {
    "stress_level": "stress level",
    "caffeine_mg": "caffeine",
    "water_ml": "water intake",
    "exercise_minutes": "exercise",
    "skipped_meal": "a skipped meal",
    "menstruating": "menstruation",
}

LEVEL_WEIGHT = {"observed": 2, "limited": 1}


def _pct(rate: float) -> int:
    return round(rate * 100)


def _comparison_level(c: dict, p_value: float, t: Thresholds) -> str:
    big_enough = (
        c["a_days"] >= t.observed_min_group
        and c["b_days"] >= t.observed_min_group
        and c["a_days"] + c["b_days"] >= t.observed_min_total
    )
    return "observed" if big_enough and p_value <= t.max_p_value_observed else "limited"


def _association(c: dict, t: Thresholds) -> tuple[str, str, float] | None:
    """('rate'|'intensity', 'higher'|'lower', p-value) for group A versus B.

    None unless the difference is both large enough to matter AND unlikely to be
    chance alone (p <= max_p_value_shown). This is a screening rule for a
    personal tracker, not a clinical test.
    """
    if abs(c["a_rate"] - c["b_rate"]) >= t.min_rate_difference and c["rate_p_value"] <= t.max_p_value_shown:
        return "rate", "higher" if c["a_rate"] > c["b_rate"] else "lower", c["rate_p_value"]
    if (
        c["a_avg_intensity"] is not None
        and abs(c["a_avg_intensity"] - c["b_avg_intensity"]) >= t.min_intensity_difference
        and c["intensity_p_value"] <= t.max_p_value_shown
    ):
        return "intensity", "higher" if c["a_avg_intensity"] > c["b_avg_intensity"] else "lower", c["intensity_p_value"]
    return None


def generate_insights(result: dict, t: Thresholds = THRESHOLDS) -> dict:
    rng: DateRange = result["range"]
    prev_start, prev_end = result["previous_range"]
    freq, inten = result["frequency"], result["intensity"]
    period = {"start": rng.start, "end": rng.end}
    insights: list[dict] = []
    gaps: list[dict] = []

    def add(id_, category, title, description, evidence, sample_size, level, effect=0.0, comparison=None):
        insights.append(
            {
                "id": id_,
                "category": category,
                "title": title,
                "description": description,
                "evidence": evidence,
                "sample_size": sample_size,
                "evidence_level": level,
                "date_range": period,
                "comparison": comparison,
                "_score": LEVEL_WEIGHT[level] * 10 + effect,
            }
        )

    enough_episodes = freq["total_episodes"] >= t.min_episodes
    if not enough_episodes:
        gaps.append({"code": "episodes", "needed": t.min_episodes, "have": freq["total_episodes"]})

    if enough_episodes:
        # --- Frequency versus the previous equivalent period ---------------------
        if not freq["previous_tracked"]:
            gaps.append({"code": "previous_period", "needed": None, "have": None})
        else:
            cur, prev = freq["total_episodes"], freq["previous_total_episodes"]
            diff = cur - prev
            relative = diff / prev if prev else None
            level = "observed" if cur + prev >= t.observed_min_episodes else "limited"
            comparison = {"previous_start": prev_start, "previous_end": prev_end, "current": cur, "previous": prev}
            if abs(diff) >= t.frequency_min_change and (relative is None or abs(relative) >= t.frequency_min_relative_change):
                direction = "increase" if diff > 0 else "decrease"
                add(
                    f"frequency_{direction}",
                    "frequency",
                    "More episodes than the previous period" if diff > 0 else "Fewer episodes than the previous period",
                    f"Your records show {cur} episodes in this period, compared with {prev} in the {rng.days} days before.",
                    {"current": cur, "previous": prev, "days": rng.days},
                    cur + prev,
                    level,
                    effect=min(abs(diff) / max(prev, 1), 2),
                    comparison=comparison,
                )
            else:
                add(
                    "frequency_stable",
                    "frequency",
                    "Similar frequency to the previous period",
                    f"Your records show {cur} episodes in this period and {prev} in the {rng.days} days before.",
                    {"current": cur, "previous": prev, "days": rng.days},
                    cur + prev,
                    level,
                    comparison=comparison,
                )

            # --- Intensity versus the previous period ----------------------------
            if inten["rated_episodes"] >= t.min_episodes and inten["previous_rated_episodes"] >= t.min_episodes:
                change = inten["average"] - inten["previous_average"]
                if abs(change) >= t.min_intensity_difference:
                    higher = change > 0
                    add(
                        "intensity_higher" if higher else "intensity_lower",
                        "intensity",
                        "Higher average intensity than before" if higher else "Lower average intensity than before",
                        f"The average peak intensity you recorded was {inten['average']}/10 in this period, "
                        f"compared with {inten['previous_average']}/10 in the {rng.days} days before.",
                        {"current": inten["average"], "previous": inten["previous_average"], "days": rng.days},
                        inten["rated_episodes"] + inten["previous_rated_episodes"],
                        "observed" if inten["rated_episodes"] + inten["previous_rated_episodes"] >= t.observed_min_episodes else "limited",
                        effect=abs(change),
                        comparison={"previous_start": prev_start, "previous_end": prev_end},
                    )

        # --- Time of day ---------------------------------------------------------
        tod, total = result["time_of_day"], freq["total_episodes"]
        if total >= t.time_of_day_min_episodes:
            ranked = sorted(tod.items(), key=lambda kv: -kv[1])
            (top, top_n), (_, second_n) = ranked[0], ranked[1]
            if top_n / total >= t.time_of_day_min_share and top_n > second_n:
                add(
                    f"time_of_day_{top}",
                    "timing",
                    f"Most episodes started in the {top}",
                    f"{top_n} of your {total} episodes in this period started in the {top}.",
                    {"part_of_day": top, "count": top_n, "total": total, "counts": tod},
                    total,
                    "observed" if total >= t.observed_min_episodes else "limited",
                    effect=top_n / total,
                )

        # --- Symptoms ------------------------------------------------------------
        counts = result["symptoms"]["counts"]
        pairs = result["symptoms"]["pairs"]
        qualifies = lambda n: n >= t.symptom_min_count and n / total >= t.symptom_min_share  # noqa: E731
        pair_ok = bool(pairs) and qualifies(pairs[0]["count"])
        # If the top symptom only ever appears as part of the top pair, the pair card
        # already says everything: skip the single-symptom card to avoid repeating it.
        pair_covers_top = (
            pair_ok and bool(counts) and counts[0]["id"] in pairs[0]["ids"] and pairs[0]["count"] == counts[0]["count"]
        )
        if counts and qualifies(counts[0]["count"]) and not pair_covers_top:
            s = counts[0]
            add(
                "symptom_common",
                "symptoms",
                "Your most frequently recorded symptom",
                f"{s['name']} was recorded in {s['count']} of your {total} episodes in this period.",
                {"symptom_id": s["id"], "symptom": s["name"], "count": s["count"], "total": total, "previous_count": s["previous_count"]},
                total,
                "observed" if total >= t.observed_min_episodes else "limited",
                effect=s["count"] / total,
            )
        if pair_ok:
            p = pairs[0]
            add(
                "symptom_pair",
                "symptoms",
                "Symptoms often recorded together",
                f"{p['names'][0]} and {p['names'][1]} were recorded together in {p['count']} of your {total} episodes.",
                {"symptom_ids": p["ids"], "symptoms": p["names"], "count": p["count"], "total": total},
                total,
                "observed" if total >= t.observed_min_episodes else "limited",
                effect=p["count"] / total * 0.9,  # slightly below the single-symptom card
            )

    # --- Sleep ---------------------------------------------------------------------
    sleep = result["sleep"]
    if sleep["usable_nights"] < t.min_sleep_nights:
        gaps.append({"code": "sleep", "needed": t.min_sleep_nights, "have": sleep["usable_nights"]})
    elif sleep["comparison"] is None:
        gaps.append({"code": "sleep_variation", "needed": t.min_group_size, "have": None})
    elif enough_episodes:
        c = sleep["comparison"]
        found = _association(c, t)
        if found:
            kind, direction, p_value = found
            evidence = {
                "median_hours": c["median_hours"],
                "shorter_nights": c["a_days"],
                "other_nights": c["b_days"],
                "shorter_headache_rate": c["a_rate"],
                "other_headache_rate": c["b_rate"],
                "shorter_avg_intensity": c["a_avg_intensity"],
                "other_avg_intensity": c["b_avg_intensity"],
            }
            if kind == "rate":
                description = (
                    f"In your records, {_pct(c['a_rate'])}% of days after shorter sleep (under {c['median_hours']} h) "
                    f"were headache days, compared with {_pct(c['b_rate'])}% after longer sleep."
                )
                effect = abs(c["a_rate"] - c["b_rate"]) * 5
            else:
                description = (
                    f"On headache days after shorter sleep (under {c['median_hours']} h), the average intensity you recorded "
                    f"was {c['a_avg_intensity']}/10, compared with {c['b_avg_intensity']}/10 after longer sleep."
                )
                effect = abs(c["a_avg_intensity"] - c["b_avg_intensity"])
            add(
                f"sleep_{kind}_{direction}",
                "sleep",
                "A sleep pattern in your records",
                description,
                evidence | {"comparison_type": kind, "direction": direction, "p_value": p_value},
                c["a_days"] + c["b_days"],
                _comparison_level(c, p_value, t),
                effect=effect,
            )

    # --- Daily factors -------------------------------------------------------------
    by_factor = result["factors"]["by_factor"]
    if all(f["recorded_days"] < t.min_factor_days for f in by_factor.values()):
        gaps.append(
            {"code": "daily_factors", "needed": t.min_factor_days, "have": max(f["recorded_days"] for f in by_factor.values())}
        )
    elif enough_episodes:
        for name, f in by_factor.items():
            c = f["comparison"]
            if not c:
                continue
            found = _association(c, t)
            if not found:
                continue
            kind, direction, p_value = found
            label = FACTOR_LABELS[name]
            if f["kind"] == "numeric":
                a, b = f"days with higher {label}", f"days with lower {label}"
            else:
                a, b = f"days with {label} recorded", f"days recorded without {label}"
            if kind == "rate":
                description = f"Your records suggest headache days were {'more' if direction == 'higher' else 'less'} common on {a} ({_pct(c['a_rate'])}%) than on {b} ({_pct(c['b_rate'])}%)."
                effect = abs(c["a_rate"] - c["b_rate"]) * 5
            else:
                description = f"The average intensity you recorded was {c['a_avg_intensity']}/10 on {a}, compared with {c['b_avg_intensity']}/10 on {b}."
                effect = abs(c["a_avg_intensity"] - c["b_avg_intensity"])
            add(
                f"factor_{name}_{kind}_{direction}",
                "factors",
                "A pattern in your daily factors",
                description,
                {
                    "factor": name,
                    "factor_kind": f["kind"],
                    "median": f.get("median"),
                    "comparison_type": kind,
                    "direction": direction,
                    "group_a_days": c["a_days"],
                    "group_b_days": c["b_days"],
                    "group_a_headache_rate": c["a_rate"],
                    "group_b_headache_rate": c["b_rate"],
                    "group_a_avg_intensity": c["a_avg_intensity"],
                    "group_b_avg_intensity": c["b_avg_intensity"],
                    "p_value": p_value,
                },
                c["a_days"] + c["b_days"],
                _comparison_level(c, p_value, t),
                effect=effect,
            )

    # --- Medication (descriptive, never about effectiveness) ------------------------
    med = result["medication"]
    if med["doses"] and enough_episodes:
        add(
            "medication_summary",
            "medication",
            "Medication you recorded",
            f"You logged {med['doses']} medication doses in this period; {med['top_medication']} was logged most often "
            f"({med['top_medication_doses']}). {med['episodes_with_medication']} of {freq['total_episodes']} episodes have medication recorded with them.",
            med | {"total_episodes": freq["total_episodes"]},
            med["doses"],
            "observed" if freq["total_episodes"] >= t.observed_min_episodes else "limited",
            effect=0,  # descriptive: listed after patterns
        )

    insights.sort(key=lambda i: -i["_score"])
    for i in insights:
        del i["_score"]

    has_extra_data = not any(g["code"] in ("sleep", "daily_factors") for g in gaps)
    data_status = "insufficient" if not enough_episodes else ("sufficient" if has_extra_data else "partial")

    return {
        "period": {"period": rng.period, "start": rng.start, "end": rng.end, "days": rng.days, "timezone": rng.tz_name},
        "previous_period": {"start": prev_start, "end": prev_end},
        "data_status": data_status,
        "summary": {
            "total_episodes": freq["total_episodes"],
            "headache_days": freq["headache_days"],
            "episodes_per_week": freq["episodes_per_week"],
            "average_intensity": inten["average"],
            "highest_intensity": inten["highest"],
            "rated_episodes": inten["rated_episodes"],
            "intensity_distribution": inten["distribution"],
            "time_of_day": result["time_of_day"],
            "average_sleep_hours": result["sleep"]["average_hours"],
            "sleep_nights": result["sleep"]["usable_nights"],
            "factor_days": result["factors"]["logged_days"],
        },
        "insights": insights,
        "data_gaps": gaps,
        "generated_at": datetime.now(timezone.utc),
    }


def build_insights(db: Session, user: User, rng: DateRange) -> dict:
    return generate_insights(analyze(db, user, rng))
