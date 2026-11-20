"""Excel exporters write real typed cells (owner rule 2026-11-20).

Numbers are numeric cells with a number format (never pre-formatted strings),
dates are real date cells shown DD-MM-YYYY, identifiers stay text, and totals are
live formulas covering exactly the data rows. Pure in-memory: no DB needed
except where noted.
"""
from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from openpyxl import Workbook, load_workbook

from apps.license.tests.xlsx_eval import evaluate_formula, sum_range_of


def _load(response_or_bytes):
    content = response_or_bytes if isinstance(response_or_bytes, bytes) else response_or_bytes.content
    return load_workbook(io.BytesIO(content))


def _d(cell):
    """Exact Decimal of a numeric cell (the file stores the shortest decimal string)."""
    return Decimal(str(cell.value))


def _is_number(cell):
    return cell.data_type == "n" and isinstance(cell.value, (int, float, Decimal))


def _find_row(ws, predicate):
    for row in ws.iter_rows():
        if predicate(row):
            return row
    raise AssertionError("row not found")


# --------------------------------------------------------------------------
# Entitlement plan workbook
# --------------------------------------------------------------------------
def _entitlement_result():
    part = lambda q, r, c: {"quantity": q, "rate": r, "cif": c}  # noqa: E731
    return {
        "licence_number": "0311001234", "sion": "E1",
        "opening": {
            "total_cif": "10000.50", "total_quantity": "1234.567",
            "rows": [{
                "group_label": "G", "label": "Item", "percentage": "12.5", "quantity": "1234.567",
                "unit_price": "1.2345", "planned_cif": "1523.99", "cif_available": "0",
            }],
            "total_planned_cif": "1523.99",
        },
        "after": {
            "entitlements": [{
                "group_label": "G", "label": "Item",
                "opening": part("1234.567", "1.2345", "1523.99"),
                "boe_debited": part("-10.001", "1.2345", "-12.35"),
                "allotted": part("0", "0", "0"),
                "components": [{"code": "residual_cif", "cif": "-5.25"}],
                "balance": part("1224.566", "1.2345", "1511.64"),
            }],
            "total_balance_cif": "-1511.64", "remaining_licence_cif": "0",
        },
        "issues": [],
    }


def test_entitlement_plan_cells_are_typed_numbers():
    from apps.license.services.exporters.entitlement_plan_excel import render_entitlement_plan_xlsx

    ws = _load(render_entitlement_plan_xlsx(_entitlement_result())).active
    row = _find_row(ws, lambda r: r[0].value == "Total CIF")
    assert _is_number(row[1]) and _d(row[1]) == Decimal("10000.50")
    assert _is_number(row[3]) and _d(row[3]) == Decimal("1234.567")  # Decimal precision kept
    assert row[3].number_format == "#,##,##0.000"
    item = _find_row(ws, lambda r: r[0].value == "G" and r[1].value == "Item")
    assert [c.data_type for c in item[2:7]] == ["n"] * 5
    assert item[2].number_format == '0.00"%"'
    assert item[6].value == 0  # zero stays numeric
    boe = _find_row(ws, lambda r: r[0].value == "BOE Debited")
    assert _d(boe[1]) == Decimal("-10.001") and _d(boe[3]) == Decimal("-12.35")  # negatives preserved
    assert ws["A1"].value.startswith("Licence 0311001234")  # identifier text


