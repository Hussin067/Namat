"""Every word in the medical report, in English and Arabic, plus formatting.

Wording rules (also checked by tests/test_reports.py):
- describe what the user recorded; never state a cause, a diagnosis, or
  whether a medication worked, and never recommend a treatment change;
- "Not recorded" (a field left empty) is kept apart from a recorded "No" or 0.

Arabic uses Western digits, like the app (locale ar-u-nu-latn), and Arabic
month names. Dates are never written as YYYY-MM-DD inside Arabic text,
because a right-to-left paragraph would reverse their parts.
"""

from __future__ import annotations

from datetime import date, datetime

# Left-to-right isolate: keeps short Latin expressions such as "p = 0.004"
# in their own order inside Arabic sentences (in the PDF and in browsers).
LRI, PDI = "⁦", "⁩"

DISCLAIMER_EN = (
    "This report is generated from information recorded by the user in Namat. Statistical observations "
    "and AI-generated explanations are intended to support communication with healthcare professionals. "
    "They are not a medical diagnosis, do not establish causation, and should not replace professional "
    "medical assessment."
)
DISCLAIMER_AR = (
    "أُعدّ هذا التقرير من المعلومات التي سجّلها المستخدم في نمط. الملاحظات الإحصائية والشروحات المولَّدة "
    "بالذكاء الاصطناعي تهدف إلى تسهيل التواصل مع مقدّمي الرعاية الصحية، وهي ليست تشخيصًا طبيًا، ولا تُثبت "
    "علاقة سببية، ولا تُغني عن التقييم الطبي المتخصص."
)

MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "ar": ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"],
}
WEEKDAYS = {
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "ar": ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"],
}


def _ar_category(n: int) -> str:
    # CLDR plural rules for Arabic.
    if n == 0:
        return "zero"
    if n == 1:
        return "one"
    if n == 2:
        return "two"
    if 3 <= n % 100 <= 10:
        return "few"
    if 11 <= n % 100 <= 99:
        return "many"
    return "other"


