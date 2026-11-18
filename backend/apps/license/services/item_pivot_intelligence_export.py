"""Excel workbooks for the Item Pivot intelligence views (same data as the UI)."""
from __future__ import annotations

import io
from decimal import Decimal, InvalidOperation

from django.http import HttpResponse


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
            ws.append([_cell(row.get(c)) for c in columns])
        ws.freeze_panes = "A2"
    buffer = io.BytesIO()
    wb.save(buffer)
    response = HttpResponse(buffer.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="item_pivot_intelligence.xlsx"'
    return response