# --------------------------------------------------------------------------
# Financial ledger (license list / detail) renderer
# --------------------------------------------------------------------------
def _ledger_payload():
    def lic(number, bal, pur, sale):
        return {
            "license_number": number, "license_type": "DFIA", "license_date": date(2026, 1, 1),
            "first_purchase_date": date(2026, 1, 2), "sion_norms": "E1",
            "current_balance": Decimal(bal), "purchase_bill_inr": Decimal(pur), "sale_bill_inr": Decimal(sale),
            "profit_loss_inr": Decimal(sale) - Decimal(pur), "has_purchase_bill": True,
            "display_transactions": [
                {"date": date(2026, 1, 2), "type": "PURCHASE", "party_name": "S", "purchase_amount": Decimal("100.125"),
                 "cif_inr": Decimal("9000"), "purchase_bill_amount": Decimal("5000")},
                {"date": date(2026, 1, 3), "type": "SALE", "party_name": "B", "sale_amount": Decimal("-20.5"),
                 "sale_bill_amount": Decimal("0")},
            ],
            "summary": {"total_purchase": Decimal("100.125"), "total_sale": Decimal("-20.5"),
                        "total_purchase_bill_inr": Decimal("5000"), "total_sale_bill_inr": Decimal("0"),
                        "current_balance": Decimal(bal), "total_profit_loss": Decimal("-5000")},
        }

    a, b = lic("0311000001", "70.5", "100", "-140"), lic("0311000002", "-20", "50", "30")
    company = {
        "company_name": "ACME", "licenses": [a, b],
        "sion_groups": [{"sion_label": "E1", "licenses": [a, b], "total_balance": Decimal("50.5")}],
        "total_balance": Decimal("50.5"),
    }
    return {"scope": "detail", "licenses": [a, b], "summary": {}, "company_groups": [company],
            "grand_total": {"total_balance": Decimal("50.5")}}


def test_financial_ledger_renderer_typed_cells_canonical_totals():
    from apps.license.services.exporters.financial_ledger_excel_renderer import render_financial_ledger_excel

    wb = load_workbook(render_financial_ledger_excel(_ledger_payload()))
    ws = wb["License Summary"]
    lic_row = next(r for r in ws.iter_rows() if r[2].value == "0311000001")
    assert lic_row[2].data_type == "s"  # licence number is text
    assert isinstance(lic_row[4].value, datetime) and lic_row[4].number_format == "DD-MM-YYYY"
    assert _is_number(lic_row[6]) and lic_row[6].value == Decimal("70.5")
    neg_row = next(r for r in ws.iter_rows() if r[2].value == "0311000002")
    assert neg_row[6].value == Decimal("-20")  # negative preserved, not abs/floored

    # Ledger totals are canonical DTO values (numeric cells), never SUM formulas:
    # licence rows carry the whole-licence balance, company totals each company's
    # share, and the canonical totals include an opening row that is not rendered.
    sion_total = next(r for r in ws.iter_rows() if r[0].value == "SION Total — E1")
    assert sion_total[6].value == Decimal("50.5") and _is_number(sion_total[6])
    grand = next(r for r in ws.iter_rows() if r[0].value == "GRAND TOTAL")
    assert grand[6].value == Decimal("50.5")

    detail = wb["Financial Trade Ledger"]
    total = next(r for r in detail.iter_rows() if r[4].value == "LICENSE TOTAL")
    assert total[8].value == Decimal("100.125") and _is_number(total[8])  # precision kept
    assert total[9].value == Decimal("-20.5")  # negative kept
    all_cells = [c for sheet in wb for row in sheet.iter_rows() for c in row]
    assert not any(isinstance(c.value, str) and c.value.startswith("=") for c in all_cells)
    purchase = next(r for r in detail.iter_rows() if r[6].value == "PURCHASE")
    assert purchase[3].number_format == "DD-MM-YYYY" and isinstance(purchase[3].value, datetime)
    assert purchase[8].value == Decimal("100.125") and purchase[8].data_type == "n"


