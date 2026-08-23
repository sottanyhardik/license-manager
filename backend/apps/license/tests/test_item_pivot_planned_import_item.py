"""Canonical v1 Item Pivot provenance and normalization regressions."""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from apps.core.constants import GE
from apps.core.models import CompanyModel, HSCodeModel, ItemNameModel, PurchaseStatus
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel, LicenseItemPlan
from apps.license.services.plan_grouping import merge_key, merge_planned_import_items
from apps.license.views.item_pivot_report import ItemPivotReportView


class CanonicalPivotSourceTests(TestCase):
    def setUp(self):
        company = CompanyModel.objects.create(iec="PIVOTSRC", name="Pivot Source Exporter")
        status, _ = PurchaseStatus.objects.get_or_create(code=GE, defaults={"label": "Global Exim"})
        self.license = LicenseDetailsModel.objects.create(
            license_number="PIVOT-SOURCE-001", license_date=date.today() - timedelta(days=1),
            license_expiry_date=date.today() + timedelta(days=30), exporter=company, purchase_status=status,
        )
        LicenseExportItemModel.objects.create(license=self.license, cif_fc=Decimal("1000"))
        self.name = ItemNameModel.objects.create(name="PIVOT SOURCE ITEM")

    def _item(self, serial, hsn, desc, qty):
        code, _ = HSCodeModel.objects.get_or_create(hs_code=hsn)
        item = LicenseImportItemsModel.objects.create(
            license=self.license, serial_number=serial, hs_code=code, description=desc,
            quantity=Decimal(qty), available_quantity=Decimal(qty), cif_fc=Decimal("100"),
        )
        item.items.add(self.name)
        return item

    def _cell(self):
        report = ItemPivotReportView().generate_report(min_balance=0, license_status="all")
        row = next(row for group in report["groups"] for row in group["licenses"] if row["license_id"] == self.license.id)
        return next(iter(row["items"].values()))

    def test_source_items_identify_only_the_planned_import_row(self):
        self._item(1, "11010000", "Batch A", "50")
        planned = self._item(2, "11010090", "Batch B", "200")
        LicenseItemPlan.objects.create(license=self.license, import_item=planned, item_name=self.name, planned_quantity=Decimal("150"), planned_cif_fc=Decimal("750"))
        cell = self._cell()
        assert cell["hsn_code"] == "11010090"
        assert cell["description"] == "Batch B"
        source = cell["source_items"]
        assert len(source) == 1
        assert source[0]["import_item_id"] == planned.id
        assert source[0]["serial_number"] == 2
        assert source[0]["hsn_code"] == "11010090"
        assert source[0]["description"] == "Batch B"
        assert Decimal(source[0]["quantity"]) == Decimal("200")
        assert Decimal(source[0]["available_quantity"]) == Decimal("200")

    def test_same_source_split_lines_sum_plan_pair_once(self):
        item = self._item(1, "04021010", "Milk", "100")
        for qty, cif in (("58", "255.2"), ("42", "63")):
            LicenseItemPlan.objects.create(license=self.license, import_item=item, item_name=self.name, planned_quantity=Decimal(qty), planned_cif_fc=Decimal(cif))
        cell = self._cell()
        assert Decimal(cell["plan_qty"]) == Decimal("100")
        assert Decimal(cell["planned_cif"]) == Decimal("318.2")
        assert len(cell["source_items"]) == 1

    def test_distinct_sources_remain_traceable_and_do_not_string_concatenate(self):
        first = self._item(1, "39021000", "PP A", "100")
        second = self._item(2, "39021000", "PP B", "200")
        for item in (first, second):
            LicenseItemPlan.objects.create(license=self.license, import_item=item, item_name=self.name, planned_quantity=item.quantity, planned_cif_fc=item.quantity)
        cell = self._cell()
        assert cell["hsn_code"] == "39021000"
        assert cell["description"] == ""
        assert {source["import_item_id"] for source in cell["source_items"]} == {first.id, second.id}
        assert Decimal(cell["plan_qty"]) == Decimal("300")


def test_merge_normalization_retains_exact_physical_product_rules():
    assert merge_key("39021000", " Packing Material / PP ") == merge_key("39021000", "packing material/PP")
    assert merge_key("39021000", "Packing Material") != merge_key("39021001", "Packing Material")
    merged = merge_planned_import_items([
        {"import_item_id": 2, "hs_code": "39021000", "description": "Packing Material / PP", "quantity": 2, "planned_quantity": 2, "planned_cif_fc": 10},
        {"import_item_id": 1, "hs_code": "39021000", "description": "packing material/PP", "quantity": 3, "planned_quantity": 3, "planned_cif_fc": 15},
        {"import_item_id": 3, "hs_code": "39021000", "description": "Other", "quantity": 1, "planned_quantity": 1, "planned_cif_fc": 7},
    ])
    assert merged[0]["import_item_ids"] == [1, 2]
    assert merged[0]["quantity"] == 5
    assert merged[0]["unit_price"] == 5.0
    assert len(merged) == 2
