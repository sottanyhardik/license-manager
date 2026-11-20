"""
Golden (characterization) tests for the BOE export endpoint
``GET /api/bill-of-entries/export/``.

Every export format is rendered through the real HTTP/permission layer from a
deterministic fixture and reduced to a JSON snapshot (sheet names, merged
cells, cell value + python type + number format + basic styling, column
widths; for PDF the extracted page text). Snapshots live in ``golden/`` and
must stay byte-for-byte identical across refactors of the export code.

Regenerate deliberately with ``UPDATE_BOE_GOLDEN=1`` (never in CI).
Run-time dates ("today") are normalised to ``<TODAY>`` / ``<GENERATED>``.
"""
import json
import os
import re
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import openpyxl
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.bill_of_entry.tests.test_boe_api_contract import BOE_URL, LOCMEM_CACHES, BoeApiFixtureMixin
from apps.core.models import CompanyModel, ExchangeRateModel, PortModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel

GOLDEN_DIR = Path(__file__).parent / "golden"
UPDATE = os.environ.get("UPDATE_BOE_GOLDEN") == "1"
DEBIT = "D"

XLSX_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _norm_text(text):
    today = datetime.now()
    text = re.sub(r"Generated on: \d{2}-\d{2}-\d{4} \d{2}:\d{2}", "Generated on: <GENERATED>", text)
    text = text.replace(today.strftime("%d-%m-%Y"), "<TODAY>")
    return text


def _cell_value(value):
    if isinstance(value, str):
        return _norm_text(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def snapshot_xlsx(content):
    wb = openpyxl.load_workbook(BytesIO(content))
    sheets = []
    for ws in wb.worksheets:
        cells = []
        for row in ws.iter_rows():
            for c in row:
                if c.value is None and not c.has_style:
                    continue
                cells.append({
                    "ref": c.coordinate,
                    "value": _cell_value(c.value),
                    "type": type(c.value).__name__,
                    "number_format": c.number_format,
                    "bold": bool(c.font and c.font.b),
                    "fill": c.fill.fgColor.rgb if c.fill and c.fill.fill_type else None,
                    "h_align": c.alignment.horizontal if c.alignment else None,
                    "bordered": bool(c.border and c.border.left and c.border.left.style),
                })
        sheets.append({
            "title": ws.title,
            "dimensions": ws.dimensions,
            "max_row": ws.max_row,
            "max_column": ws.max_column,
            "merged": sorted(str(m) for m in ws.merged_cells.ranges),
            "column_widths": {k: v.width for k, v in sorted(ws.column_dimensions.items())},
            "freeze_panes": ws.freeze_panes,
            "auto_filter": ws.auto_filter.ref,
            "cells": cells,
        })
    return {"sheet_names": wb.sheetnames, "sheets": sheets}


def snapshot_pdf(content):
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(content))
    pages = [_norm_text(p.extract_text() or "") for p in reader.pages]
    return {"starts_with_pdf_magic": content[:5] == b"%PDF-", "page_count": len(pages), "pages": pages}


def _dump(data):
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


