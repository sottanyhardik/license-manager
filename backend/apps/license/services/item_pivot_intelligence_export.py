"""Excel workbooks for the Item Pivot intelligence views (same data as the UI)."""
from __future__ import annotations

import io
from decimal import Decimal, InvalidOperation

from django.http import HttpResponse

from apps.core.exporters.excel.cell_formats import (
    AMOUNT_FORMAT,
    INTEGER_FORMAT,
    PERCENT_POINTS_FORMAT,
    QUANTITY_FORMAT,
    RATE_FORMAT,
    finalize_workbook,
    parse_display_date,
    to_number,
    write_date,
    write_number,
    write_text,
)

# Identifier columns stay text (leading zeros / digit-only licence & HSN codes).
TEXT_COLUMNS = {"license_number", "hsn_codes"}
DATE_COLUMNS = {"expiry_date"}
INTEGER_COLUMNS = {"source_record_count", "eligible_licences", "rank", "rule_priority"}


def _column_format(column: str) -> str | None:
    """Number format for a numeric business column (None -> not a numeric column)."""
    if column in INTEGER_COLUMNS:
        return INTEGER_FORMAT
    if "percent" in column:
        return PERCENT_POINTS_FORMAT
    if "unit_price" in column:
        return RATE_FORMAT
    if column.endswith("_qty") or "_qty_" in column or column.endswith("quantity"):
        return QUANTITY_FORMAT
    if "cif" in column:
        return AMOUNT_FORMAT
    return None


def _write_cell(cell, column: str, value) -> None:
    if column in TEXT_COLUMNS:
        # Raw string stays untouched (``_cell`` would turn "0311000042" into a Decimal).
        write_text(cell, value if isinstance(value, str) or value is None else _cell(value))
        return
    if column in DATE_COLUMNS and parse_display_date(value) is not None:
        write_date(cell, value)
        return
    fmt = _column_format(column)
    if fmt is not None and not isinstance(value, bool) and to_number(value) is not None:
        write_number(cell, value, fmt)
        return
    cell.value = _cell(value)


def _cell(value):
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value)
    if isinstance(value, dict):
        return ", ".join(f"{k}: {v}" for k, v in value.items())
    if isinstance(value, str):
        try:
            return Decimal(value) if value and value.replace(".", "", 1).lstrip("-").isdigit() else value
        except InvalidOperation:
            return value
    return value


SHEETS = {
    "Products": ("products", ["product", "sion", "kind", "hsn_codes", "aliases", "source_record_count", "eligible_licences",
                              "entitlement_qty", "allotted_qty", "debited_qty", "billed_qty", "balance_qty", "max_unit_price",
                              "planned_qty", "planned_cif", "utilisation_percent", "mapping_basis", "mapping_review", "status_counts"]),
    "Licences": ("licences", ["license_number", "sion", "company", "expiry_date", "purchase_status", "original_cif", "boe_cif",
                              "allotment_cif", "billed_cif", "other_adjustments_cif", "available_cif", "is_over_utilised",
                              "planned_cif", "final_balance_cif", "utilisation_percent"]),
    "Eligibility": ("eligibility", ["license_number", "product", "sion", "kind", "status", "entitlement_qty", "debited_qty",
                                    "allotted_qty", "billed_qty", "balance_qty", "max_unit_price", "planned_qty", "planned_cif",
                                    "licence_available_cif", "licence_final_balance_cif", "reasons", "references"]),
}
REC_COLUMNS = ["rank", "license_number", "expiry_date", "sion", "product", "rule_priority", "unit_price", "recommended_qty",
               "recommended_cif", "existing_qty", "existing_cif", "additional_qty", "additional_cif", "licence_available_cif",
               "remaining_licence_cif_after", "cif_status", "reason", "alternatives"]


def workbook_response(sheets: list[tuple[str, list[str], list[dict]]]) -> HttpResponse:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    wb.remove(wb.active)
    for title, columns, rows in sheets:
        ws = wb.create_sheet(title)
        ws.append([c.replace("_", " ").title() for c in columns])
        for cell in ws[1]:
            cell.font = Font(bold=True)
        for row in rows:
            ws.append([None] * len(columns))
            for idx, c in enumerate(columns, start=1):
                _write_cell(ws.cell(row=ws.max_row, column=idx), c, row.get(c))
        ws.freeze_panes = "A2"
    finalize_workbook(wb)
    buffer = io.BytesIO()
    wb.save(buffer)
    response = HttpResponse(buffer.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="item_pivot_intelligence.xlsx"'
    return response


