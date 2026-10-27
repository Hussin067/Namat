"""Render the medical report (app/services/report.py) as a multi-page PDF.

- fpdf2 draws the PDF locally from the report's data; nothing is sent to an
  external service and nothing is a screenshot of the web page.
- Arabic: HarfBuzz text shaping (uharfbuzz) joins the letters, and the
  Unicode bidirectional algorithm lays out right-to-left text. Tables and bar
  charts are mirrored, and text is right-aligned.
- Fonts: Noto Sans and Noto Sans Arabic (SIL Open Font License, see
  fonts/OFL.txt), merged into one font per report language (the report's own
  script first, so shared characters like digits use its design) and
  embedded as a subset. One font covering both scripts means a note typed in
  either language renders in either report, without fpdf2's fallback-font
  switching (which garbled some text in testing). The merged files are built
  once per process in the system temp folder; they are never committed.
- Text the user typed (notes) gets its own paragraph and its direction comes
  from its own first letter, so an English note in an Arabic report (or the
  reverse) keeps its word order.
- Tables repeat their header row on every page they continue onto; long
  notes flow across pages. Every page has "Page X of Y": footers are drawn
  after the layout, once the page count is known.
"""

from __future__ import annotations

import logging
import tempfile
import unicodedata
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from fontTools.merge import Merger
from fpdf import FPDF
from fpdf.fonts import FontFace

FONTS = Path(__file__).resolve().parent / "fonts"
FONT_FILES = {"latin": "NotoSans", "arabic": "NotoSansArabic"}


@lru_cache
def merged_font(first: str, weight: str) -> Path:
    """Noto Sans + Noto Sans Arabic as one font; `first` decides shared characters."""
    second = "arabic" if first == "latin" else "latin"
    target = Path(tempfile.gettempdir()) / f"namat-report-{first}-{weight}.ttf"
    if not target.exists():
        # fontTools reports a few dropped duplicate space mappings; nothing to act on.
        logging.getLogger("fontTools.merge").setLevel(logging.ERROR)
        sources = [str(FONTS / f"{FONT_FILES[name]}-{weight}.ttf") for name in (first, second)]
        partial = target.with_suffix(".tmp")
        Merger().merge(sources).save(partial)
        partial.replace(target)  # atomic: another process never sees half a file
    return target

INK = (28, 36, 48)
MUTED = (95, 107, 122)
LINE = (214, 220, 227)
BRAND = (15, 107, 107)
BRAND_SOFT = (225, 241, 239)
SUNKEN = (242, 245, 247)

BODY = 9.5
SMALL = 8.2
LINE_H = 5.0


def text_direction(text: str, default: str) -> str:
    """Direction of the first strong letter (Unicode bidi class), else the default."""
    for ch in text:
        kind = unicodedata.bidirectional(ch)
        if kind in ("R", "AL"):
            return "rtl"
        if kind == "L":
            return "ltr"
    return default