# Plural entries are dicts of CLDR categories. "{n}" is the count.
STRINGS: dict[str, dict] = {
    "en": {
        "title": "Headache medical report",
        "subtitle": "Prepared from the records kept in Namat",
        "page": "Page {page} of {pages}",
        "footer": "Namat · Medical report · Generated {date}",
        "running_head": "Headache medical report · {period}",
        "not_recorded": "Not recorded",
        "none_recorded": "None recorded",
        "not_available": "Not available",
        "dash": "—",
        "yes": "Yes",
        "no": "No",
        "language_names": {"en": "English", "ar": "Arabic"},
        "range": "{start} – {end}",
        "sections": {
            "info": "Report information",
            "overview": "Headache overview",
            "history": "Episode history",
            "pain": "Pain characteristics",
            "symptoms": "Associated symptoms",
            "sleep": "Sleep history",
            "factors": "Daily factors",
            "medication": "Medication history",
            "observations": "Key observations",
            "summary": "Summary for discussion with a doctor",
            "questions": "Questions to discuss with a doctor",
            "limitations": "Missing information and limitations",
            "disclaimer": "Medical disclaimer",
        },
        # A. Report information
        "info": {
            "generated": "Generated",
            "period": "Reporting period",
            "days": "Days covered",
            "timezone": "Time zone used for dates",
            "language": "Report language",
            "latest": "Latest recorded entry",
            "latest_none": "No records yet",
            "latest_episode": "Headache episode, {date}",
            "latest_sleep": "Sleep, night of {date}",
            "latest_factors": "Daily factors, {date}",
            "latest_medication": "Medication dose, {date}",
            "availability": "Data available for this period",
            "col_type": "Record type",
            "col_count": "In this period",
            "col_note": "Note",
            "type_episodes": "Headache episodes",
            "type_sleep": "Sleep records (nights)",
            "type_factors": "Daily factors (days)",
            "type_medication": "Medication doses",
            "note_episodes": "{rated} rated for intensity, {ended} with an end time",
            "note_sleep": "No record for {missing} of {days} nights",
            "note_factors": "No record for {missing} of {days} days",
            "note_medication": "{linked} linked to an episode",
            "about": "Everything in this report comes from what was recorded in Namat. Where something was not recorded, the report says so instead of estimating it.",
        },
        # B. Overview
        "overview": {
            "episodes": "Recorded episodes",
            "headache_days": "Headache days",
            "per_week": "Episodes per week",
            "average_intensity": "Average peak intensity",
            "highest_intensity": "Highest recorded intensity",
            "average_duration": "Average duration",
            "median_duration": "Median duration",
            "ongoing": "Episodes without an end time",
            "latest": "Latest episode",
            "intensity_value": "{value}/10 (from {rated})",
            "duration_value": "{value} (from {count})",
            "comparison": "In the previous {days} days ({range}) the records show {prev} and {prev_days} headache days, compared with {cur} and {cur_days} headache days in this period.",
            "comparison_none": "No comparison with the previous {days} days ({range}): the records don't cover that period, so a difference would only reflect when tracking started.",
            "headache_days_note": "A headache day is a calendar day touched by at least one episode, from its start to its end.",
        },
        # C. History
        "history": {
            "legend": "Every episode that started in this period, oldest first. “Not recorded” means the field was left empty. “None recorded” means nothing was added to that list; it doesn’t confirm that none occurred.",
            "empty": "No episodes were recorded in this period.",
            "heading": "Episode {number} · {date}",
            "start": "Started",
            "end": "Ended",
            "ongoing": "No end time recorded",
            "duration": "Duration",
            "intensity": "Peak intensity",
            "location": "Pain location",
            "aura": "Aura",
            "symptoms": "Symptoms",
            "medication": "Medication",
            "notes": "Notes",
            "dose": "{amount} · {time}",
            "relief": "relief you recorded: {value}",
        },
        # D. Pain
        "pain": {
            "location": "Pain location",
            "intensity": "Peak intensity",
            "duration": "Episode duration",
            "time_of_day": "Start time (part of the day)",
            "bar_value": "{count} ({pct})",
            "rated_note": "Intensity bands: none 0, mild 1–3, moderate 4–6, severe 7–8, very severe 9–10.",
            "empty": "No episodes were recorded in this period, so there is nothing to describe.",
        },
        # E. Symptoms
        "symptoms": {
            "col_symptom": "Symptom",
            "col_count": "Episodes",
            "col_share": "Share of episodes",
            "col_previous": "Previous {days} days",
            "combinations": "Symptoms recorded together (in at least {min} episodes)",
            "col_pair": "Symptoms",
            "none": "No symptoms were recorded with the episodes in this period.",
            "without": "{count} of {total} episodes have no symptoms recorded.",
            "no_previous": "The previous-period column is left out because the records don't cover that period.",
            "no_pairs": "No two symptoms were recorded together in at least {min} episodes.",
        },
        # F. Sleep
        "sleep": {
            "none": "No sleep was recorded in this period. Sleep can be recorded under Sleep & daily factors.",
            "nights": "Nights recorded",
            "missing": "Nights without a record",
            "average": "Average sleep length",
            "median": "Median sleep length",
            "shortest": "Shortest night",
            "longest": "Longest night",
            "quality": "Sleep quality you recorded",
            "quality_value": "{value} of 5 on average (from {count}); 1 is very poor, 5 very good",
            "awakenings": "Times woken during the night",
            "awakenings_value": "{value} on average (from {count})",
            "trend": "Average sleep length by {interval}",
            "trend_value": "{hours} ({count})",
            "intervals": {"day": "night", "week": "week (starting)", "month": "month"},
            "matching": "Sleep is compared with the following day: the night of 1 June is matched with 2 June.",
            "comparison_title": "Sleep and headache days",
            "comparison": "After shorter sleep (under {median}): {a_hits} of {a_n} days were headache days ({a_rate}). After longer sleep: {b_hits} of {b_n} ({b_rate}).",
            "comparison_too_few": "Not enough recorded nights to compare shorter and longer sleep (at least {min} nights with a following day in this period are needed; there are {have}).",
            "status_listed": "This difference is listed under Key observations.",
            "status_unclear": "This difference is not clear enough to rule out chance, so it isn't reported as a pattern.",
            "records": "Sleep records",
            "col_night": "Night of",
            "col_bed": "Went to sleep",
            "col_wake": "Woke up",
            "col_length": "Length",
            "col_quality": "Quality",
            "col_awakenings": "Awakenings",
            "qualities": {1: "Very poor", 2: "Poor", 3: "Fair", 4: "Good", 5: "Very good"},
        },
        # G. Daily factors
        "factors": {
            "none": "No daily factors were recorded in this period. They can be recorded under Sleep & daily factors.",
            "logged": "{days} of {total} days have daily factors recorded.",
            "col_factor": "Factor",
            "col_days": "Days recorded",
            "col_values": "Recorded values",
            "col_comparison": "Headache days",
            "col_result": "Result",
            "numeric_values": "average {avg}, median {median}, range {min}–{max}",
            "boolean_values": "yes on {yes}, no on {no}",
            "numeric_groups": "above {median}: {a_hits} of {a_n} ({a_rate}); at or below: {b_hits} of {b_n} ({b_rate})",
            "boolean_groups": "yes: {a_hits} of {a_n} ({a_rate}); no: {b_hits} of {b_n} ({b_rate})",
            "intensity_groups": "average intensity {a_avg}/10 versus {b_avg}/10",
            "result_listed": "Listed under Key observations",
            "result_unclear": "No clear difference",
            "result_too_few": "Too few days to compare",
            "records": "Recorded values by day",
            "records_legend": "— means not recorded. 0 and “No” are recorded values.",
            "col_date": "Date",
            "names": {
                "stress_level": "Stress (0–10)",
                "caffeine_mg": "Caffeine (mg)",
                "water_ml": "Water (ml)",
                "exercise_minutes": "Exercise (min)",
                "skipped_meal": "Skipped a meal",
                "menstruating": "Menstruation",
            },
            "rule": "Comparisons use only days where that factor was recorded. Numbers are split at your own median; yes/no factors compare recorded “yes” days with recorded “no” days.",
        },
        # H. Medication
        "medication": {
            "none": "No medication doses were recorded in this period.",
            "summary": "Medications recorded",
            "col_name": "Medication",
            "col_doses": "Doses",
            "col_days": "Days",
            "col_linked": "With an episode",
            "col_first": "First",
            "col_last": "Last",
            "doses": "Every recorded dose",
            "col_when": "Date and time",
            "col_amount": "Dose",
            "col_episode": "Episode",
            "col_relief": "Relief you recorded",
            "episode_ref": "Episode {number}",
            "not_linked": "Not linked",
            "note": "Relief ratings are what was recorded at the time. This report doesn't assess whether any medication helped and doesn't suggest changes.",
            "relief": {0: "No relief", 1: "Some relief", 2: "Good relief", 3: "Complete relief"},
        },
        # I. Observations
        "observations": {
            "intro": "These come from Namat's pattern analysis, which reports a difference only when it is large enough and unlikely to be chance alone. They are associations in the records and don't show what leads to what.",
            "none": "No clear patterns met the analysis thresholds in this period.",
            "insufficient": "Pattern analysis needs at least {min} episodes in the period; there are {have}.",
            "level": "Evidence level",
            "levels": {"observed": "Observed pattern", "limited": "Limited evidence"},
            "level_help": {
                "observed": "Seen across enough records to be worth noting.",
                "limited": "Based on few records, so it may change.",
            },
            "sample": "Based on",
            "statistic": "Statistical check",
            "fisher": "p {p} (Fisher's exact test)",
            "permutation": "p {p} (permutation test)",
            "counts": "{a} versus {b}",
            "limitation": "An association in the recorded data only. It doesn't show that one thing leads to another.",
            "limitation_limited": "Small sample: this may not hold as more records are added.",
            "descriptive": "A summary of what was recorded; not a statistical comparison.",
        },
        # J. Summary
        "summary": {
            "period": "Between {start} and {end} ({days}), {episodes} were recorded on {headache_days} headache days ({per_week} per week).",
            "none": "No headache episodes were recorded between {start} and {end} ({days}).",
            "intensity": "The average recorded peak intensity was {avg}/10 (highest {max}/10, from {rated}).",
            "duration": "Episodes with an end time lasted {median} at the median (average {avg}, from {count}).",
            "timing": "Most episodes started in the {part} ({count} of {total}).",
            "location": "The most often recorded pain location was {location} ({count} of {total}).",
            "symptom": "The most often recorded symptom was {symptom} ({count} of {total} episodes).",
            "aura": "Aura was recorded with {count} of {total} episodes.",
            "medication": "{doses} of medication were recorded on {days}.",
            "observation": "Strongest observation ({level}): {text}",
            "previous": "In the previous {days} days, {prev} were recorded.",
        },
        # K. Questions
        "questions": {
            "intro": "Suggested points to raise. They are prompts for the conversation, not conclusions.",
            "frequency": "My records show {episodes} on {headache_days} headache days in {days}. Is this something to look at more closely?",
            "change": "My records show {cur} in this period compared with {prev} in the previous {days} days. Is this change worth discussing?",
            "intensity": "{count} of my recorded episodes reached {min}/10 or higher. What would be useful to note about severe episodes?",
            "medication_days": "I recorded medication on {days} in {period_days}. How often is it appropriate for me to take it?",
            "aura": "I recorded aura with {count}. What would be useful to keep track of when this happens?",
            "observation": "My records show this: “{text}” Is this worth looking into further?",
            "ongoing": "{count} have no end time recorded. Would recording when episodes end be helpful?",
            "missing_sleep": "I have few sleep records for this period. Would tracking sleep be useful for us?",
            "missing_factors": "I have few daily-factor records for this period. Which daily details would be most useful to record?",
            "general": "Is there anything else you would like me to record before the next appointment?",
        },
        # L. Limitations
        "limitations": {
            "self_reported": "All information was entered by the user and has not been checked clinically.",
            "statistics": "Observations are associations within a small personal dataset. Many comparisons are made, days are not independent of each other, and some differences can still occur by chance.",
            "timezone": "Dates use the time zone set on the account ({timezone}).",
            "unrated": "{count} have no intensity recorded and are left out of intensity averages.",
            "ongoing": "{count} have no end time and are left out of duration figures.",
            "no_symptoms": "{count} have no symptoms recorded.",
            "sleep_missing": "Sleep is missing for {missing} of {days} nights, which limits sleep comparisons.",
            "factors_missing": "Daily factors are missing for {missing} of {days} days; each factor is only compared on days it was recorded.",
            "previous": "The previous {days} days aren't covered by the records, so changes over time can't be described.",
            "insufficient": "With fewer than {min} episodes, no pattern analysis was done.",
            "sleep_variation": "Recorded sleep lengths are too similar to compare shorter and longer nights.",
            "medication": "Medication doses not linked to an episode can't be related to specific episodes.",
        },
        # Labels shared by several sections
        "locations": {
            "left": "Left side",
            "right": "Right side",
            "bilateral": "Both sides",
            "frontal": "Forehead",
            "occipital": "Back of the head",
            "behind_eye": "Behind the eye",
            "other": "Somewhere else",
            "not_recorded": "Not recorded",
        },
        "bands": {
            "none": "None (0)",
            "mild": "Mild (1–3)",
            "moderate": "Moderate (4–6)",
            "severe": "Severe (7–8)",
            "very_severe": "Very severe (9–10)",
            "not_rated": "Not rated",
        },
        "durations": {
            "under_1h": "Under 1 hour",
            "h1_4": "1 to 4 hours",
            "h4_12": "4 to 12 hours",
            "h12_24": "12 to 24 hours",
            "over_24h": "Over 24 hours",
            "ongoing": "No end time",
        },
        "parts": {
            "morning": "Morning (05:00–11:59)",
            "afternoon": "Afternoon (12:00–16:59)",
            "evening": "Evening (17:00–20:59)",
            "night": "Night (21:00–04:59)",
        },
        "part_names": {"morning": "morning", "afternoon": "afternoon", "evening": "evening", "night": "night"},
        "factor_names": {
            "stress_level": "stress level",
            "caffeine_mg": "caffeine",
            "water_ml": "water",
            "exercise_minutes": "exercise",
            "skipped_meal": "skipped meals",
            "menstruating": "menstruation",
        },
        "units": {},
        "symptom_names": {},
        "counts": {
            "episodes": {"one": "{n} episode", "other": "{n} episodes"},
            "days": {"one": "{n} day", "other": "{n} days"},
            "nights": {"one": "{n} night", "other": "{n} nights"},
            "doses": {"one": "{n} dose", "other": "{n} doses"},
            "rated": {"one": "{n} rated episode", "other": "{n} rated episodes"},
        },
        "hours": "{h} h",
        "duration_hm": "{h} h {m} min",
        "duration_h": "{h} h",
        "duration_m": "{m} min",
    },
    "ar": {
        "title": "التقرير الطبي للصداع",
        "subtitle": "أُعدّ من السجلات المحفوظة في نمط",
        "page": "صفحة {page} من {pages}",
        "footer": "نمط · التقرير الطبي · أُنشئ في {date}",
        "running_head": "التقرير الطبي للصداع · {period}",
        "not_recorded": "غير مسجَّل",
        "none_recorded": "لم يُسجَّل شيء",
        "not_available": "غير متاح",
        "dash": "—",
        "yes": "نعم",
        "no": "لا",
        "language_names": {"en": "الإنجليزية", "ar": "العربية"},
        "range": "{start} – {end}",
        "sections": {
            "info": "معلومات التقرير",
            "overview": "نظرة عامة على الصداع",
            "history": "سجل النوبات بالترتيب الزمني",
            "pain": "خصائص الألم",
            "symptoms": "الأعراض المصاحبة",
            "sleep": "سجل النوم",
            "factors": "العوامل اليومية",
            "medication": "سجل الأدوية",
            "observations": "أبرز الملاحظات",
            "summary": "ملخص للنقاش مع الطبيب",
            "questions": "أسئلة للنقاش مع الطبيب",
            "limitations": "المعلومات الناقصة وحدود التقرير",
            "disclaimer": "إخلاء المسؤولية الطبية",
        },
        "info": {
            "generated": "تاريخ الإنشاء",
            "period": "فترة التقرير",
            "days": "عدد الأيام",
            "timezone": "المنطقة الزمنية المستخدمة للتواريخ",
            "language": "لغة التقرير",
            "latest": "آخر سجل",
            "latest_none": "لا توجد سجلات بعد",
            "latest_episode": "نوبة صداع، {date}",
            "latest_sleep": "نوم، ليلة {date}",
            "latest_factors": "عوامل يومية، {date}",
            "latest_medication": "جرعة دواء، {date}",
            "availability": "البيانات المتوفرة لهذه الفترة",
            "col_type": "نوع السجل",
            "col_count": "في هذه الفترة",
            "col_note": "ملاحظة",
            "type_episodes": "نوبات الصداع",
            "type_sleep": "سجلات النوم (ليالٍ)",
            "type_factors": "العوامل اليومية (أيام)",
            "type_medication": "جرعات الدواء",
            "note_episodes": "{rated} بشدة مسجّلة، و{ended} بوقت انتهاء",
            "note_sleep": "لا يوجد سجل لـ{missing} من أصل {days} ليلة",
            "note_factors": "لا يوجد سجل لـ{missing} من أصل {days} يوم",
            "note_medication": "{linked} مرتبطة بنوبة",
            "about": "كل ما في هذا التقرير مأخوذ مما سُجّل في نمط. وحيث لم يُسجَّل شيء، يذكر التقرير ذلك بدلًا من تقديره.",
        },
        "overview": {
            "episodes": "النوبات المسجّلة",
            "headache_days": "أيام الصداع",
            "per_week": "النوبات في الأسبوع",
            "average_intensity": "متوسط أعلى شدة",
            "highest_intensity": "أعلى شدة مسجّلة",
            "average_duration": "متوسط المدة",
            "median_duration": "وسيط المدة",
            "ongoing": "نوبات بلا وقت انتهاء",
            "latest": "آخر نوبة",
            "intensity_value": "{value}/10 (من {rated})",
            "duration_value": "{value} (من {count})",
            "comparison": "في الأيام الـ{days} السابقة ({range}) تُظهر السجلات {prev} و{prev_days} يوم صداع، مقارنةً بـ{cur} و{cur_days} يوم صداع في هذه الفترة.",
            "comparison_none": "لا توجد مقارنة بالأيام الـ{days} السابقة ({range}): السجلات لا تغطي تلك الفترة، فأي فرق لن يعكس إلا وقت بدء التسجيل.",
            "headache_days_note": "يوم الصداع هو أي يوم تقويمي شملته نوبة واحدة على الأقل، من بدايتها إلى نهايتها.",
        },
        "history": {
            "legend": "كل نوبة بدأت في هذه الفترة، من الأقدم إلى الأحدث. «غير مسجَّل» يعني أن الحقل تُرك فارغًا. «لم يُسجَّل شيء» يعني أنه لم يُضف شيء إلى تلك القائمة، ولا يؤكد عدم حدوثه.",
            "empty": "لم تُسجَّل أي نوبات في هذه الفترة.",
            "heading": "النوبة {number} · {date}",
            "start": "البداية",
            "end": "النهاية",
            "ongoing": "لم يُسجَّل وقت انتهاء",
            "duration": "المدة",
            "intensity": "أعلى شدة",
            "location": "مكان الألم",
            "aura": "الهالة",
            "symptoms": "الأعراض",
            "medication": "الدواء",
            "notes": "ملاحظات",
            "dose": "{amount} · {time}",
            "relief": "التحسّن الذي سجّلته: {value}",
        },
        "pain": {
            "location": "مكان الألم",
            "intensity": "أعلى شدة",
            "duration": "مدة النوبة",
            "time_of_day": "وقت البدء (جزء اليوم)",
            "bar_value": "{count} ({pct})",
            "rated_note": "فئات الشدة: لا ألم 0، خفيف 1–3، متوسط 4–6، شديد 7–8، شديد جدًا 9–10.",
            "empty": "لم تُسجَّل أي نوبات في هذه الفترة، فلا يوجد ما يُوصف.",
        },
        "symptoms": {
            "col_symptom": "العرَض",
            "col_count": "النوبات",
            "col_share": "النسبة من النوبات",
            "col_previous": "الأيام الـ{days} السابقة",
            "combinations": "أعراض سُجّلت معًا (في {min} نوبات على الأقل)",
            "col_pair": "الأعراض",
            "none": "لم تُسجَّل أعراض مع النوبات في هذه الفترة.",
            "without": "{count} من أصل {total} بلا أعراض مسجّلة.",
            "no_previous": "حُذف عمود الفترة السابقة لأن السجلات لا تغطي تلك الفترة.",
            "no_pairs": "لم يُسجَّل عرَضان معًا في {min} نوبات على الأقل.",
        },
        "sleep": {
            "none": "لم يُسجَّل نوم في هذه الفترة. يمكن تسجيله من صفحة «النوم والعوامل اليومية».",
            "nights": "الليالي المسجّلة",
            "missing": "ليالٍ بلا سجل",
            "average": "متوسط مدة النوم",
            "median": "وسيط مدة النوم",
            "shortest": "أقصر ليلة",
            "longest": "أطول ليلة",
            "quality": "جودة النوم التي سجّلتها",
            "quality_value": "{value} من 5 في المتوسط (من {count})؛ 1 سيئ جدًا و5 جيد جدًا",
            "awakenings": "مرات الاستيقاظ أثناء الليل",
            "awakenings_value": "{value} في المتوسط (من {count})",
            "trend": "متوسط مدة النوم حسب {interval}",
            "trend_value": "{hours} ({count})",
            "intervals": {"day": "الليلة", "week": "الأسبوع (بدايته)", "month": "الشهر"},
            "matching": "يُقارن النوم باليوم التالي: ليلة 1 يونيو تُقابَل بيوم 2 يونيو.",
            "comparison_title": "النوم وأيام الصداع",
            "comparison": "بعد نوم أقصر (أقل من {median}): كانت {a_hits} من أصل {a_n} أيامَ صداع ({a_rate}). بعد نوم أطول: {b_hits} من أصل {b_n} ({b_rate}).",
            "comparison_too_few": "لا توجد ليالٍ مسجّلة كافية للمقارنة بين النوم الأقصر والأطول (يلزم {min} ليالٍ على الأقل يقع يومها التالي في هذه الفترة، والمتوفر {have}).",
            "status_listed": "هذا الفرق مذكور ضمن «أبرز الملاحظات».",
            "status_unclear": "هذا الفرق ليس واضحًا بما يكفي لاستبعاد الصدفة، لذا لا يُعرض كنمط.",
            "records": "سجلات النوم",
            "col_night": "ليلة",
            "col_bed": "وقت النوم",
            "col_wake": "وقت الاستيقاظ",
            "col_length": "المدة",
            "col_quality": "الجودة",
            "col_awakenings": "مرات الاستيقاظ",
            "qualities": {1: "سيئ جدًا", 2: "سيئ", 3: "مقبول", 4: "جيد", 5: "جيد جدًا"},
        },
        "factors": {
            "none": "لم تُسجَّل عوامل يومية في هذه الفترة. يمكن تسجيلها من صفحة «النوم والعوامل اليومية».",
            "logged": "سُجّلت عوامل يومية في {days} من أصل {total} يوم.",
            "col_factor": "العامل",
            "col_days": "أيام التسجيل",
            "col_values": "القيم المسجّلة",
            "col_comparison": "أيام الصداع",
            "col_result": "النتيجة",
            "numeric_values": "المتوسط {avg}، الوسيط {median}، المدى {min}–{max}",
            "boolean_values": "نعم في {yes}، لا في {no}",
            "numeric_groups": "أعلى من {median}: {a_hits} من أصل {a_n} ({a_rate})؛ عند الوسيط أو أقل: {b_hits} من أصل {b_n} ({b_rate})",
            "boolean_groups": "نعم: {a_hits} من أصل {a_n} ({a_rate})؛ لا: {b_hits} من أصل {b_n} ({b_rate})",
            "intensity_groups": "متوسط الشدة {a_avg}/10 مقابل {b_avg}/10",
            "result_listed": "مذكور ضمن «أبرز الملاحظات»",
            "result_unclear": "لا يوجد فرق واضح",
            "result_too_few": "أيام قليلة لا تكفي للمقارنة",
            "records": "القيم المسجّلة حسب اليوم",
            "records_legend": "— تعني غير مسجَّل. القيمة 0 و«لا» قيم مسجّلة.",
            "col_date": "التاريخ",
            "names": {
                "stress_level": "التوتر (0–10)",
                "caffeine_mg": "الكافيين (ملغ)",
                "water_ml": "الماء (مل)",
                "exercise_minutes": "التمارين (دقيقة)",
                "skipped_meal": "تخطّي وجبة",
                "menstruating": "الدورة الشهرية",
            },
            "rule": "تستخدم المقارنات الأيام التي سُجّل فيها العامل فقط. تُقسَم القيم الرقمية عند الوسيط الخاص بك، وتُقارَن عوامل «نعم/لا» بين الأيام المسجّلة بـ«نعم» والأيام المسجّلة بـ«لا».",
        },
        "medication": {
            "none": "لم تُسجَّل جرعات دواء في هذه الفترة.",
            "summary": "الأدوية المسجّلة",
            "col_name": "الدواء",
            "col_doses": "الجرعات",
            "col_days": "الأيام",
            "col_linked": "مع نوبة",
            "col_first": "الأولى",
            "col_last": "الأخيرة",
            "doses": "كل الجرعات المسجّلة",
            "col_when": "التاريخ والوقت",
            "col_amount": "الجرعة",
            "col_episode": "النوبة",
            "col_relief": "التحسّن الذي سجّلته",
            "episode_ref": "النوبة {number}",
            "not_linked": "غير مرتبطة",
            "note": "درجات التحسّن هي ما سُجّل في حينه. لا يقيّم هذا التقرير ما إذا كان أي دواء قد ساعد، ولا يقترح أي تغيير.",
            "relief": {0: "لا تحسّن", 1: "تحسّن بسيط", 2: "تحسّن جيد", 3: "زوال تام"},
        },
        "observations": {
            "intro": "هذه الملاحظات من تحليل الأنماط في نمط، الذي لا يذكر فرقًا إلا إذا كان كبيرًا بما يكفي ومن غير المرجح أن يكون صدفة. وهي ارتباطات في السجلات، وليست أسبابًا.",
            "none": "لم يستوفِ أي نمط واضح شروط التحليل في هذه الفترة.",
            "insufficient": "يحتاج تحليل الأنماط إلى {min} نوبات على الأقل في الفترة، والمتوفر {have}.",
            "level": "مستوى الدليل",
            "levels": {"observed": "نمط ملحوظ", "limited": "أدلة محدودة"},
            "level_help": {
                "observed": "ظهر في عدد كافٍ من السجلات ليستحق الملاحظة.",
                "limited": "مبني على عدد قليل من السجلات، لذا قد يتغيّر.",
            },
            "sample": "بناءً على",
            "statistic": "الفحص الإحصائي",
            "fisher": LRI + "p {p}" + PDI + " (اختبار فيشر الدقيق)",
            "permutation": LRI + "p {p}" + PDI + " (اختبار التبديل)",
            "counts": "{a} مقابل {b}",
            "limitation": "ارتباط في البيانات المسجّلة فقط، ولا يدل على أن أمرًا يؤدي إلى آخر.",
            "limitation_limited": "عيّنة صغيرة: قد لا يستمر هذا مع إضافة سجلات أكثر.",
            "descriptive": "ملخص لما سُجّل، وليس مقارنة إحصائية.",
        },
        "summary": {
            "period": "بين {start} و{end} ({days})، سُجّلت {episodes} في {headache_days} يوم صداع ({per_week} في الأسبوع).",
            "none": "لم تُسجَّل أي نوبات صداع بين {start} و{end} ({days}).",
            "intensity": "كان متوسط أعلى شدة مسجّلة {avg}/10 (الأعلى {max}/10، من {rated}).",
            "duration": "بلغ وسيط مدة النوبات التي سُجّل وقت انتهائها {median} (المتوسط {avg}، من {count}).",
            "timing": "بدأت معظم النوبات {part} ({count} من أصل {total}).",
            "location": "كان مكان الألم الأكثر تسجيلًا: {location} ({count} من أصل {total}).",
            "symptom": "كان العرَض الأكثر تسجيلًا: {symptom} ({count} من أصل {total} نوبة).",
            "aura": "سُجّلت الهالة مع {count} من أصل {total} نوبة.",
            "medication": "سُجّلت {doses} في {days}.",
            "observation": "أقوى ملاحظة ({level}): {text}",
            "previous": "وفي الأيام الـ{days} السابقة سُجّلت {prev}.",
        },
        "questions": {
            "intro": "نقاط مقترحة للنقاش. هي مداخل للحديث، وليست استنتاجات.",
            "frequency": "تُظهر سجلاتي {episodes} في {headache_days} يوم صداع خلال {days}. هل يستدعي هذا نظرة أدق؟",
            "change": "تُظهر سجلاتي {cur} في هذه الفترة مقارنةً بـ{prev} في الأيام الـ{days} السابقة. هل يستحق هذا التغيّر النقاش؟",
            "intensity": "بلغت {count} من نوباتي المسجّلة شدة {min}/10 أو أكثر. ما الذي ينبغي أن أدوّنه عن النوبات الشديدة؟",
            "medication_days": "سجّلت تناول دواء في {days} خلال {period_days}. كم مرة يناسبني تناوله؟",
            "aura": "عدد النوبات التي سجّلتُ معها الهالة: {count}. ما الذي ينبغي أن أتابعه عندما يحدث ذلك؟",
            "observation": "تُظهر سجلاتي ما يلي: «{text}» هل يستحق هذا مزيدًا من البحث؟",
            "ongoing": "{count} بلا وقت انتهاء مسجّل. هل يفيد تسجيل وقت انتهاء النوبات؟",
            "missing_sleep": "سجلات نومي قليلة في هذه الفترة. هل تفيدنا متابعة النوم؟",
            "missing_factors": "سجلات العوامل اليومية لديّ قليلة في هذه الفترة. ما التفاصيل اليومية الأكثر فائدة للتسجيل؟",
            "general": "هل هناك ما تودّ أن أسجّله قبل الموعد القادم؟",
        },
        "limitations": {
            "self_reported": "أدخل المستخدم كل المعلومات بنفسه، ولم تُراجَع سريريًا.",
            "statistics": "الملاحظات ارتباطات ضمن بيانات شخصية محدودة. تُجرى مقارنات عديدة، والأيام ليست مستقلة عن بعضها، وقد تظهر بعض الفروق بالصدفة رغم ذلك.",
            "timezone": "تستخدم التواريخ المنطقة الزمنية المحددة في الحساب ({timezone}).",
            "unrated": "{count} بلا شدة مسجّلة، ولم تُحتسب في متوسطات الشدة.",
            "ongoing": "{count} بلا وقت انتهاء، ولم تُحتسب في أرقام المدة.",
            "no_symptoms": "{count} بلا أعراض مسجّلة.",
            "sleep_missing": "النوم غير مسجَّل في {missing} من أصل {days} ليلة، مما يحدّ من مقارنات النوم.",
            "factors_missing": "العوامل اليومية غير مسجّلة في {missing} من أصل {days} يوم، ويُقارَن كل عامل فقط في الأيام التي سُجّل فيها.",
            "previous": "السجلات لا تغطي الأيام الـ{days} السابقة، فلا يمكن وصف التغيّر مع الوقت.",
            "insufficient": "مع أقل من {min} نوبات، لم يُجرَ تحليل للأنماط.",
            "sleep_variation": "مدد النوم المسجّلة متقاربة جدًا بحيث لا يمكن المقارنة بين الليالي الأقصر والأطول.",
            "medication": "لا يمكن ربط جرعات الدواء غير المرتبطة بنوبة بنوبات محددة.",
        },
        "locations": {
            "left": "الجانب الأيسر",
            "right": "الجانب الأيمن",
            "bilateral": "كلا الجانبين",
            "frontal": "الجبهة",
            "occipital": "مؤخرة الرأس",
            "behind_eye": "خلف العين",
            "other": "مكان آخر",
            "not_recorded": "غير مسجَّل",
        },
        "bands": {
            "none": "لا ألم (0)",
            "mild": "خفيف (1–3)",
            "moderate": "متوسط (4–6)",
            "severe": "شديد (7–8)",
            "very_severe": "شديد جدًا (9–10)",
            "not_rated": "بلا تقييم",
        },
        "durations": {
            "under_1h": "أقل من ساعة",
            "h1_4": "من 1 إلى 4 ساعات",
            "h4_12": "من 4 إلى 12 ساعة",
            "h12_24": "من 12 إلى 24 ساعة",
            "over_24h": "أكثر من 24 ساعة",
            "ongoing": "بلا وقت انتهاء",
        },
        "parts": {
            "morning": "الصباح (05:00–11:59)",
            "afternoon": "بعد الظهر (12:00–16:59)",
            "evening": "المساء (17:00–20:59)",
            "night": "الليل (21:00–04:59)",
        },
        "part_names": {"morning": "في الصباح", "afternoon": "بعد الظهر", "evening": "في المساء", "night": "ليلًا"},
        "factor_names": {
            "stress_level": "مستوى التوتر",
            "caffeine_mg": "الكافيين",
            "water_ml": "الماء",
            "exercise_minutes": "التمارين",
            "skipped_meal": "تخطّي الوجبات",
            "menstruating": "الدورة الشهرية",
        },
        # Same translations as the app (frontend/src/i18n/messages/ar.js).
        "units": {"mg": "ملغ", "ml": "مل", "tablet": "قرص", "capsule": "كبسولة", "puff": "بخّة", "drop": "قطرة"},
        "symptom_names": {
            "Nausea": "غثيان",
            "Vomiting": "قيء",
            "Sensitivity to light": "حساسية للضوء",
            "Sensitivity to sound": "حساسية للصوت",
            "Sensitivity to smell": "حساسية للروائح",
            "Visual aura": "هالة بصرية",
            "Tingling or numbness": "وخز أو خدر",
            "Dizziness": "دوخة",
            "Difficulty concentrating": "صعوبة في التركيز",
            "Neck pain or stiffness": "ألم أو تيبّس في الرقبة",
            "Fatigue": "إرهاق",
            "Throbbing pain": "ألم نابض",
            "Pain worse with activity": "ألم يزداد مع الحركة",
        },
        "counts": {
            "episodes": {"zero": "لا نوبات", "one": "نوبة واحدة", "two": "نوبتان", "few": "{n} نوبات", "many": "{n} نوبة", "other": "{n} نوبة"},
            "days": {"zero": "لا أيام", "one": "يوم واحد", "two": "يومان", "few": "{n} أيام", "many": "{n} يومًا", "other": "{n} يوم"},
            "nights": {"zero": "لا ليالٍ", "one": "ليلة واحدة", "two": "ليلتان", "few": "{n} ليالٍ", "many": "{n} ليلة", "other": "{n} ليلة"},
            "doses": {"zero": "لا جرعات", "one": "جرعة واحدة", "two": "جرعتان", "few": "{n} جرعات", "many": "{n} جرعة", "other": "{n} جرعة"},
            "rated": {"zero": "لا نوبات مقيّمة", "one": "نوبة واحدة مقيّمة", "two": "نوبتين مقيّمتين", "few": "{n} نوبات مقيّمة", "many": "{n} نوبة مقيّمة", "other": "{n} نوبة مقيّمة"},
        },
        "hours": "{h} ساعة",
        "duration_hm": "{h} س {m} د",
        "duration_h": "{h} س",
        "duration_m": "{m} د",
    },
}


