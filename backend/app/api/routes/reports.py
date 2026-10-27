"""The medical report for the authenticated user: a preview (JSON) and a PDF.

Both use the same period filters as /analytics/dashboard and /insights, plus
a language (en or ar). No user id is accepted: the records always belong to
the token's user. Reports are built on request and never stored, logged or
cached, and the PDF is generated locally (no external service).
"""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.core.rate_limit import REPORT_PDFS_PER_USER, REPORTS_PER_USER, check_and_record
from app.reports.pdf import render_pdf
from app.schemas.analytics import Period
from app.schemas.report import MedicalReport
from app.services.analytics import AnalyticsRangeError, DateRange, resolve_range
from app.services.report import build_report

router = APIRouter(prefix="/reports", tags=["reports"])

PRIVATE = {"Cache-Control": "no-store, private"}
Language = Literal["en", "ar"]
PeriodQuery = Annotated[Period, Query(description="Preset range ending today: 7d, 30d, 3m (90 days), 6m (180 days) or 12m (365 days)")]
StartQuery = Annotated[date | None, Query(description="Custom range start (inclusive). Overrides period.")]
EndQuery = Annotated[date | None, Query(description="Custom range end (inclusive). Required with start_date.")]
LangQuery = Annotated[Language, Query(description="Report language: en or ar")]


def _range(user, period: str, start_date: date | None, end_date: date | None) -> DateRange:
    try:
        return resolve_range(user, period, start_date, end_date, interval=None)
    except AnalyticsRangeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from None


def pdf_filename(rng: DateRange, lang: str) -> str:
    # Only digits, letters and hyphens: safe in every browser and file system.
    return f"namat-medical-report-{rng.start.isoformat()}-to-{rng.end.isoformat()}-{lang}.pdf"


@router.get("/medical", response_model=MedicalReport)
def medical_report(
    user: CurrentUser,
    db: DbSession,
    response: Response,
    period: PeriodQuery = "3m",
    start_date: StartQuery = None,
    end_date: EndQuery = None,
    lang: LangQuery = "en",
) -> dict:
    """Every section of the report, ready to preview."""
    check_and_record(REPORTS_PER_USER, str(user.id))  # building a report is CPU-heavy
    report = build_report(db, user, _range(user, period, start_date, end_date), lang)
    response.headers.update(PRIVATE)
    return report


@router.get(
    "/medical/pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "The report as a PDF file"}},
)
def medical_report_pdf(
    user: CurrentUser,
    db: DbSession,
    period: PeriodQuery = "3m",
    start_date: StartQuery = None,
    end_date: EndQuery = None,
    lang: LangQuery = "en",
) -> Response:
    """The same report as a downloadable, multi-page PDF."""
    check_and_record(REPORT_PDFS_PER_USER, str(user.id))
    rng = _range(user, period, start_date, end_date)
    content = render_pdf(build_report(db, user, rng, lang))
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            **PRIVATE,
            "Content-Disposition": f'attachment; filename="{pdf_filename(rng, lang)}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
