"""OD-21 (owner decision, 2026-11-15): Item pivot keeps planned and unplanned rows separate.

* planned totals include only planned import rows;
* unplanned rows stay visible in their own cell/column (``planning_state``);
* source descriptions/HSNs and ``source_items`` lineage are preserved;
* unplanned descriptions/HSNs are never merged into a planned cell;
* no import row is counted in both a planned and an unplanned cell.
"""
import io
from datetime import date, timedelta
from decimal import Decimal

import openpyxl
from django.test import TestCase

from apps.core.constants import GE
from apps.core.models import CompanyModel, HSCodeModel, ItemNameModel, PurchaseStatus
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel, LicenseItemPlan
from apps.license.services.item_pivot_item_summary import project_item_summary
from apps.license.views.item_pivot_report import ItemPivotReportView


class PlannedUnplannedSeparationTests(TestCase):
    def setUp(self):
        company = CompanyModel.objects.create(iec="PIVOTOD21", name="Pivot OD21 Exporter")
        status, _ = PurchaseStatus.objects.get_or_create(code=GE, defaults={"label": "Global Exim"})
        self.license = LicenseDetailsModel.objects.create(
            license_number="PIVOT-OD21-001", license_date=date.today() - timedelta(days=1),
            license_expiry_date=date.today() + timedelta(days=30), exporter=company, purchase_status=status,
        )
        LicenseExportItemModel.objects.create(license=self.license, cif_fc=Decimal("1000"))
        self.name = ItemNameModel.objects.create(name="PIVOT OD21 ITEM")

    def _item(self, serial, hsn, desc, qty, name=None):
        code, _ = HSCodeModel.objects.get_or_create(hs_code=hsn)
        item = LicenseImportItemsModel.objects.create(
            license=self.license, serial_number=serial, hs_code=code, description=desc,
            quantity=Decimal(qty), available_quantity=Decimal(qty), cif_fc=Decimal("100"),
        )
        item.items.add(name or self.name)
        return item

    def _plan(self, item, qty, cif, name=None, **extra):
        return LicenseItemPlan.objects.create(
            license=self.license, import_item=item, item_name=name or self.name,
            planned_quantity=Decimal(qty), planned_cif_fc=Decimal(cif), **extra,
        )

    def _report_row(self):
        report = ItemPivotReportView().generate_report(min_balance=0, license_status="all")
        for group in report["groups"]:
            for row in group["licenses"]:
                if row["license_id"] == self.license.id:
                    return report, group, row
        raise AssertionError("licence missing from the pivot")

    @staticmethod
    def _by_state(row):
        cells = {}
        for cell in row["items"].values():
            assert cell["planning_state"] not in cells, "one cell per planning state expected here"
            cells[cell["planning_state"]] = cell
        return cells

    def test_unplanned_row_is_its_own_cell_with_its_own_identity_and_quantity(self):
        unplanned = self._item(1, "11010000", "Batch A", "50")
        planned = self._item(2, "11010090", "Batch B", "200")
        self._plan(planned, "150", "750")
        report, group, row = self._report_row()
        cells = self._by_state(row)
        assert set(cells) == {"planned", "unplanned"}
        planned_cell, unplanned_cell = cells["planned"], cells["unplanned"]
        # Planned cell: the planned row only.
        assert Decimal(planned_cell["total_qty"]) == Decimal("200")
        assert Decimal(planned_cell["plan_qty"]) == Decimal("150")
        assert Decimal(planned_cell["planned_cif"]) == Decimal("750")
        assert [s["import_item_id"] for s in planned_cell["source_items"]] == [planned.id]
        # Unplanned cell: visible, own HSN/description/qty, no plan quantities.
        assert unplanned_cell["hsn_code"] == "11010000"
        assert unplanned_cell["description"] == "Batch A"
        assert Decimal(unplanned_cell["total_qty"]) == Decimal("50")
        assert Decimal(unplanned_cell["plan_qty"]) == Decimal("0")
        assert Decimal(unplanned_cell["planned_cif"]) == Decimal("0")
        assert unplanned_cell["status"] == "not_planned"
        assert [s["import_item_id"] for s in unplanned_cell["source_items"]] == [unplanned.id]
        # Licence planned CIF counts the plan once; quantities are not double counted.
        assert Decimal(row["planned_cif"]) == Decimal("750")
        assert sum(Decimal(cell["total_qty"]) for cell in row["items"].values()) == Decimal("250")
        # Both are columns, planned before unplanned, each tagged.
        states = [col["planning_state"] for col in group["item_groups"] if col["key"] in row["items"]]
        assert states == ["planned", "unplanned"]
        # Group totals keep the two quantities apart.
        key_by_state = {cell["planning_state"]: key for key, cell in row["items"].items()}
        totals = group["totals"]["items"]
        assert Decimal(totals[key_by_state["planned"]]["total_qty"]) == Decimal("200")
        assert Decimal(totals[key_by_state["planned"]]["plan_qty"]) == Decimal("150")
        assert Decimal(totals[key_by_state["unplanned"]]["total_qty"]) == Decimal("50")
        assert Decimal(totals[key_by_state["unplanned"]]["plan_qty"]) == Decimal("0")
        # Report-level item list and per-group item summary are split the same way.
        report_states = {item["key"]: item["planning_state"] for item in report["items"]}
        assert report_states[key_by_state["planned"]] == "planned"
        assert report_states[key_by_state["unplanned"]] == "unplanned"
        summary = {r["planning_state"]: r for r in group["item_summary"]}
        assert Decimal(summary["planned"]["total_qty"]) == Decimal("200")
        assert Decimal(summary["unplanned"]["total_qty"]) == Decimal("50")

    def test_provenance_source_row_is_planned_not_double_counted_as_unplanned(self):
        first = self._item(1, "39021000", "PP", "100")
        second = self._item(2, "39021000", "PP", "40")
        self._plan(first, "140", "140", allocation_provenance={"source_item_ids": [first.id, second.id]})
        _report, _group, row = self._report_row()
        assert [cell["planning_state"] for cell in row["items"].values()] == ["planned"]
        cell = next(iter(row["items"].values()))
        assert {s["import_item_id"] for s in cell["source_items"]} == {first.id, second.id}
        assert Decimal(cell["total_qty"]) == Decimal("140")

    def test_every_planned_column_is_registered_not_only_the_last(self):
        fibre_name = ItemNameModel.objects.create(name="PIVOT OD21 FIBRE")
        flour = self._item(1, "11010000", "Wheat Gluten Flour", "100")
        fibre = self._item(2, "08029900", "Dietary Fibre (HSN Code 0802)", "30", name=fibre_name)
        self._plan(flour, "100", "100")
        self._plan(fibre, "30", "30", name=fibre_name)
        _report, group, row = self._report_row()
        assert len(row["items"]) == 2
        assert set(row["items"]) <= {col["key"] for col in group["item_groups"]}
        fibre_cell = next(cell for cell in row["items"].values() if cell["product_category"] == "DIETARY FIBRE")
        # A genuinely single planned source keeps its description (ff021e74 intent).
        assert fibre_cell["description"] == "Dietary Fibre (HSN Code 0802)"
        assert fibre_cell["planning_state"] == "planned"

    def test_unplanned_rows_never_lend_description_or_hsn_to_the_planned_cell(self):
        fibre_name = ItemNameModel.objects.create(name="PIVOT OD21 FIBRE 2")
        planned = self._item(1, "08029900", "Dietary Fibre (HSN Code 0802)", "30", name=fibre_name)
        self._item(2, "08029910", "Dietary Fibre (HSN Code-0802)", "20", name=fibre_name)
        self._item(3, "08029990", "dietary fibre (hsn code-0802)", "10", name=fibre_name)
        self._plan(planned, "30", "30", name=fibre_name)
        _report, _group, row = self._report_row()
        cells = self._by_state(row)
        assert set(cells) == {"planned", "unplanned"}
        assert cells["planned"]["description"] == "Dietary Fibre (HSN Code 0802)"
        assert cells["planned"]["hsn_code"] == "08029900"
        assert Decimal(cells["planned"]["total_qty"]) == Decimal("30")
        assert [s["import_item_id"] for s in cells["planned"]["source_items"]] == [planned.id]
        # Unplanned rows of one category share one unplanned column; their own
        # (case-insensitively identical) description stays visible there.
        assert cells["unplanned"]["product_category"] == cells["planned"]["product_category"] == "DIETARY FIBRE"
        assert cells["unplanned"]["description"] == "Dietary Fibre (HSN Code-0802)"
        assert cells["unplanned"]["hsn_code"] == "08029910, 08029990"
        assert Decimal(cells["unplanned"]["total_qty"]) == Decimal("30")
        assert len(cells["unplanned"]["source_items"]) == 2

    def test_excel_export_shows_planned_and_unplanned_blocks_separately(self):
        self._item(1, "11010000", "Batch A", "50")
        planned = self._item(2, "11010090", "Batch B", "200")
        self._plan(planned, "150", "750")
        response = ItemPivotReportView().export_to_excel_streaming(min_balance=0, license_status="all")
        workbook = openpyxl.load_workbook(io.BytesIO(b"".join(response.streaming_content)), data_only=True)
        for sheet in workbook.worksheets:
            for row in sheet.iter_rows(min_row=4, max_col=2):
                if str(row[1].value) != self.license.license_number:
                    continue
                values = {}
                for col in range(10, sheet.max_column + 1):
                    label = sheet.cell(3, col).value
                    values.setdefault(label, []).append(sheet.cell(row[0].row, col).value)
                assert values["HSN CODE"] == ["11010090", "11010000"]
                assert values["DESCRIPTION"] == ["Batch B", "Batch A"]
                assert [Decimal(str(v)) for v in values["TOTAL QTY"]] == [Decimal("200"), Decimal("50")]
                return
        raise AssertionError("licence row not found in the workbook")