class Lang:
    """Text and number/date formatting for one report language."""

    def __init__(self, code: str):
        self.code = code
        self.rtl = code == "ar"
        self.direction = "rtl" if self.rtl else "ltr"
        self._s = STRINGS[code]

    def t(self, key: str, **values) -> str:
        node = self.get(key)
        return node.format(**values) if values else node

    def get(self, key: str):
        node = self._s
        for part in key.split("."):
            # Rating labels (sleep quality, relief) are keyed by number.
            node = node[int(part)] if part.isdigit() else node[part]
        return node

    def count(self, kind: str, n: int) -> str:
        forms = self._s["counts"][kind]
        category = _ar_category(n) if self.rtl else ("one" if n == 1 else "other")
        return forms.get(category, forms["other"]).format(n=n)

    # --- Values ---------------------------------------------------------------

    def num(self, value, digits: int = 1) -> str:
        if value is None:
            return self.t("not_available")
        text = f"{float(value):.{digits}f}".rstrip("0").rstrip(".") if digits else str(round(float(value)))
        return text or "0"

    def pct(self, rate: float | None) -> str:
        return self.t("not_available") if rate is None else f"{round(rate * 100)}%"

    def date(self, d: date) -> str:
        return f"{d.day} {MONTHS[self.code][d.month - 1]} {d.year}"

    def day(self, d: date) -> str:
        """Date with the weekday, for the episode history."""
        return f"{WEEKDAYS[self.code][d.weekday()]} {self.date(d)}"

    def time(self, dt: datetime) -> str:
        return f"{dt.hour:02d}:{dt.minute:02d}"

    def datetime(self, dt: datetime) -> str:
        return f"{self.date(dt.date())}، {self.time(dt)}" if self.rtl else f"{self.date(dt.date())}, {self.time(dt)}"

    def period(self, start: date, end: date) -> str:
        return self.t("range", start=self.date(start), end=self.date(end))

    def duration(self, minutes: int | None) -> str:
        if minutes is None:
            return self.t("not_available")
        h, m = divmod(int(minutes), 60)
        if h and m:
            return self.t("duration_hm", h=h, m=m)
        return self.t("duration_h", h=h) if h else self.t("duration_m", m=m)

    def hours(self, value: float | None) -> str:
        return self.t("not_available") if value is None else self.t("hours", h=self.num(value))

    def symptom(self, name: str) -> str:
        return self._s["symptom_names"].get(name, name)

    def unit(self, unit: str | None) -> str:
        return "" if not unit else self._s["units"].get(unit, unit)

    def p_value(self, p: float) -> str:
        """Text after the letter p: "< 0.001" or "= 0.004"."""
        return "< 0.001" if p < 0.001 else f"= {p:.3f}"