# --------------------------------------------------------------------------
# Plan utilisation section (shared by single + bulk balance exports)
# --------------------------------------------------------------------------
def test_plan_utilization_section_numeric_metrics_and_group_sum_totals():
    from apps.license.services.exporters.planning_split_rows import render_plan_utilization_section

    groups = [
        {"available_quantity": Decimal("100.125"), "original_quantity": Decimal("40"), "original_cif_fc": Decimal("200.5"),
         "has_plan": True, "description": "A", "hs_code": "09042110", "serials": [1],
         "splits": [{"item_name": "X", "planned_quantity": 40, "unit_price": 5.0, "planned_cif_fc": 200.5}]},
        {"available_quantity": Decimal("10"), "original_quantity": Decimal("0"), "original_cif_fc": Decimal("0"),
         "has_plan": False, "description": "B", "hs_code": "0713", "serials": [2], "splits": []},
    ]
    ws = Workbook().active
    totals = {}
    render_plan_utilization_section(ws, 1, license_obj=None, license_balance=-400.0, plan_map={}, groups=groups,
                                    totals_out=totals)
    assert ws["B2"].value == -400.0 and ws["B2"].data_type == "n" and ws["B2"].number_format == '"$"#,##0.00'
    assert ws["B3"].number_format == "#,##0.000" and ws["D3"].number_format == "#,##0.000"
    assert ws["H3"].value == 1 and ws["H3"].number_format == "#,##0"  # plan entries (integer count)
    total_row = _find_row(ws, lambda r: r[0].value == "TOTALS")
    # Split sub-rows sit between group rows -> explicit group-cell SUM (no double counting).
    group_rows = [r[0].row for r in ws.iter_rows() if r[3].value in ("Planned", "Not Planned")]
    assert total_row[4].value == "=SUM(" + ",".join(f"E{n}" for n in group_rows) + ")"
    assert evaluate_formula(ws, total_row[4].value) == Decimal(str(totals["available_quantity"]))
    assert evaluate_formula(ws, total_row[7].value) == Decimal(str(totals["planned_cif"]))
    assert abs(float(evaluate_formula(ws, total_row[6].value)) - totals["remaining_quantity"]) < 1e-9
    split_row = next(r for r in ws.iter_rows() if str(r[0].value).startswith("  └"))
    assert split_row[1].value == 5.0 and split_row[1].number_format == '"@ $"#,##0.00"/unit"'
    assert split_row[5].data_type == "n" and split_row[7].data_type == "n"
    hs = next(r for r in ws.iter_rows() if r[3].value == "Planned")
    assert hs[1].value == "09042110" and hs[1].data_type == "s"  # HSN stays text


# --------------------------------------------------------------------------
# Active / expiring licences
# --------------------------------------------------------------------------
def _licence_report():
    item = {
        "item_id": 1, "serial_numbers": "1, 2", "item_name": "Cardamom", "hs_code": "09083110", "unit": "KGS",
        "quantity": 1234.567, "debited_quantity": 0.0, "allotted_quantity": -1.5, "available_quantity": 1233.067,
        "cif_fc": 100.25, "available_value": 99.0, "conditions": "",
    }
    lic = {
        "license_number": "0311009999", "notification_number": "N1", "license_date": "2026-03-01",
        "license_expiry_date": "2027-03-01", "ledger_date": "2026-04-05", "days_until_expiry": 100, "days_to_expiry": 100,
        "exporter": "E", "port": "P", "sion_norms": ["E1"], "balance_cif": -12.345,
        "import_summary": {"total_quantity": 1234.567, "debited_quantity": 0.0, "allotted_quantity": -1.5,
                           "available_quantity": 1233.067},
        "items": [dict(item), dict(item, item_name="Pepper", item_id=2)],
    }
    return {"report_period": {"from_date": "2026-01-01", "to_date": "2026-12-31"}, "licenses": [lic]}


