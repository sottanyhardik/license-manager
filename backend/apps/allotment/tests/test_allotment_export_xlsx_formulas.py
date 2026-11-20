"""Grouped allotment Excel export: live SUM formulas, real date cells, text identifiers."""
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace as NS
from unittest import mock

import openpyxl
from django.test import TestCase

from apps.allotment.api.views_export import add_grouped_export_action


class _Dummy:
    pass


def _detail(dfia_no, qty, cif):
    lic = NS(license_number=dfia_no, exporter=NS(name="EXP"), license_date=date(2024, 2, 29), port=NS(code="NSA"))
    return NS(item=NS(license=lic, serial_number=1), qty=qty, cif_fc=cif)


def _allotment(value, qty, details, created):
    d = [_detail(f"03000{i}", Decimal("5"), Decimal("1.5")) for i in range(details)]
    return NS(
        company=NS(name="ACME"), port=NS(code="NSA"), item_name="Sugar", required_quantity=qty,
        unit_value_per_unit=Decimal("2"), required_value=value, exchange_rate=Decimal("80"),
        invoice="INV-001", estimated_arrival_date=date(2024, 3, 31), created_on=created,
        is_boe=False, is_approved=False,
        allotment_details=NS(all=lambda d=d: d),
    )


class _QS(list):
    pass


class AllotmentXlsxFormulaTests(TestCase):
    def _export(self, allotments):
        cls = add_grouped_export_action(_Dummy)
        view = cls()
        with mock.patch("apps.allotment.api.views_export.ExchangeRateModel.get_active_rate", return_value=None):
            response = view._export_grouped_xlsx(_QS(allotments), "AT")
        return openpyxl.load_workbook(BytesIO(response.content)).active

    def test_totals_are_formulas_over_exact_data_rows(self):
        allotments = [
            _allotment(Decimal("100.10"), Decimal("10.6"), 2, datetime(2024, 1, 31, 20, 0, tzinfo=dt_timezone.utc)),
            _allotment(Decimal("50.05"), Decimal("20.7"), 1, datetime(2024, 12, 31, 12, 0, tzinfo=dt_timezone.utc)),
        ]
        ws = self._export(allotments)
        total_rows = [r for r in range(1, ws.max_row + 1) if ws.cell(r, 3).value == "Total Quantity"]
        self.assertEqual(len(total_rows), 1)
        tr = total_rows[0]
        # Table data starts right after the two header rows and ends right before the total row.
        header_row = next(r for r in range(1, tr) if ws.cell(r, 1).value == "Sr No")
        first, last = header_row + 2, tr - 1
        for col, letter in ((4, "D"), (6, "F"), (7, "G")):
            self.assertEqual(ws.cell(tr, col).value, f"=SUM({letter}{first}:{letter}{last})")
        # The DFIA subtotal row ("Total DFIA allocation") lives in the DFIA columns, outside D/F/G.
        self.assertTrue(any(ws.cell(r, 12).value == "Total DFIA allocation" for r in range(first, last + 1)))
        for r in range(first, last + 1):
            for col in (4, 6, 7):
                self.assertNotIsInstance(ws.cell(r, col).value, str)
        # Grand total sums only the item/port total rows.
        gt = next(r for r in range(tr, ws.max_row + 1) if ws.cell(r, 1).value == "Grand Total:")
        self.assertEqual(ws.cell(gt, 4).value, f'=SUMIF(C{tr}:C{tr},"Total Quantity",D{tr}:D{tr})')
        self.assertEqual(ws.cell(gt, 6).value, f'=SUMIF(C{tr}:C{tr},"Total Quantity",F{tr}:F{tr})')
        # Quantities are the raw Decimals (not int-truncated) so the SUM is exact (CIF audit S1).
        qtys = [Decimal(str(ws.cell(r, 4).value)) for r in range(first, last + 1) if ws.cell(r, 4).value is not None]
        self.assertEqual(sum(qtys), Decimal("31.3"))  # old int() rows summed to 30
        self.assertTrue(all(ws.cell(r, 4).number_format == "#,##0.000" for r in range(first, last + 1) if ws.cell(r, 4).value is not None))

    def test_dates_are_real_cells_and_ids_are_text(self):
        ws = self._export([_allotment(Decimal("1"), Decimal("1"), 1, datetime(2024, 1, 31, 20, 0, tzinfo=dt_timezone.utc))])
        header_row = next(r for r in range(1, ws.max_row) if ws.cell(r, 1).value == "Sr No")
        row = header_row + 2
        self.assertIsInstance(ws.cell(row, 2).value, datetime)
        self.assertEqual(ws.cell(row, 2).number_format, "DD-MM-YYYY")
        self.assertEqual(ws.cell(row, 10).value, datetime(2024, 3, 31))  # ETA
        self.assertEqual(ws.cell(row, 13).value, datetime(2024, 2, 29))  # DFIA date, leap day
        self.assertEqual(ws.cell(row, 12).value, "030000")  # leading zero kept
        self.assertEqual(Decimal(str(ws.cell(row, 6).value)), Decimal("1"))  # Value ($) numeric