# Arabic wording for the insights engine's observations (the engine itself
# writes English). Mirrors the app's translations in frontend ar.js.
OBSERVATIONS_AR = {
    "frequency_increase": "نوبات أكثر من الفترة السابقة",
    "frequency_decrease": "نوبات أقل من الفترة السابقة",
    "frequency_stable": "عدد نوبات مماثل للفترة السابقة",
    "frequency_body": "تُظهر سجلاتك {current} في هذه الفترة، و{previous} في الأيام الـ{days} السابقة.",
    "intensity_higher": "متوسط شدة أعلى من السابق",
    "intensity_lower": "متوسط شدة أقل من السابق",
    "intensity_body": "كان متوسط أعلى شدة سجّلتها {current}/10 في هذه الفترة، مقارنةً بـ{previous}/10 في الأيام الـ{days} السابقة.",
    "time_title": "بدأت معظم النوبات {part}",
    "time_body": "بدأت {count} من نوباتك الـ{total} في هذه الفترة {part}.",
    "symptom_common": "العرَض الأكثر تسجيلًا لديك",
    "symptom_common_body": "سُجّل «{symptom}» في {count} من نوباتك الـ{total} في هذه الفترة.",
    "symptom_pair": "أعراض تُسجَّل معًا كثيرًا",
    "symptom_pair_body": "سُجّل «{a}» و«{b}» معًا في {count} من نوباتك الـ{total} في هذه الفترة.",
    "sleep_title": "نمط في نومك حسب سجلاتك",
    "sleep_rate_body": "في سجلاتك، كانت {a} من الأيام التي تلت نومًا أقصر (أقل من {hours} ساعة) أيامَ صداع، مقارنةً بـ{b} من الأيام التي تلت نومًا أطول.",
    "sleep_intensity_body": "في أيام الصداع التي تلت نومًا أقصر (أقل من {hours} ساعة)، كان متوسط الشدة المسجّل {a}/10، مقارنةً بـ{b}/10 بعد نوم أطول.",
    "factor_title": "نمط في عواملك اليومية",
    "factor_rate_body": "في سجلاتك، كانت {a_rate} من {a} أيامَ صداع، مقارنةً بـ{b_rate} من {b}.",
    "factor_intensity_body": "كان متوسط الشدة المسجّل {a_avg}/10 في {a}، مقارنةً بـ{b_avg}/10 في {b}.",
    "factor_groups": {
        "stress_level": ("الأيام التي سجّلت فيها توترًا أعلى", "الأيام التي سجّلت فيها توترًا أقل"),
        "caffeine_mg": ("الأيام التي سجّلت فيها كافيينًا أكثر", "الأيام التي سجّلت فيها كافيينًا أقل"),
        "water_ml": ("الأيام التي سجّلت فيها شرب ماء أكثر", "الأيام التي سجّلت فيها شرب ماء أقل"),
        "exercise_minutes": ("الأيام التي سجّلت فيها تمارين أكثر", "الأيام التي سجّلت فيها تمارين أقل"),
        "skipped_meal": ("الأيام التي سجّلت فيها تخطي وجبة", "الأيام التي سجّلت فيها عدم تخطي أي وجبة"),
        "menstruating": ("الأيام التي سجّلت فيها الدورة الشهرية", "الأيام التي سجّلت فيها عدم وجود الدورة الشهرية"),
    },
    "medication_title": "الأدوية التي سجّلتها",
    "medication_body": "سجّلت {doses} في هذه الفترة، وكان «{top}» الأكثر تسجيلًا ({top_doses}). لدى {with_medication} من نوباتك الـ{total} دواء مسجَّل معها.",
}