@pytest.mark.parametrize("module,cls", [
    ("active_licenses_report", "ActiveLicensesReportView"),
    ("expiring_licenses_report", "ExpiringLicensesReportView"),
])
def test_licence_reports_typed_cells_and_sum_totals(module, cls):
    import importlib

    view = getattr(importlib.import_module(f"apps.license.api.views.{module}"), cls)()
    ws = _load(view.export_to_excel(_licence_report(), 30)).worksheets[0]

    lic_date = _find_row(ws, lambda r: r[0].value == "Notification Number:")
    assert isinstance(lic_date[3].value, datetime) and lic_date[3].number_format == "DD-MM-YYYY"
    bal = _find_row(ws, lambda r: r[2].value == "Balance CIF:" or r[2].value is not None and r[2].value == "Balance CIF:")
    assert bal[3].value == -12.345 and bal[3].data_type == "n"  # negative preserved, numeric
    ledger = _find_row(ws, lambda r: r[0].value == "Ledger Date:")
    assert isinstance(ledger[1].value, datetime) and ledger[1].number_format == "DD-MM-YYYY"

    items = [r for r in ws.iter_rows() if r[1].value in ("Cardamom", "Pepper") and r[2].value == "09083110"]
    first_item = items[0]
    assert first_item[2].data_type == "s"  # HS code text
    assert first_item[4].value == 1234.567 and first_item[4].number_format == "#,##0.000"
    assert first_item[6].value == -1.5 and first_item[6].data_type == "n"
    assert first_item[8].number_format == "#,##0.00" and first_item[9].number_format == "#,##0.00"

    total = _find_row(ws, lambda r: r[0].value == "TOTAL")
    for col in (4, 5, 6, 7):
        rng = sum_range_of(total[col].value)
        assert rng is not None and rng[1] == items[0][0].row and rng[2] == items[-1][0].row
        assert total[col].number_format == "#,##0.000"
    assert float(evaluate_formula(ws, total[4].value)) == pytest.approx(2 * 1234.567)

    grand = _find_row(ws, lambda r: r[0].value == "GRAND TOTAL")
    assert evaluate_formula(ws, grand[2].value) == Decimal("2469.134")
    assert all(grand[i].data_type == "f" or grand[i].value is not None for i in range(2, 8))
    norm_balance = _find_row(ws, lambda r: r[0].value == "Total Balance CIF:")
    assert float(evaluate_formula(ws, norm_balance[1].value)) == pytest.approx(-12.345)
    assert norm_balance[1].number_format == '"$"#,##0.00'


# --------------------------------------------------------------------------
# Inventory balance
# --------------------------------------------------------------------------
def test_inventory_balance_typed_cells_and_sum_totals():
    from apps.license.api.views.inventory_balance_report import InventoryBalanceReportView

    def item(name, q, a):
        return {"item_name": name, "hs_code": "0904", "unit": "KGS", "description": "d", "total_quantity": q,
                "debited_quantity": 0.0, "allotted_quantity": 0.0, "available_quantity": a,
                "total_cif_value": 10.5, "available_cif_value": -2.25, "license_count": 3}

    data = {
        "sion_norm": {"description": ""},
        "items": [item("A", 1234.567, 1000.0), item("B", 0.0, -5.5)],
        "summary": {"total_quantity": 1234.567, "total_debited": 0.0, "total_allotted": 0.0, "total_available": 994.5,
                    "total_cif_value": 21.0, "available_cif_value": -4.5, "total_items": 2},
    }
    ws = _load(InventoryBalanceReportView().export_to_excel(data, "E1")).active
    a = _find_row(ws, lambda r: r[0].value == "A")
    assert a[1].data_type == "s" and _is_number(a[4]) and a[4].number_format == "#,##0.000"
    assert a[8].number_format == "#,##0.00" and a[10].number_format == "#,##0"
    b = _find_row(ws, lambda r: r[0].value == "B")
    assert b[4].value == 0 and b[4].data_type == "n" and b[7].value == -5.5
    total = _find_row(ws, lambda r: r[0].value == "Total")
    assert sum_range_of(total[4].value) == ("E", a[0].row, b[0].row)
    assert float(evaluate_formula(ws, total[7].value)) == pytest.approx(994.5)
    assert float(evaluate_formula(ws, total[9].value)) == pytest.approx(-4.5)
    assert total[10].value == 2 and total[10].data_type == "n"  # item count, not a sum


