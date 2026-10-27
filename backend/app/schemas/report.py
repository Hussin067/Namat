"""Response body for GET /reports/medical (see app/services/report.py).

Sections are a list of typed blocks (facts, paragraph, list, subheading,
table, bars, episode, observation, callout) whose text is already in the
report's language. Block fields vary by type, so they are kept as plain
objects here; the frontend preview renders each type it knows.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class ReportSection(BaseModel):
    id: str
    title: str
    blocks: list[dict[str, Any]]


class MedicalReport(BaseModel):
    language: Literal["en", "ar"]
    direction: Literal["ltr", "rtl"]
    title: str
    subtitle: str
    period_label: str
    generated_at: datetime
    generated_label: str
    data: dict[str, Any]
    sections: list[ReportSection]
