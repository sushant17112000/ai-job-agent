"""
Excel Generator — produces a formatted, color-coded job report workbook.
"""

import logging
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)

COLOR_HEADER_FILL = "1F3864"
COLOR_HEADER_FONT = "FFFFFF"
COLOR_GREEN       = "C6EFCE"
COLOR_YELLOW      = "FFEB9C"
COLOR_GREEN_FONT  = "276221"
COLOR_YELLOW_FONT = "9C6500"


def _auto_width(ws):
    """Set column widths based on maximum cell content length."""
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            try:
                max_len = max(max_len, len(str(cell.value)) if cell.value is not None else 0)
            except Exception:
                pass
        ws.column_dimensions[col_letter].width = min(max(max_len + 2, 12), 60)


def generate_excel(
    scored_jobs: list,
    cv_profile: dict,
    report_date=None,
    output_dir: str = "reports",
) -> str:
    """
    Build and save a formatted Excel workbook.
    Returns the absolute path to the saved xlsx file.
    """
    if report_date is None:
        report_date = date.today()

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    filename = f"{report_date.isoformat()}_jobs.xlsx"
    filepath = Path(output_dir) / filename

    columns = [
        "Rank", "Job Title", "Company", "Location", "Portal",
        "Match Score", "Match Reason", "Apply URL", "Date Posted",
    ]

    rows = [
        {
            "Rank": job.get("rank", ""),
            "Job Title": job.get("title", ""),
            "Company": job.get("company", ""),
            "Location": job.get("location", ""),
            "Portal": job.get("portal", ""),
            "Match Score": job.get("match_score", ""),
            "Match Reason": job.get("match_reason", ""),
            "Apply URL": job.get("url", ""),
            "Date Posted": job.get("date_posted", ""),
        }
        for job in scored_jobs
    ]

    df = pd.DataFrame(rows, columns=columns) if rows else pd.DataFrame(columns=columns)
    df.to_excel(str(filepath), index=False, sheet_name="Jobs")

    wb = load_workbook(str(filepath))
    ws = wb["Jobs"]

    header_fill = PatternFill(fill_type="solid", fgColor=COLOR_HEADER_FILL)
    header_font = Font(bold=True, color=COLOR_HEADER_FONT)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ws.freeze_panes = "A2"

    col_map = {cell.value: cell.column for cell in ws[1]}
    score_col = col_map.get("Match Score")
    url_col   = col_map.get("Apply URL")

    for row in ws.iter_rows(min_row=2):
        # Determine row colour from match score
        score = 0
        if score_col:
            cell_val = row[score_col - 1].value
            try:
                score = int(float(str(cell_val))) if cell_val is not None else 0
            except (ValueError, TypeError):
                score = 0

        if score >= 80:
            fill = PatternFill(fill_type="solid", fgColor=COLOR_GREEN)
            font_color = COLOR_GREEN_FONT
        elif score >= 60:
            fill = PatternFill(fill_type="solid", fgColor=COLOR_YELLOW)
            font_color = COLOR_YELLOW_FONT
        else:
            fill = None
            font_color = "000000"

        for cell in row:
            if fill:
                cell.fill = fill
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if url_col is None or cell.column != url_col:
                cell.font = Font(color=font_color)

        # Clickable hyperlink for Apply URL column
        if url_col and url_col <= len(row):
            url_cell = row[url_col - 1]
            url_val  = url_cell.value
            if url_val:
                url_cell.hyperlink = str(url_val)
                url_cell.font      = Font(color="0563C1", underline="single")
                url_cell.value     = "Apply Here"

    _auto_width(ws)

    # --- Summary sheet ---
    portal_counts   = Counter(j.get("portal", "Unknown")   for j in scored_jobs)
    location_counts = Counter(j.get("location", "Unknown") for j in scored_jobs)
    top_companies   = Counter(j.get("company", "Unknown")  for j in scored_jobs).most_common(5)

    ws_s = wb.create_sheet("Summary")
    rows_s = [
        ["AI Job Search Report — Summary"], [],
        ["Report Date",        report_date.isoformat()],
        ["Candidate",          cv_profile.get("name", "Unknown")],
        ["Total Matched Jobs", len(scored_jobs)],
        [], ["Jobs by Portal"],
        *[[f"  {p}", c] for p, c in portal_counts.items()],
        [], ["Jobs by Location (Top 10)"],
        *[[f"  {l}", c] for l, c in location_counts.most_common(10)],
        [], ["Top 5 Companies"],
        *[[f"  {co}", c] for co, c in top_companies],
    ]
    for r in rows_s:
        ws_s.append(r)
    ws_s["A1"].font = Font(bold=True, size=14, color=COLOR_HEADER_FILL)
    _auto_width(ws_s)

    wb.save(str(filepath))
    logger.info("Excel report saved: %s (%d jobs)", filepath, len(scored_jobs))
    return str(filepath.resolve())
