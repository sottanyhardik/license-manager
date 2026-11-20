"""Unit tests for the shared Excel cell helpers (numeric / date / text / SUM formulas)."""
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from io import BytesIO

import openpyxl
from django.test import SimpleTestCase, override_settings

from apps.core.exporters.excel.cell_formats import (
    AMOUNT_FORMAT,
    DATE_FORMAT,
    DATETIME_FORMAT,
    finalize_workbook,
    parse_display_date,
    sum_formula,
    to_number,
    write_date,
    write_number,
    write_sum,
    write_text,
)
from apps.core.exporters.excel.workbook_builder import ExcelWorkbookBuilder


def _roundtrip(wb):
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return openpyxl.load_workbook(buf)


class NumberCellTests(SimpleTestCase):
    def setUp(self):
        self.ws = openpyxl.Workbook().active

    def test_numeric_types_stay_numeric(self):
        for idx, value in enumerate([5, 2.5, Decimal("1234.5678")], 1):
            cell = write_number(self.ws.cell(row=idx, column=1), value)
            self.assertEqual(cell.value, value)
            self.assertNotIsInstance(cell.value, str)
            self.assertEqual(cell.number_format, AMOUNT_FORMAT)

    def test_decimal_precision_survives_save(self):
        write_number(self.ws["A1"], Decimal("0.1234567"))
        wb = _roundtrip(self.ws.parent)
        self.assertEqual(Decimal(str(wb.active["A1"].value)), Decimal("0.1234567"))

    def test_negative_and_zero(self):
        write_number(self.ws["A1"], Decimal("-12.50"))
        write_number(self.ws["A2"], 0)
        write_number(self.ws["A3"], Decimal("0.00"))
        self.assertEqual(self.ws["A1"].value, Decimal("-12.50"))
        self.assertEqual(self.ws["A2"].value, 0)
        self.assertEqual(self.ws["A3"].value, Decimal("0.00"))

    def test_numeric_strings_parsed_and_blank_is_none(self):
        self.assertEqual(to_number("1,234.50"), Decimal("1234.50"))
        self.assertEqual(to_number("-3"), Decimal("-3"))
        self.assertIsNone(to_number(""))
        self.assertIsNone(to_number("abc"))
        self.assertIsNone(to_number(None))
        self.assertIsNone(to_number(True))


class TextCellTests(SimpleTestCase):
    def test_identifiers_keep_leading_zeros(self):
        ws = openpyxl.Workbook().active
        write_text(ws["A1"], "0300123456")
        write_text(ws["A2"], 7)
        wb = _roundtrip(ws.parent)
        self.assertEqual(wb.active["A1"].value, "0300123456")
        self.assertEqual(wb.active["A1"].number_format, "@")
        self.assertEqual(wb.active["A2"].value, "7")


class DateCellTests(SimpleTestCase):
    def setUp(self):
        self.ws = openpyxl.Workbook().active

    def _date(self, value):
        cell = write_date(self.ws["A1"], value)
        return cell.value, cell.number_format

    def test_real_date_cell_ddmmyyyy(self):
        value, fmt = self._date(date(2024, 3, 5))
        self.assertEqual(value, date(2024, 3, 5))
        self.assertEqual(fmt, DATE_FORMAT)
        self.assertEqual(DATE_FORMAT, "DD-MM-YYYY")

    def test_leap_day(self):
        self.assertEqual(self._date(date(2024, 2, 29))[0], date(2024, 2, 29))
        self.assertEqual(parse_display_date("29-02-2024"), date(2024, 2, 29))
        self.assertIsNone(parse_display_date("29-02-2023"))

    def test_boundaries(self):
        self.assertEqual(self._date(date(2023, 12, 31))[0], date(2023, 12, 31))
        self.assertEqual(self._date(date(2024, 1, 1))[0], date(2024, 1, 1))

    def test_string_dates_are_day_first(self):
        self.assertEqual(parse_display_date("01-02-2024"), date(2024, 2, 1))
        self.assertEqual(parse_display_date("01/02/2024"), date(2024, 2, 1))
        self.assertEqual(parse_display_date("2024-02-01"), date(2024, 2, 1))
        self.assertIsNone(parse_display_date("--"))
        self.assertIsNone(write_date(self.ws["B1"], "--").value)

    @override_settings(USE_TZ=True, TIME_ZONE="Asia/Kolkata")
    def test_aware_datetime_uses_local_date(self):
        # 20:00 UTC on 31-Dec is already 01:30 on 01-Jan in IST.
        aware = datetime(2023, 12, 31, 20, 0, tzinfo=dt_timezone.utc)
        from django.utils import timezone

        with timezone.override("Asia/Kolkata"):
            self.assertEqual(parse_display_date(aware), date(2024, 1, 1))
            cell = write_date(self.ws["A1"], aware, DATETIME_FORMAT)
        self.assertEqual(cell.value, datetime(2024, 1, 1, 1, 30))
        self.assertIsNone(cell.value.tzinfo)

    @override_settings(USE_TZ=True, TIME_ZONE="UTC")
    def test_aware_datetime_near_midnight_utc_not_shifted(self):
        aware = datetime(2024, 3, 5, 23, 59, tzinfo=dt_timezone.utc)
        self.assertEqual(parse_display_date(aware), date(2024, 3, 5))

    def test_finalize_sets_date_format_on_default_cells(self):
        self.ws["A1"] = date(2024, 3, 5)
        self.ws["A2"] = datetime(2024, 3, 5, 10, 30)
        finalize_workbook(self.ws.parent)
        self.assertEqual(self.ws["A1"].number_format, DATE_FORMAT)
        self.assertEqual(self.ws["A2"].number_format, DATETIME_FORMAT)
        self.assertTrue(self.ws.parent.calculation.fullCalcOnLoad)


