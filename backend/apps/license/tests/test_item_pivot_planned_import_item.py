"""
Regression tests for the Item Pivot Report's "planned import item"
verification data (`ItemPivotReportView.generate_report`, `apps/license/
views/item_pivot_report.py`).

Prior to this fix, a pivot cell for an item-name (`ItemNameModel`) shared by
several `LicenseImportItemsModel` rows showed quantities SUMMED across every
one of them, but HSN/Description from whichever import item was encountered
FIRST — not necessarily the one the quantities came from. These tests prove
that for a PLANNED cell (one with real `LicenseItemPlan` rows behind it),
HSN/Description/ledger quantities always come from the exact import item(s)
actually referenced by those plan lines, never a cross-item merge, and that
distinct import items sharing an item-name are listed separately via
`planned_import_items` rather than merged into one ledger record. Unplanned
cells (no `LicenseItemPlan` rows) must keep the pre-existing aggregate
behaviour unchanged — this is a verification aid for planned items only.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from apps.core.constants import GE
from apps.core.models import CompanyModel, HSCodeModel, ItemNameModel, PurchaseStatus
from apps.license.models import (
    LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel, LicenseItemPlan,
)
from apps.license.views.item_pivot_report import ItemPivotReportView


def _hs(code):
    obj, _ = HSCodeModel.objects.get_or_create(hs_code=code)
    return obj


class ItemPivotPlannedImportItemTests(TestCase):

    def _make_license(self, license_number, balance_cif=Decimal('1000.00')):
        company = CompanyModel.objects.create(iec=f"IEC{license_number[-7:]}", name="Pivot Verify Exporter")
        purchase_status, _ = PurchaseStatus.objects.get_or_create(code=GE, defaults={"label": "Global Exim"})
        license_obj = LicenseDetailsModel.objects.create(
            license_number=license_number,
            license_date=date.today() - timedelta(days=30),
            license_expiry_date=date.today() + timedelta(days=30),
            exporter=company,
            purchase_status=purchase_status,
        )
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=balance_cif)
        return license_obj

    def _find_row(self, report, license_number):
        for _norm, notifs in report["licenses_by_norm_notification"].items():
            for _notif, licenses_list in notifs.items():
                for lic_row in licenses_list:
                    if lic_row["license_number"] == license_number:
                        return lic_row
        return None

    def test_planned_cell_uses_the_actual_planned_import_items_own_ledger_data(self):
        # Two import items share the SAME item-name. Only the SECOND one
        # (larger qty, different HSN/description) is actually planned.
        license_obj = self._make_license("PIVOT-VERIFY-001")
        item_name = ItemNameModel.objects.create(name="Wheat Flour - E5")

        unplanned_item = LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=1, description="Wheat Flour Batch A",
            hs_code=_hs('11010000'),
            quantity=Decimal('50.000'), available_quantity=Decimal('50.000'),
            allotted_quantity=Decimal('0.000'), debited_quantity=Decimal('0.000'),
        )
        unplanned_item.items.add(item_name)

        planned_item = LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=2, description="Wheat Flour Batch B",
            hs_code=_hs('11010090'),
            quantity=Decimal('200.000'), available_quantity=Decimal('150.000'),
            allotted_quantity=Decimal('30.000'), debited_quantity=Decimal('20.000'),
        )
        planned_item.items.add(item_name)

        LicenseItemPlan.objects.create(
            license=license_obj, import_item=planned_item, item_name=item_name,
            planned_quantity=Decimal('150.000'), unit_price=Decimal('5.00'),
            planned_cif_fc=Decimal('750.00'),
        )

        view = ItemPivotReportView()
        report = view.generate_report(min_balance=0, license_status='all')
        row = self._find_row(report, "PIVOT-VERIFY-001")
        self.assertIsNotNone(row)

        cell = row['items'][item_name.name]
        # HSN/Description/ledger quantities belong to the PLANNED import item
        # (Batch B) — never the unplanned one (Batch A), and never a sum of
        # both (the old first-wins/merge bug would have shown Batch A's HSN
        # '11010000' with a summed quantity of 250).
        self.assertEqual(cell['hs_code'], '11010090')
        self.assertEqual(cell['description'], 'Wheat Flour Batch B')
        self.assertEqual(cell['quantity'], 200.0)
        self.assertEqual(cell['allotted_quantity'], 30.0)
        self.assertEqual(cell['debited_quantity'], 20.0)
        self.assertEqual(cell['available_quantity'], 150.0)

        self.assertEqual(len(cell['planned_import_items']), 1)
        pit = cell['planned_import_items'][0]
        self.assertEqual(pit['import_item_id'], planned_item.id)
        self.assertEqual(pit['hs_code'], '11010090')
        self.assertEqual(pit['description'], 'Wheat Flour Batch B')
        self.assertEqual(pit['planned_quantity'], 150.0)
        self.assertEqual(pit['planned_cif_fc'], 750.0)

    def test_multiple_planned_import_items_under_one_item_name_are_never_merged(self):
        license_obj = self._make_license("PIVOT-VERIFY-002")
        item_name = ItemNameModel.objects.create(name="SWP - E1")

        item_a = LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=1, description="Milk Powder A",
            hs_code=_hs('04021010'),
            quantity=Decimal('100.000'), available_quantity=Decimal('100.000'),
            allotted_quantity=Decimal('10.000'), debited_quantity=Decimal('5.000'),
        )
        item_a.items.add(item_name)

        item_b = LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=2, description="Milk Powder B",
            hs_code=_hs('04022110'),
            quantity=Decimal('80.000'), available_quantity=Decimal('80.000'),
            allotted_quantity=Decimal('0.000'), debited_quantity=Decimal('0.000'),
        )
        item_b.items.add(item_name)

        LicenseItemPlan.objects.create(
            license=license_obj, import_item=item_a, item_name=item_name,
            planned_quantity=Decimal('90.000'), unit_price=Decimal('1.50'),
            planned_cif_fc=Decimal('135.00'),
        )
        LicenseItemPlan.objects.create(
            license=license_obj, import_item=item_b, item_name=item_name,
            planned_quantity=Decimal('80.000'), unit_price=Decimal('1.50'),
            planned_cif_fc=Decimal('120.00'),
        )

        view = ItemPivotReportView()
        report = view.generate_report(min_balance=0, license_status='all')
        row = self._find_row(report, "PIVOT-VERIFY-002")
        cell = row['items'][item_name.name]

        # Two distinct import items were planned under the same item-name —
        # never merged into one ledger record. The top-level scalar columns
        # are left blank/zero rather than silently summed or picking one.
        self.assertEqual(cell['hs_code'], '')
        self.assertEqual(cell['description'], '')
        self.assertEqual(cell['quantity'], 0.0)
        self.assertEqual(cell['allotted_quantity'], 0.0)
        self.assertEqual(cell['debited_quantity'], 0.0)
        self.assertEqual(cell['available_quantity'], 0.0)

        planned = {p['import_item_id']: p for p in cell['planned_import_items']}
        self.assertEqual(len(planned), 2)
        self.assertEqual(planned[item_a.id]['hs_code'], '04021010')
        self.assertEqual(planned[item_a.id]['description'], 'Milk Powder A')
        self.assertEqual(planned[item_a.id]['quantity'], 100.0)
        self.assertEqual(planned[item_a.id]['allotted_quantity'], 10.0)
        self.assertEqual(planned[item_a.id]['planned_quantity'], 90.0)
        self.assertEqual(planned[item_a.id]['planned_cif_fc'], 135.0)

        self.assertEqual(planned[item_b.id]['hs_code'], '04022110')
        self.assertEqual(planned[item_b.id]['description'], 'Milk Powder B')
        self.assertEqual(planned[item_b.id]['quantity'], 80.0)
        self.assertEqual(planned[item_b.id]['planned_quantity'], 80.0)
        self.assertEqual(planned[item_b.id]['planned_cif_fc'], 120.0)

    def test_multiple_plan_lines_on_the_same_import_item_are_summed_not_duplicated(self):
        # A milk item split into DWP + SWP still references ONE import item —
        # planned_import_items must have exactly one entry with the CIF/qty
        # from both lines summed, not two entries for the same import item.
        license_obj = self._make_license("PIVOT-VERIFY-003")
        item_name = ItemNameModel.objects.create(name="DWP - E1")
        item = LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=1, description="Milk Powder",
            hs_code=_hs('04021010'),
            quantity=Decimal('100.000'), available_quantity=Decimal('100.000'),
        )
        item.items.add(item_name)

        LicenseItemPlan.objects.create(
            license=license_obj, import_item=item, item_name=item_name,
            planned_quantity=Decimal('58.000'), unit_price=Decimal('4.40'),
            planned_cif_fc=Decimal('255.20'),
        )
        LicenseItemPlan.objects.create(
            license=license_obj, import_item=item, item_name=item_name,
            planned_quantity=Decimal('42.000'), unit_price=Decimal('1.50'),
            planned_cif_fc=Decimal('63.00'),
        )

        view = ItemPivotReportView()
        report = view.generate_report(min_balance=0, license_status='all')
        row = self._find_row(report, "PIVOT-VERIFY-003")
        cell = row['items'][item_name.name]

        self.assertEqual(len(cell['planned_import_items']), 1)
        pit = cell['planned_import_items'][0]
        self.assertEqual(pit['import_item_id'], item.id)
        self.assertEqual(pit['planned_quantity'], 100.0)
        self.assertEqual(pit['planned_cif_fc'], 318.2)
        # Single planned import item -> top-level scalar columns are that
        # item's own ledger values.
        self.assertEqual(cell['hs_code'], '04021010')
        self.assertEqual(cell['quantity'], 100.0)

    def test_unplanned_cell_keeps_existing_aggregate_behaviour(self):
        # No LicenseItemPlan rows at all — this is the pre-existing,
        # unaffected code path: quantities summed, first-non-empty HSN wins.
        license_obj = self._make_license("PIVOT-VERIFY-004")
        item_name = ItemNameModel.objects.create(name="Wheat Flour - E5")

        item_a = LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=1, description="Wheat Flour Batch A",
            hs_code=_hs('11010000'),
            quantity=Decimal('50.000'), available_quantity=Decimal('50.000'),
        )
        item_a.items.add(item_name)
        item_b = LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=2, description="Wheat Flour Batch B",
            hs_code=_hs('11010090'),
            quantity=Decimal('200.000'), available_quantity=Decimal('150.000'),
        )
        item_b.items.add(item_name)

        view = ItemPivotReportView()
        report = view.generate_report(min_balance=0, license_status='all')
        row = self._find_row(report, "PIVOT-VERIFY-004")
        cell = row['items'][item_name.name]

        # Unchanged legacy behaviour: quantities summed across both items,
        # HSN/description from whichever was encountered first.
        self.assertEqual(cell['hs_code'], '11010000')
        self.assertEqual(cell['description'], 'Wheat Flour Batch A')
        self.assertEqual(cell['quantity'], 250.0)
        self.assertEqual(cell['available_quantity'], 200.0)
        self.assertEqual(cell['planned_import_items'], [])