class ReportPDF(FPDF):
    def __init__(self, report: dict):
        super().__init__(format="A4", unit="mm")
        self.report = report
        self.rtl = report["direction"] == "rtl"
        self.direction = report["direction"]
        self.start_align = "R" if self.rtl else "L"
        self.end_align = "L" if self.rtl else "R"

        self.family = "report"
        first = "arabic" if self.rtl else "latin"
        self.add_font(self.family, "", str(merged_font(first, "Regular")))
        self.add_font(self.family, "B", str(merged_font(first, "Bold")))
        self.set_text_shaping(use_shaping_engine=True, direction=self.direction)

        self.set_margins(16, 16, 16)
        self.set_auto_page_break(True, margin=20)
        self.set_title(report["title"])
        self.set_lang(report["language"])
        self.set_creator("Namat")
        self.set_font(self.family, size=BODY)

    # --- Page furniture ---------------------------------------------------------

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font(self.family, size=SMALL)
        self.set_text_color(*MUTED)
        self.cell(0, 5, self.report["title"] + " · " + self.report["period_label"], align=self.start_align,
                  new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*LINE)
        self.line(self.l_margin, self.get_y() + 1, self.w - self.r_margin, self.get_y() + 1)
        self.ln(5)
        self.set_text_color(*INK)

    def footer(self):
        # Footers are drawn by add_page_numbers() once the total is known.
        pass

    def add_page_numbers(self):
        """Go back to every page and draw its footer ("Page X of Y")."""
        total = self.pages_count
        self.set_auto_page_break(False)
        brand = "نمط · التقرير الطبي" if self.rtl else "Namat · Medical report"
        for number in range(1, total + 1):
            self.page = number
            self.set_y(-13)
            self.set_font(self.family, size=SMALL)
            self.set_text_color(*MUTED)
            page = f"صفحة {number} من {total}" if self.rtl else f"Page {number} of {total}"
            y = self.get_y()
            self.cell(0, 5, f"{brand} · {self.report['generated_label']}", align=self.start_align)
            self.set_xy(self.l_margin, y)
            self.cell(0, 5, page, align=self.end_align)
        self.page = total
        self.set_text_color(*INK)

    # --- Text helpers -------------------------------------------------------------

    @contextmanager
    def direction_of(self, text: str):
        direction = text_direction(text, self.direction)
        if direction == self.direction:
            yield "R" if self.rtl else "L"
            return
        self.set_text_shaping(use_shaping_engine=True, direction=direction)
        try:
            yield "R" if direction == "rtl" else "L"
        finally:
            self.set_text_shaping(use_shaping_engine=True, direction=self.direction)

    def para(self, text: str, size: float = BODY, bold: bool = False, color=INK, user_text: bool = False, after: float = 1.5):
        self.set_font(self.family, "B" if bold else "", size)
        self.set_text_color(*color)
        if user_text:
            with self.direction_of(text) as align:
                self.multi_cell(0, LINE_H, text, align=align, new_x="LMARGIN", new_y="NEXT")
        else:
            self.multi_cell(0, LINE_H, text, align=self.start_align, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*INK)
        self.ln(after)

    def keep(self, height: float):
        """Start a new page unless `height` mm still fit (keeps headings with what follows)."""
        if self.will_page_break(height):
            self.add_page()

    def section_title(self, text: str):
        self.keep(32)
        self.ln(3)
        self.set_font(self.family, "B", 13.5)
        self.set_text_color(*BRAND)
        self.multi_cell(0, 7, text, align=self.start_align, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*BRAND)
        self.set_line_width(0.5)
        self.line(self.l_margin, self.get_y() + 0.5, self.w - self.r_margin, self.get_y() + 0.5)
        self.set_line_width(0.2)
        self.set_text_color(*INK)
        self.ln(3.5)

    def subheading(self, text: str):
        self.keep(22)
        self.ln(1)
        self.para(text, size=10.5, bold=True, after=1)

    # --- Blocks ---------------------------------------------------------------------

    def ordered(self, cells: list):
        """Column order: first column on the right in a right-to-left report."""
        return list(reversed(cells)) if self.rtl else list(cells)

    def draw_table(self, columns: list[tuple[str, float]], rows: list[list[str]], heading: bool = True,
                   size: float = SMALL, borders: str = "ALL", bold_first: bool = False):
        self.set_font(self.family, size=size)
        self.set_draw_color(*LINE)
        self.set_fill_color(255, 255, 255)  # cells would otherwise take the last fill colour used
        align = "RIGHT" if self.rtl else "LEFT"
        widths = self.ordered([w for _, w in columns])
        with self.table(
            col_widths=widths,
            text_align=align,
            first_row_as_headings=heading,
            repeat_headings=1 if heading else 0,
            headings_style=FontFace(emphasis="BOLD", fill_color=SUNKEN, color=INK),
            line_height=4.4 if size < BODY else LINE_H,
            padding=(1.2, 1.6),
            borders_layout=borders,
        ) as tbl:
            if heading:
                row = tbl.row()
                for label, _ in self.ordered(columns):
                    row.cell(label)
            first_index = len(columns) - 1 if self.rtl else 0
            for values in rows:
                row = tbl.row()
                for i, value in enumerate(self.ordered(values)):
                    style = FontFace(emphasis="BOLD", color=MUTED) if bold_first and i == first_index else None
                    row.cell(value, style=style)
        self.ln(2.5)

    def key_values(self, items: list[tuple[str, str]], label_share: float = 0.34, size: float = BODY - 0.5):
        """Label/value rows with a line under each, mirrored in Arabic.

        Much cheaper than a general table: a value that fits on one line is a
        single cell, and only longer values are wrapped. (A year of episodes has
        hundreds of these rows.)
        """
        pad_x, pad_y, line_h = 1.6, 1.2, 4.6
        label_w = self.epw * label_share
        value_w = self.epw - label_w
        right = self.w - self.r_margin
        label_x = right - label_w if self.rtl else self.l_margin
        value_x = self.l_margin if self.rtl else self.l_margin + label_w

        def height(text: str, width: float, bold: bool) -> float:
            self.set_font(self.family, "B" if bold else "", size)
            if "\n" not in text and self.get_string_width(text) <= width - 2 * pad_x:
                return line_h
            return self.multi_cell(width - 2 * pad_x, line_h, text, align=self.start_align, dry_run=True, output="HEIGHT")

        def write(text: str, x: float, y: float, width: float, bold: bool, color):
            self.set_font(self.family, "B" if bold else "", size)
            self.set_text_color(*color)
            self.set_xy(x + pad_x, y + pad_y)
            self.multi_cell(width - 2 * pad_x, line_h, text, align=self.start_align)

        self.set_draw_color(*LINE)
        for label, value in items:
            row_h = max(height(label, label_w, True), height(value, value_w, False)) + 2 * pad_y
            self.keep(row_h)
            y = self.get_y()
            write(label, label_x, y, label_w, True, MUTED)
            write(value, value_x, y, value_w, False, INK)
            self.line(self.l_margin, y + row_h, right, y + row_h)
            self.set_xy(self.l_margin, y + row_h)
        self.set_text_color(*INK)
        self.ln(2.5)

    def facts(self, items: list[dict]):
        self.key_values([(i["label"], i["value"]) for i in items])

    def bullets(self, items: list[str]):
        self.set_font(self.family, size=BODY)
        width = self.epw - 6
        for item in items:
            self.keep(LINE_H * 2)
            y = self.get_y()
            bullet_x = self.w - self.r_margin - 4 if self.rtl else self.l_margin
            text_x = self.l_margin if self.rtl else self.l_margin + 6
            self.set_xy(bullet_x, y)
            self.set_text_color(*BRAND)
            self.cell(4, LINE_H, "•", align="C")
            self.set_text_color(*INK)
            self.set_xy(text_x, y)
            self.multi_cell(width, LINE_H, item, align=self.start_align, new_x="LMARGIN", new_y="NEXT")
            self.ln(1.2)
        self.ln(1)

    def bars(self, block: dict):
        if not block["items"]:
            return
        self.subheading(block["title"])
        label_w, value_w, gap = 58.0, 34.0, 2.0
        bar_w = self.epw - label_w - value_w - 2 * gap
        row_h = 6.0
        top = block["max"] or 1
        self.set_font(self.family, size=SMALL)
        for item in block["items"]:
            self.keep(row_h + 1)
            y = self.get_y()
            length = max(0.6, bar_w * item["value"] / top) if item["value"] else 0
            if self.rtl:
                right = self.w - self.r_margin
                self.set_xy(right - label_w, y)
                self.cell(label_w, row_h, item["label"], align="R")
                bar_end = right - label_w - gap
                if length:
                    self.set_fill_color(*BRAND)
                    self.rect(bar_end - length, y + 1.3, length, row_h - 2.6, style="F")
                self.set_xy(bar_end - length - gap - value_w, y)
                self.set_text_color(*MUTED)
                self.cell(value_w, row_h, item["display"], align="R")
            else:
                self.set_xy(self.l_margin, y)
                self.cell(label_w, row_h, item["label"], align="L")
                start = self.l_margin + label_w + gap
                if length:
                    self.set_fill_color(*BRAND)
                    self.rect(start, y + 1.3, length, row_h - 2.6, style="F")
                self.set_xy(start + length + gap, y)
                self.set_text_color(*MUTED)
                self.cell(value_w, row_h, item["display"], align="L")
            self.set_text_color(*INK)
            self.set_xy(self.l_margin, y + row_h)
        self.ln(3)

    def episode(self, block: dict):
        self.keep(48)
        self.set_fill_color(*BRAND_SOFT)
        self.set_font(self.family, "B", 10.5)
        self.multi_cell(0, 7, block["heading"], align=self.start_align, fill=True, padding=(0, 2),
                        new_x="LMARGIN", new_y="NEXT")
        self.ln(1)
        self.key_values([(f["label"], f["value"]) for f in block["fields"]], label_share=0.26, size=SMALL + 0.5)
        if block.get("notes"):
            self.para(block["notes_label"], size=SMALL + 0.5, bold=True, color=MUTED, after=0.5)
            self.para(block["notes"], user_text=True, after=1)
        self.ln(2.5)

    def observation(self, block: dict):
        self.keep(45)
        self.set_font(self.family, "B", 10.5)
        self.multi_cell(0, 6, block["title"], align=self.start_align, new_x="LMARGIN", new_y="NEXT")
        self.para(block["description"], after=1)
        self.facts(block["facts"])
        self.para(block["limitation"], size=SMALL, color=MUTED, after=3)

    def callout(self, text: str):
        self.keep(30)
        self.set_fill_color(*SUNKEN)
        self.set_draw_color(*LINE)
        self.set_font(self.family, size=BODY)
        self.multi_cell(0, LINE_H + 0.5, text, align=self.start_align, border=1, fill=True, padding=4,
                        new_x="LMARGIN", new_y="NEXT")

    def block(self, b: dict):
        kind = b["type"]
        if kind == "facts":
            self.facts(b["items"])
        elif kind == "paragraph":
            style = b.get("style", "body")
            if style == "muted":
                self.para(b["text"], size=SMALL, color=MUTED)
            elif style == "label":
                self.para(b["text"], size=SMALL + 0.5, bold=True, color=MUTED, after=0.5)
            else:
                self.para(b["text"], user_text=b.get("user_text", False))
        elif kind == "subheading":
            self.subheading(b["text"])
        elif kind == "list":
            self.bullets(b["items"])
        elif kind == "table":
            if b.get("title"):
                self.subheading(b["title"])
            self.keep(16)
            self.draw_table([(c["label"], c["width"]) for c in b["columns"]], b["rows"])
        elif kind == "bars":
            self.bars(b)
        elif kind == "episode":
            self.episode(b)
        elif kind == "observation":
            self.observation(b)
        elif kind == "callout":
            self.callout(b["text"])

    # --- Document ------------------------------------------------------------------------

    def build(self) -> "ReportPDF":
        self.add_page()
        self.set_font(self.family, "B", 21)
        self.set_text_color(*BRAND)
        self.multi_cell(0, 10, self.report["title"], align=self.start_align, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*INK)
        self.para(self.report["subtitle"], size=10.5, color=MUTED, after=0.5)
        self.para(self.report["period_label"], size=11, bold=True, after=2)
        self.set_fill_color(*BRAND)
        self.rect(self.l_margin, self.get_y(), self.epw, 1.2, style="F")
        self.ln(5)
        for sec in self.report["sections"]:
            self.section_title(sec["title"])
            for b in sec["blocks"]:
                self.block(b)
        return self


def render_pdf(report: dict) -> bytes:
    """The report as PDF bytes: laid out once, then page numbers are added."""
    pdf = ReportPDF(report).build()
    pdf.add_page_numbers()
    return bytes(pdf.output())
