"""Canonical Excel cell typing + number formats for every ERP exporter.

Global rules (owner, 2026-11-20):
- Numeric business values (CIF, quantities, rates, amounts, percentages, totals)
  are written as real numeric cells — never pre-formatted strings — so SUM,
  sorting and filtering work. ``Decimal`` is passed through unchanged (openpyxl
  serialises it exactly), so precision and sign are preserved.
- Dates are real Excel date cells displayed as DD-MM-YYYY.
- Identifiers (licence number, HSN, IEC, BOE number, file number) are text.

Use the ``write_*`` helpers when building a sheet, and ``finalize_workbook`` as
a safety net just before saving (it applies the DD-MM-YYYY format to every
date cell and strips tz info, which openpyxl cannot write).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django.utils import timezone

DATE_FORMAT = "DD-MM-YYYY"
DATETIME_FORMAT = "DD-MM-YYYY HH:MM"
AMOUNT_FORMAT = "#,##0.00"
QUANTITY_FORMAT = "#,##0.000"
RATE_FORMAT = "#,##0.00##"
INTEGER_FORMAT = "#,##0"
# Percentages stored as "12.5" (not 0.125) — display the number with a % suffix.
PERCENT_POINTS_FORMAT = '0.00"%"'
TEXT_FORMAT = "@"

NUMERIC_TYPES = (int, float, Decimal)
_DEFAULT_DATE_FORMATS = {"General", "yyyy-mm-dd", "yyyy-mm-dd h:mm:ss", "mm-dd-yy"}


def to_excel_datetime(value: datetime) -> datetime:
    """Aware datetime → naive local time (openpyxl rejects tz-aware values).

    Uses Django's current time zone so the calendar date shown matches the app.
    """
    if timezone.is_aware(value):
        value = timezone.localtime(value)
        return value.replace(tzinfo=None)
    return value


def parse_display_date(value: Any) -> date | None:
    """Unambiguous parse of DD-MM-YYYY / DD/MM/YYYY / ISO YYYY-MM-DD → ``date``.

    Never guesses MM-DD: a 4-digit leading part means ISO, a 4-digit trailing
    part means day-first. Returns None for anything else.
    """
    if isinstance(value, datetime):
        return to_excel_datetime(value).date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip().split("T")[0].split(" ")[0]
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def to_number(value: Any) -> int | float | Decimal | None:
    """Numeric value for a cell; numeric strings ("1,234.50", "-3") → Decimal.

    Returns None for blanks / non-numeric text so callers can write an empty cell.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, NUMERIC_TYPES):
        return value
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace("$", "").replace("₹", "")
        if not text:
            return None
        try:
            return Decimal(text)
        except InvalidOperation:
            return None
    return None


def write_number(cell, value: Any, number_format: str = AMOUNT_FORMAT):
    """Write a numeric cell (None/blank → empty cell, format still applied)."""
    cell.value = to_number(value)
    cell.number_format = number_format
    return cell


def write_date(cell, value: Any, number_format: str = DATE_FORMAT):
    """Write a real Excel date cell displayed as DD-MM-YYYY (blank if unparsable)."""
    if isinstance(value, datetime) and number_format == DATETIME_FORMAT:
        cell.value = to_excel_datetime(value)
    else:
        cell.value = parse_display_date(value)
    cell.number_format = number_format
    return cell


def write_text(cell, value: Any):
    """Write an identifier / free text as a text cell (keeps leading zeros)."""
    cell.value = None if value is None else str(value)
    cell.number_format = TEXT_FORMAT
    return cell


def sum_formula(column: int | str, first_row: int, last_row: int) -> str | int:
    """``=SUM(H2:H101)`` over the data rows only (the total row is never included).

    Returns 0 when there are no data rows so an empty sheet still totals to zero.
    """
    from openpyxl.utils import get_column_letter

    letter = column if isinstance(column, str) else get_column_letter(column)
    if last_row < first_row:
        return 0
    return f"=SUM({letter}{first_row}:{letter}{last_row})"