# --------------------------------------------------------------------------
# Planned report
# --------------------------------------------------------------------------
def test_planned_report_typed_cells():
    from apps.license.api.views.planned_report import PlannedReportView

    item = {
        "license_id": 1, "is_restricted": True, "license_number": "0311007777", "license_date": "2026-01-02",
        "license_expiry_date": "2027-01-02", "ledger_date": None, "exporter_name": "E", "serial_number": 1,
        "hs_code": "09042110", "product_description": "P", "planned_item_name": "X", "available_quantity": 12.345,
        "available_balance": -3.5, "balance_cif": 100.0, "notes": "", "condition_sheet": "", "latest_transfer": "",
        "planned_quantity": 0, "unit_price": 1.2345, "planned_cif": 7.0,
    }
    response = PlannedReportView().export_to_excel({"items": [item]})
    ws = _load(response).worksheets[0]
    row = [c for c in ws[2]]
    assert row[1].data_type == "s" and row[8].value == "09042110" and row[8].data_type == "s"
    assert isinstance(row[2].value, datetime) and row[2].number_format == "DD-MM-YYYY"
    assert row[4].value is None and row[4].number_format == "DD-MM-YYYY"  # missing date stays blank, not a string
    assert row[11].value == 12.345 and row[11].number_format == "#,##0.000"
    assert row[12].value == -3.5 and row[12].data_type == "n"
    assert row[17].value == 0 and row[17].data_type == "n"  # zero stays numeric
    assert row[18].number_format == "#,##0.00##" and row[19].number_format == "#,##0.00"


# --------------------------------------------------------------------------
# Purchase & profit report (service-authoritative totals kept as numbers)
# --------------------------------------------------------------------------
def test_purchase_profit_typed_cells():
    from apps.license.api.views.license_purchase_profit_report import LicensePurchaseProfitReportView

    lic = {
        "license_number": "0311005555", "license_date": "2026-02-03", "expiry_date": "2027-02-03", "exporter": "E",
        "norms": ["E1"], "purchase_from": "S", "purchase_amount": 1000.5, "purchase_usd": 12.5, "sale_amount": 0.0,
        "sale_usd": 0.0, "profit_loss": -1000.5, "trade_balance_usd": 12.5,
    }
    data = {
        "summary": {"total_licenses": 1, "purchase_amount": 1000.5, "purchase_usd": 12.5, "total_sale_amount": 0.0,
                    "total_sale_usd": 0.0, "total_profit_loss": -1000.5, "trade_balance_usd": 12.5},
        "licenses": [lic],
        "item_matrix": {"headers": ["Cardamom"], "rows": [dict(lic, items={"Cardamom": {"qty": 1234.567, "cif": 5.5, "bill": 9.0}})],
                        "totals": {"Cardamom": {"qty": 1234.567, "cif": 5.5, "bill": 9.0}}},
    }
    request = SimpleNamespace(user=SimpleNamespace(username="tester", get_full_name=lambda: "Tester"))
    response = LicensePurchaseProfitReportView().export_to_excel(request, data, None, None, "E1", None, None)
    wb = _load(response)
    ws = wb["License Summary"]
    metrics = {r[0].value: r[1] for r in ws.iter_rows(min_row=1, max_row=15) if r[0].value}
    assert metrics["Total Licenses"].number_format == "#,##0" and metrics["Total Licenses"].value == 1
    assert metrics["Profit / Loss"].value == -1000.5 and metrics["Profit / Loss"].data_type == "n"
    row = _find_row(ws, lambda r: r[0].value == "0311005555")
    assert row[0].data_type == "s"
    assert isinstance(row[1].value, datetime) and row[1].number_format == "DD-MM-YYYY"
    assert _is_number(row[6]) and row[6].number_format == "#,##0.00" and row[10].value == -1000.5
    total = _find_row(ws, lambda r: r[0].value == "GRAND TOTAL")
    assert _is_number(total[6]) and total[10].value == -1000.5
    matrix = wb["Item Utilization Matrix"]
    data_row = _find_row(matrix, lambda r: r[0].value == "0311005555")
    assert data_row[12].value == 1234.567 and data_row[12].number_format == "#,##0.000"
    assert data_row[13].number_format == "#,##0.00" and data_row[14].value == 9.0