@override_settings(CACHES=LOCMEM_CACHES)
class BoeExportGoldenTests(BoeApiFixtureMixin, TestCase):
    def setUp(self):
        self.user = self.make_role_user("BOE_VIEWER")
        self.client = self.client_for(self.user)

    # -- deterministic fixture ------------------------------------------
    def build_dataset(self):
        acme = CompanyModel.objects.create(iec="1111111111", name="Acme Foods Pvt Ltd")
        beta = CompanyModel.objects.create(iec="2222222222", name="Beta Traders")
        mum = PortModel.objects.create(code="INMUN1", name="Mundra")
        che = PortModel.objects.create(code="INMAA1", name="Chennai")
        lic1 = LicenseDetailsModel.objects.create(
            license_number="0311000001", license_date=date(2024, 1, 10),
            license_expiry_date=date(2026, 1, 10), exporter=acme, port=mum)
        lic2 = LicenseDetailsModel.objects.create(
            license_number="0311000002", license_date=date(2024, 2, 20),
            license_expiry_date=date(2026, 2, 20), exporter=beta, port=che)
        items = {}
        for lic, serial in ((lic1, 1), (lic1, 2), (lic2, 1)):
            items[(lic.license_number, serial)] = LicenseImportItemsModel.objects.create(
                license=lic, serial_number=serial, description=f"Item {serial}",
                quantity=Decimal("5000.000"), available_quantity=Decimal("5000.000"))

        def boe(number, d, company, port, product, rate, invoice, rows):
            b = BillOfEntryModel.objects.create(
                company=company, port=port, bill_of_entry_number=number, bill_of_entry_date=d,
                exchange_rate=rate, product_name=product, invoice_no=invoice)
            for key, cif_fc, cif_inr, qty in rows:
                RowDetails.objects.create(
                    bill_of_entry=b, sr_number=items[key], transaction_type=DEBIT,
                    cif_fc=Decimal(cif_fc), cif_inr=Decimal(cif_inr), qty=Decimal(qty))
            return b

        boe("9000001", date(2025, 3, 1), acme, mum, "sugar refined", Decimal("84.5000"), "INV-1",
            [(("0311000001", 1), "100.50", "8492.25", "1000.125"),
             (("0311000001", 2), "20.25", "1711.13", "250.500")])
        boe("9000002", date(2025, 3, 5), acme, che, "Sugar Refined ", Decimal("84.5000"), "",
            [(("0311000001", 1), "300.00", "25350.00", "2000.000")])
        boe("9000003", date(2025, 3, 2), beta, mum, "palm oil", Decimal("0.0000"), "INV-3",
            [(("0311000002", 1), "50.75", "4288.88", "500.250")])
        boe("9000004", date(2025, 3, 2), beta, che, "palm oil", Decimal("83.1234"), None,
            [(("0311000002", 1), "10.10", "839.58", "100.100")])
        ExchangeRateModel.objects.create(
            date=date(2025, 3, 1), usd=Decimal("84.5000"), euro=Decimal("91.2500"),
            pound_sterling=Decimal("107.1000"), chinese_yuan=Decimal("11.6500"))
        return {"acme": acme, "beta": beta}

    # -- golden plumbing --------------------------------------------------
    def assert_golden(self, name, data):
        path = GOLDEN_DIR / f"{name}.json"
        rendered = _dump(data)
        if UPDATE or not path.exists():
            GOLDEN_DIR.mkdir(exist_ok=True)
            path.write_text(rendered, encoding="utf-8")
            if not UPDATE:
                self.fail(f"golden {name} did not exist and was created; re-run")
            return
        self.assertEqual(path.read_text(encoding="utf-8"), rendered, f"golden mismatch: {name}")

    def export(self, fmt, **params):
        params = {"_export": fmt, **params} if fmt else params
        return self.client.get(BOE_URL + "export/", params)

    def header_snapshot(self, response):
        return {
            "status": response.status_code,
            "content_type": _norm_text(response["Content-Type"]),
            "disposition": _norm_text(response.get("Content-Disposition", "")),
        }

    def xlsx_golden(self, name, fmt, **params):
        response = self.export(fmt, **params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], XLSX_CT)
        self.assert_golden(name, {"response": self.header_snapshot(response), "workbook": snapshot_xlsx(response.content)})

    # -- grouped xlsx ------------------------------------------------------
    def test_grouped_xlsx_full(self):
        self.build_dataset()
        self.xlsx_golden("grouped_xlsx_full", "xlsx")

    def test_grouped_xlsx_empty(self):
        self.xlsx_golden("grouped_xlsx_empty", "xlsx")

    def test_grouped_xlsx_company_filter(self):
        companies = self.build_dataset()
        self.xlsx_golden("grouped_xlsx_company_filter", "xlsx", company=companies["beta"].id)

    def test_grouped_xlsx_date_filter(self):
        self.build_dataset()
        self.xlsx_golden("grouped_xlsx_date_filter", "xlsx", bill_of_entry_date_after="2025-03-02",
                         bill_of_entry_date_before="2025-03-02")

    def test_grouped_xlsx_all_invoice_states(self):
        self.build_dataset()
        self.xlsx_golden("grouped_xlsx_is_invoice_all", "xlsx", is_invoice="all")

    def test_grouped_xlsx_invoiced_only(self):
        self.build_dataset()
        self.xlsx_golden("grouped_xlsx_is_invoice_true", "xlsx", is_invoice="true")

    # -- port xlsx ---------------------------------------------------------
    def test_port_xlsx_full(self):
        self.build_dataset()
        self.xlsx_golden("port_xlsx_full", "port_xlsx")

    def test_port_xlsx_all_invoice_states(self):
        self.build_dataset()
        self.xlsx_golden("port_xlsx_is_invoice_all", "port_xlsx", is_invoice="all")

    def test_port_xlsx_empty(self):
        self.xlsx_golden("port_xlsx_empty", "port_xlsx")

    def test_port_xlsx_company_filter(self):
        companies = self.build_dataset()
        self.xlsx_golden("port_xlsx_company_filter", "port_xlsx", company=companies["acme"].id)

    # -- grouped pdf (extracted text) ----------------------------------------
    def pdf_golden(self, name, **params):
        response = self.export("pdf", **params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assert_golden(name, {"response": self.header_snapshot(response), "pdf": snapshot_pdf(response.content)})

    def test_grouped_pdf_full(self):
        self.build_dataset()
        self.pdf_golden("grouped_pdf_full")

    def test_grouped_pdf_all_invoice_states(self):
        self.build_dataset()
        self.pdf_golden("grouped_pdf_is_invoice_all", is_invoice="all")

    def test_grouped_pdf_empty(self):
        self.pdf_golden("grouped_pdf_empty")

    def test_grouped_pdf_company_filter(self):
        companies = self.build_dataset()
        self.pdf_golden("grouped_pdf_company_filter", company=companies["beta"].id)

    def test_default_format_is_pdf(self):
        self.build_dataset()
        response = self.export(None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

    # -- errors / permissions ----------------------------------------------------
    def test_invalid_format_is_400_plain_text(self):
        response = self.export("csv")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response["Content-Type"].startswith("text/plain"))
        self.assertEqual(response.content.decode(), "Invalid export format. Use 'pdf', 'xlsx', or 'port_xlsx'.")

    def test_no_role_user_is_403_for_every_format(self):
        client = self.client_for(self.make_role_user())
        for fmt in ("pdf", "xlsx", "port_xlsx"):
            self.assertEqual(client.get(BOE_URL + "export/", {"_export": fmt}).status_code, 403, fmt)

    def test_unauthenticated_is_denied(self):
        from rest_framework.test import APIClient
        self.assertIn(APIClient().get(BOE_URL + "export/").status_code, (401, 403))

    def test_boes_without_item_details_are_excluded(self):
        self.build_dataset()
        acme = CompanyModel.objects.get(iec="1111111111")
        BillOfEntryModel.objects.create(
            company=acme, bill_of_entry_number="9999999", bill_of_entry_date=date(2025, 4, 1))
        snap = snapshot_xlsx(self.export("port_xlsx").content)
        values = [c["value"] for c in snap["sheets"][0]["cells"]]
        self.assertNotIn("9999999", values)
        # Default is_invoice=false hides invoiced BOEs: only 9000002 / 9000004 remain.
        self.assertEqual(snap["sheets"][0]["max_row"], 2 + 2)

    # -- query count (iteration-1 prefetch seeding) --------------------------------
    def _queries(self, fmt):
        self.export(fmt, is_invoice="all")  # warm-up
        with CaptureQueriesContext(connection) as ctx:
            response = self.export(fmt, is_invoice="all")
        self.assertEqual(response.status_code, 200)
        return [q["sql"] for q in ctx.captured_queries]

    def test_query_count_constant_in_boe_count_and_no_per_boe_sums(self):
        self.build_dataset()
        for fmt in ("xlsx", "port_xlsx", "pdf"):
            four = self._queries(fmt)
            per_boe_sum = [s for s in four if "SUM(" in s and '"bill_of_entry_rowdetails"."bill_of_entry_id" =' in s]
            self.assertEqual(per_boe_sum, [], fmt)
            acme = CompanyModel.objects.get(iec="1111111111")
            for i in range(5):
                b = BillOfEntryModel.objects.create(
                    company=acme, bill_of_entry_number=f"98000{i}", bill_of_entry_date=date(2025, 5, 1 + i),
                    product_name="extra")
                RowDetails.objects.create(
                    bill_of_entry=b, sr_number=LicenseImportItemsModel.objects.first(),
                    transaction_type=DEBIT, cif_fc=Decimal("1.00"), cif_inr=Decimal("84.50"), qty=Decimal("1.000"))
            nine = self._queries(fmt)
            self.assertEqual(len(four), len(nine), f"{fmt}: query count must not grow with BOE count")
            BillOfEntryModel.objects.filter(bill_of_entry_number__startswith="98000").delete()