MAX_FORMULA_LENGTH = 8000  # Excel hard limit is 8,192 characters
MAX_FUNCTION_ARGS = 255  # Excel SUM() argument limit


def sum_cells_formula(cells: list[str], fallback: Any = None) -> Any:
    """``=SUM(F5,F20,…)`` over explicit cells (e.g. sub-total or group rows).

    Chunks into nested SUMs to respect Excel's 255-argument limit and returns
    ``fallback`` (the computed total) when the formula would exceed Excel's
    length limit or there are no cells, so a huge sheet never needs repair.
    """
    if not cells:
        return fallback
    chunks = [cells[i:i + MAX_FUNCTION_ARGS] for i in range(0, len(cells), MAX_FUNCTION_ARGS)]
    if len(chunks) == 1:
        formula = "=SUM(" + ",".join(chunks[0]) + ")"
    elif len(chunks) <= MAX_FUNCTION_ARGS:
        formula = "=SUM(" + ",".join("SUM(" + ",".join(c) + ")" for c in chunks) + ")"
    else:
        return fallback
    return formula if len(formula) <= MAX_FORMULA_LENGTH else fallback


def sumif_label_formula(label_column: int | str, label: str, value_column: int | str,
                        first_row: int, last_row: int) -> str | int:
    """``=SUMIF(C1:C99,"Total",D1:D99)`` — totals rows whose label cell equals ``label``.

    Used for grand totals over sub-total rows: constant length (no Excel limit),
    and the range ends above the grand-total row so it never includes itself.
    """
    from openpyxl.utils import get_column_letter

    if last_row < first_row:
        return 0
    lab = label_column if isinstance(label_column, str) else get_column_letter(label_column)
    val = value_column if isinstance(value_column, str) else get_column_letter(value_column)
    escaped = label.replace('"', '""')
    return f'=SUMIF({lab}{first_row}:{lab}{last_row},"{escaped}",{val}{first_row}:{val}{last_row})'


def write_sum(cell, first_row: int, last_row: int, number_format: str = AMOUNT_FORMAT, column: int | str | None = None):
    """Write a live SUM formula for ``cell``'s column (or ``column``) over the data range."""
    cell.value = sum_formula(column if column is not None else cell.column, first_row, last_row)
    cell.number_format = number_format
    return cell


def excel_value(value: Any) -> Any:
    """Normalise a raw value for openpyxl without changing its type class."""
    if isinstance(value, datetime):
        return to_excel_datetime(value)
    return value


def finalize_worksheet(ws) -> None:
    """Apply DD-MM-YYYY to every date cell still on a default format; strip tz."""
    for row in ws.iter_rows():
        for cell in row:
            value = cell.value
            if isinstance(value, datetime):
                if value.tzinfo is not None:
                    cell.value = to_excel_datetime(value)
                if cell.number_format in _DEFAULT_DATE_FORMATS:
                    has_time = (value.hour, value.minute, value.second) != (0, 0, 0)
                    cell.number_format = DATETIME_FORMAT if has_time else DATE_FORMAT
            elif isinstance(value, date):
                if cell.number_format in _DEFAULT_DATE_FORMATS:
                    cell.number_format = DATE_FORMAT


def finalize_workbook(wb) -> None:
    """Date formats on every sheet + force Excel/LibreOffice to recalculate formulas on open.

    openpyxl cannot store cached formula results, so ``fullCalcOnLoad`` makes the
    spreadsheet app compute every SUM when the file is opened.
    """
    for ws in wb.worksheets:
        finalize_worksheet(ws)
    try:
        from openpyxl.workbook.properties import CalcProperties

        if wb.calculation is None:
            wb.calculation = CalcProperties()
        wb.calculation.fullCalcOnLoad = True
    except Exception:  # pragma: no cover - older openpyxl without calc props
        pass