# --------------------------------------------------------------------------
# Item pivot intelligence workbook
# --------------------------------------------------------------------------
def test_item_pivot_intelligence_export_types():
    from apps.license.services.item_pivot_intelligence_export import SHEETS, workbook_response

    columns = SHEETS["Licences"][1]
    rows = [{"license_number": "0311000042", "sion": "E1", "company": "C", "expiry_date": "2027-05-06",
             "original_cif": "1234.567", "available_cif": "-10.50", "planned_cif": "0", "utilisation_percent": "12.5",
             "is_over_utilised": True}]
    ws = _load(workbook_response([("Licences", columns, rows)]).content)["Licences"]
    header = [c.value for c in ws[1]]
    row = ws[2]
    lic = row[header.index("License Number")]
    assert lic.value == "0311000042" and lic.data_type == "s"  # digit-only identifier stays text
    exp = row[header.index("Expiry Date")]
    assert isinstance(exp.value, datetime) and exp.number_format == "DD-MM-YYYY"
    assert row[header.index("Original Cif")].value == 1234.567
    assert row[header.index("Available Cif")].value == Decimal("-10.50")
    assert row[header.index("Planned Cif")].value == 0 and row[header.index("Planned Cif")].data_type == "n"
    assert row[header.index("Utilisation Percent")].number_format == '0.00"%"'


# --------------------------------------------------------------------------
# Balance ledger sheets (financial / customs / timeline)
# --------------------------------------------------------------------------
def test_balance_ledger_sheets_typed_cells():
    from apps.license.services.exporters.balance_excel_ledger_sheets import (
        _write_customs_ledger_sheet, _write_financial_ledger_sheet, _write_timeline_sheet,
    )

    fin_row = {
        "sr": 1, "date": date(2026, 5, 1), "type": "BOE", "document_number": "D1", "boe_number": "9876543",
        "boe_date": date(2026, 5, 2), "company": "C", "item_name": "I", "invoice_numbers": [], "qty": Decimal("1234.567"),
        "cif_usd": Decimal("-50.25"), "cif_inr": None, "credit": Decimal("0"), "debit": Decimal("50.25"),
        "running_balance": Decimal("-10.5"), "remarks": "", "row_kind": "boe", "children": [
            {"type": "alloc", "boe_number": "9876543", "boe_date": date(2026, 5, 2), "qty": Decimal("1"),
             "cif_usd": Decimal("2.5"), "cif_inr": None},
        ],
    }
    fin_summary = {
        "missing_purchase_warning": {"show_warning": False}, "opening_balance": Decimal("1"), "total_boe_debit": Decimal("0"),
        "total_allotment_debit": Decimal("0"), "total_trade_debit": Decimal("0"), "computed_balance": Decimal("-10.5"),
        "engine_balance": Decimal("-10.5"), "difference": Decimal("0"), "tolerance": Decimal("0.01"), "mismatched": False,
    }
    cust_row = dict(fin_row, row_kind="customs_boe")
    cust_summary = {"opening_balance": Decimal("1"), "total_boe_cif": Decimal("2"), "total_pending_allotment_cif": Decimal("0"),
                    "computed_balance": Decimal("-1"), "engine_balance": Decimal("-1"), "mismatched": False}
    events = [{"sr": 1, "date": datetime(2026, 5, 1, 13, 45), "label": "E", "quantity": Decimal("3.125"), "cif": None,
               "children": []}]
    wb = Workbook()
    wb.remove(wb.active)
    _write_financial_ledger_sheet(wb, [fin_row], fin_summary)
    _write_customs_ledger_sheet(wb, [cust_row], cust_summary)
    _write_timeline_sheet(wb, events)
    from apps.core.exporters.excel.cell_formats import finalize_workbook
    finalize_workbook(wb)
    wb = load_workbook(io.BytesIO(_save(wb)))

    fin = wb["Financial Ledger"]
    row = _find_row(fin, lambda r: r[3].value == "D1")
    assert isinstance(row[1].value, datetime) and row[1].number_format == "DD-MM-YYYY"
    assert isinstance(row[5].value, datetime) and row[5].number_format == "DD-MM-YYYY"
    assert row[4].value == "9876543" and row[4].data_type == "s"  # BOE number text
    assert _d(row[9]) == Decimal("1234.567") and _is_number(row[9])
    assert _d(row[10]) == Decimal("-50.25")  # negative preserved
    assert row[12].value is None and _d(row[13]) == Decimal("50.25")  # zero credit -> blank, debit numeric
    assert _d(row[14]) == Decimal("-10.5") and row[14].number_format == "#,##0.00"
    assert any(_is_number(c) and c.value == Decimal("-10.5") for r in fin.iter_rows() for c in r)  # summary values

    customs = wb["Customs Ledger"]
    crow = _find_row(customs, lambda r: r[3].value == "D1")
    assert crow[1].number_format == "DD-MM-YYYY" and _is_number(crow[8]) and _is_number(crow[12])

    tl = wb["Timeline"]
    trow = _find_row(tl, lambda r: r[2].value == "E")
    assert isinstance(trow[1].value, datetime) and trow[1].number_format == "DD-MM-YYYY HH:MM"
    assert _d(trow[5]) == Decimal("3.125") and trow[6].value is None