class SumFormulaTests(SimpleTestCase):
    def test_sum_formula_text(self):
        self.assertEqual(sum_formula(8, 2, 101), "=SUM(H2:H101)")
        self.assertEqual(sum_formula("C", 3, 3), "=SUM(C3:C3)")

    def test_empty_range_is_zero(self):
        self.assertEqual(sum_formula(1, 5, 4), 0)

    def test_write_sum_covers_data_rows_not_total_row(self):
        ws = openpyxl.Workbook().active
        for i, v in enumerate([Decimal("10.10"), Decimal("-2.05"), 3], start=2):
            write_number(ws.cell(row=i, column=2), v)
        total = write_sum(ws.cell(row=5, column=2), 2, 4)
        self.assertEqual(total.value, "=SUM(B2:B4)")
        self.assertEqual(total.number_format, AMOUNT_FORMAT)
        wb = _roundtrip(ws.parent)
        self.assertEqual(wb.active["B5"].value, "=SUM(B2:B4)")


class WorkbookBuilderTotalTests(SimpleTestCase):
    def test_total_row_is_live_formula_over_data_rows_only(self):
        ws = openpyxl.Workbook().active
        b = ExcelWorkbookBuilder(ws)
        b.add_title("T")
        b.add_header_row(["Name", "Amount"])
        b.add_data_rows([["a", Decimal("1.50")], ["b", "2,000.25"], ["c", -1]], number_columns=[1])
        b.add_total_row(["Total", None], number_columns=[1], sum_columns=[1])
        # header on row 2, data rows 3..5, total row 6
        self.assertEqual(ws["B6"].value, "=SUM(B3:B5)")
        self.assertEqual(ws["B4"].value, Decimal("2000.25"))  # numeric string became a number

    def test_total_row_without_sum_columns_is_backward_compatible(self):
        ws = openpyxl.Workbook().active
        b = ExcelWorkbookBuilder(ws)
        b.add_header_row(["Amount"])
        b.add_data_row([Decimal("1.00")], number_columns=[0])
        b.add_total_row([Decimal("1.00")], number_columns=[0])
        self.assertEqual(ws["A3"].value, Decimal("1.00"))

    def test_date_value_becomes_date_cell(self):
        ws = openpyxl.Workbook().active
        b = ExcelWorkbookBuilder(ws)
        b.add_data_row([date(2024, 2, 29)])
        self.assertEqual(ws["A1"].number_format, DATE_FORMAT)


# --- length/argument-safe formula helpers (CIF audit S3) -------------------
def test_sum_cells_formula_small_list():
    from apps.core.exporters.excel.cell_formats import sum_cells_formula

    assert sum_cells_formula(["F5", "F20"], fallback=1) == "=SUM(F5,F20)"
    assert sum_cells_formula([], fallback=Decimal("7.5")) == Decimal("7.5")


def test_sum_cells_formula_chunks_past_255_args():
    from apps.core.exporters.excel.cell_formats import sum_cells_formula

    cells = [f"F{i}" for i in range(1, 301)]
    formula = sum_cells_formula(cells, fallback=0)
    assert formula.startswith("=SUM(SUM(F1,") and formula.count("SUM(") == 3
    assert all(f"F{i}," in formula or f"F{i})" in formula for i in (1, 255, 256, 300))


def test_sum_cells_formula_falls_back_past_length_limit():
    from apps.core.exporters.excel.cell_formats import sum_cells_formula

    cells = [f"F{100000 + i}" for i in range(2000)]  # ~16k characters
    assert sum_cells_formula(cells, fallback=Decimal("-12.34")) == Decimal("-12.34")


def test_sumif_label_formula_span_and_escaping():
    from apps.core.exporters.excel.cell_formats import sumif_label_formula

    assert sumif_label_formula(3, "Total", 5, 12, 40) == '=SUMIF(C12:C40,"Total",E12:E40)'
    assert sumif_label_formula("C", 'A "q"', "D", 1, 2) == '=SUMIF(C1:C2,"A ""q""",D1:D2)'
    assert sumif_label_formula(3, "Total", 5, 10, 9) == 0
