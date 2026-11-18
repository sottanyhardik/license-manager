"""Excel rendering of the entitlement planning report (spreadsheet layout).

Pure presentation of an ``EntitlementPlanningService.build`` result: it never
recomputes a figure.  Numbers are written as numbers (2-dp format) so the
sheet totals in Excel exactly as on screen.
"""
from __future__ import annotations

import io
from decimal import Decimal

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

BOLD = Font(bold=True)
HEAD = PatternFill("solid", fgColor="E8EEF7")
NUM = "#,##,##0.00"
RATE = "0.00"


def _n(value):
    return float(Decimal(value)) if value not in (None, "") else None


def _row(ws, values, *, bold=False, fill=None, formats=None):
    ws.append(values)
    r = ws.max_row
    for idx, _ in enumerate(values, start=1):
        cell = ws.cell(row=r, column=idx)
        if bold:
            cell.font = BOLD
        if fill:
            cell.fill = fill
        if formats and idx in formats and isinstance(cell.value, (int, float)):
            cell.number_format = formats[idx]
            cell.alignment = Alignment(horizontal="right")


def render_entitlement_plan_xlsx(result: dict) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Planning"
    opening = result["opening"]
    _row(ws, [f"Licence {result['licence_number']} · {result['sion']}"], bold=True)
    _row(ws, ["OPENING PLANNING"], bold=True)
    _row(ws, ["Total CIF", _n(opening["total_cif"]), "Total Qty", _n(opening["total_quantity"])],
         formats={2: NUM, 4: NUM})
    _row(ws, ["Group", "Product / Entitlement", "Split %", "Total Qty", "Unit Price", "Planned CIF", "CIF Available"],
         bold=True, fill=HEAD)
    fmt = {4: NUM, 5: RATE, 6: NUM, 7: NUM}
    for row in opening["rows"]:
        _row(ws, [row["group_label"], row["label"], _n(row["percentage"]), _n(row["quantity"]),
                  _n(row["unit_price"]), _n(row["planned_cif"]), _n(row["cif_available"])], formats=fmt)
    _row(ws, ["", "Total", None, _n(opening["total_quantity"]), None, _n(opening["total_planned_cif"]), None],
         bold=True, formats=fmt)

    ws.append([])
    _row(ws, ["AFTER BOE DEBITS AND ALLOTTED"], bold=True)
    fmt = {2: NUM, 3: RATE, 4: NUM}
    for ent in result["after"]["entitlements"]:
        ws.append([])
        _row(ws, [f"{ent['group_label']} — {ent['label']}", "Quantity", "Rate", "CIF"], bold=True, fill=HEAD)
        for label, key in (("Opening", "opening"), ("BOE Debited", "boe_debited"), ("Allotted", "allotted")):
            part = ent[key]
            _row(ws, [label, _n(part["quantity"]), _n(part["rate"]), _n(part["cif"])], formats=fmt)
        for comp in ent["components"]:
            _row(ws, [comp["code"].replace("_", " ").title(), None, None, _n(comp["cif"])], formats=fmt)
        bal = ent["balance"]
        _row(ws, ["Balance", _n(bal["quantity"]), _n(bal["rate"]), _n(bal["cif"])], bold=True, formats=fmt)
    ws.append([])
    _row(ws, ["Total balance CIF", _n(result["after"]["total_balance_cif"])], bold=True, formats={2: NUM})
    _row(ws, ["Remaining licence CIF", _n(result["after"]["remaining_licence_cif"])], formats={2: NUM})
    if result["issues"]:
        ws.append([])
        _row(ws, ["Warnings"], bold=True)
        for issue in result["issues"]:
            ws.append([("BLOCKING · " if issue["blocking"] else "") + issue["code"], issue["message"]])
    for col, width in zip("ABCDEFG", (34, 30, 12, 18, 12, 18, 18)):
        ws.column_dimensions[col].width = width
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