def test_item_summary_projection_keeps_planned_and_unplanned_rows_apart():
    common = {"canonical_item_id": 7, "item_name": "X", "sion": "E5", "available_cif": 0}
    result = project_item_summary([{"license_id": 1, "items": {
        "X:E5": {**common, "planning_state": "planned", "adjusted_total_qty": "200", "available_qty": "200", "plan_qty": "150", "planned_cif": "750"},
        "X:E5:unplanned": {**common, "planning_state": "unplanned", "priority_source": "unplanned", "adjusted_total_qty": "50", "available_qty": "50", "plan_qty": "0", "planned_cif": "0"},
    }}])
    rows = {row["planning_state"]: row for row in result["item_summary"]}
    assert [row["planning_state"] for row in result["item_summary"]] == ["planned", "unplanned"]
    assert Decimal(rows["planned"]["total_qty"]) == Decimal("200")
    assert Decimal(rows["planned"]["planned_qty"]) == Decimal("150")
    assert Decimal(rows["unplanned"]["total_qty"]) == Decimal("50")
    assert Decimal(rows["unplanned"]["planned_qty"]) == Decimal("0")


def test_legacy_cells_without_planning_state_are_treated_as_planned():
    result = project_item_summary([{"license_id": 1, "items": {"1:E1": {
        "canonical_item_id": 1, "item_name": "Y", "sion": "E1", "adjusted_total_qty": "5", "available_qty": "5", "plan_qty": "1", "planned_cif": "1",
    }}}])
    assert [row["planning_state"] for row in result["item_summary"]] == ["planned"]