def _save(wb):
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# --------------------------------------------------------------------------
# DB-backed: full single-licence workbook (Reconciliation + Audit Log sheets)
# --------------------------------------------------------------------------
from django.test import TestCase  # noqa: E402

from apps.license.models import LicenseExportItemModel  # noqa: E402
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin  # noqa: E402


class BalanceWorkbookCellTypeTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def test_reconciliation_header_and_totals_are_typed(self):
        from apps.license.services.exporters.license_balance_excel import build_balance_excel

        company = self.make_company()
        license_obj = self.make_license(company)
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("10000.00"))
        wb = _load(build_balance_excel(license_obj))
        ws = wb["Reconciliation"]
        # "Label: value" look is kept by a literal prefix in the number format; the value is a real date/number.
        assert ws["A1"].value == f"License No: {license_obj.license_number}" and ws["A1"].data_type == "s"
        assert isinstance(ws["B1"].value, datetime) and ws["B1"].number_format == '"License Date: "DD-MM-YYYY'
        assert isinstance(ws["C1"].value, datetime) and ws["C1"].number_format == '"Expiry Date: "DD-MM-YYYY'
        assert _is_number(ws["D1"]) and ws["D1"].number_format == '"Total CIF: "#,##0.00'
        rec = _find_row(ws, lambda r: r[0].value == "Difference")
        assert _is_number(rec[1]) and rec[1].number_format == "#,##0.00"


def test_financial_ledger_multi_company_licence_totals_not_double_counted():
    """Regression (CIF audit B1): a licence under two companies must not inflate totals."""
    from apps.license.services.exporters.financial_ledger_excel_renderer import render_financial_ledger_excel

    payload = _ledger_payload()
    shared = payload["licenses"][0]  # whole-licence balance 70.5, listed under both companies
    payload["company_groups"] = [
        {"company_name": "BUYER CO", "sion_groups": [{"sion_label": None, "licenses": [shared]}],
         "total_balance": Decimal("100")},
        {"company_name": "SELLER CO", "sion_groups": [{"sion_label": None, "licenses": [shared]}],
         "total_balance": Decimal("-29.5")},
    ]
    payload["grand_total"] = {"total_balance": Decimal("70.5")}
    ws = load_workbook(render_financial_ledger_excel(payload))["License Summary"]
    by_label = {r[0].value: r[6].value for r in ws.iter_rows() if r[0].value}
    assert by_label["Total — BUYER CO"] == Decimal("100")
    assert by_label["Total — SELLER CO"] == Decimal("-29.5")
    assert by_label["GRAND TOTAL"] == Decimal("70.5")  # not 141 (70.5 counted twice)
