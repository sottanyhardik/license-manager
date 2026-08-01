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
from apps.core.models import (
    CompanyModel, HeadSIONNormsModel, HSCodeModel, ItemNameModel, PurchaseStatus, SionNormClassModel,
)
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


class ItemPivotLiveComputeVerificationTests(TestCase):
    """Regression tests for the LIVE norm-waterfall recompute path
    (`item_plan_data`, built inline in `_build_license_row` for licences with
    no — or a different — persisted `LicenseItemPlan`). Its bug was
    attributing planned CIF to the import item's OWN `ItemNameModel` M2M tags
    instead of the engine's step -> item-name mapping (`STEP_ITEM_NAME`).

    A pivot column only exists at all when the report has SOME reason to
    know about that item-name — either a real M2M-tagged import item
    somewhere in the batch, or a persisted plan (`_missing_planned`). These
    tests reproduce the realistic shape of the reported bug: the
    "FRUIT/COCOA - E1" column is visible because ANOTHER licence in the same
    batched report has an item tagged with it (a common real-world case,
    since these reports are run across many licences at once) — the licence
    under test has its OWN, untagged Cocoa Mass import item that the live
    engine must still resolve correctly, not leave blank.
    """

    def _make_e1_license(self, license_number, balance_cif=Decimal('10000.00')):
        company = CompanyModel.objects.create(iec=f"IEC{license_number[-7:]}", name="Pivot Live-Compute Exporter")
        purchase_status, _ = PurchaseStatus.objects.get_or_create(code=GE, defaults={"label": "Global Exim"})
        head_norm = HeadSIONNormsModel.objects.create(name=f"Head {license_number}")
        norm_class, _ = SionNormClassModel.objects.get_or_create(
            norm_class="E1", defaults={"head_norm": head_norm, "is_active": True},
        )
        license_obj = LicenseDetailsModel.objects.create(
            license_number=license_number,
            license_date=date.today() - timedelta(days=30),
            license_expiry_date=date.today() + timedelta(days=30),
            exporter=company,
            purchase_status=purchase_status,
        )
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=balance_cif, norm_class=norm_class)
        return license_obj

    def _find_row(self, report, license_number):
        for _norm, notifs in report["licenses_by_norm_notification"].items():
            for _notif, licenses_list in notifs.items():
                for lic_row in licenses_list:
                    if lic_row["license_number"] == license_number:
                        return lic_row
        return None

    def test_cocoa_mass_column_resolves_the_real_import_item_with_no_persisted_plan(self):
        # Another licence in the same batch has a Cocoa item DIRECTLY tagged
        # with "FRUIT/COCOA - E1" — this is what makes the column exist in
        # the report at all (mirrors real master-data setups).
        tagging_license = self._make_e1_license("0311055574-TAGGED")
        item_name = ItemNameModel.objects.create(name="FRUIT/COCOA - E1", is_active=True)
        tagging_item = LicenseImportItemsModel.objects.create(
            license=tagging_license, serial_number=1, description="Tagging-only Cocoa",
            hs_code=_hs('18039999'), quantity=Decimal('1.000'), available_quantity=Decimal('1.000'),
        )
        tagging_item.items.add(item_name)

        # License under test: its OWN Cocoa Mass import item has NO M2M
        # item-name links at all — exactly how a real Cocoa Mass row
        # typically looks in master data, since "FRUIT/COCOA - E1" is a
        # planner-output label, not something an operator pre-tags import
        # items with. No LicenseItemPlan rows either — never Auto-Plan-saved.
        license_obj = self._make_e1_license("0311055574")
        cocoa_item = LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=1, description="Cocoa Mass HSN 1803",
            hs_code=_hs('18031000'),
            quantity=Decimal('500.000'), available_quantity=Decimal('500.000'),
        )
        self.assertEqual(cocoa_item.items.count(), 0)

        view = ItemPivotReportView()
        report = view.generate_report(min_balance=0, license_status='all')
        row = self._find_row(report, "0311055574")
        self.assertIsNotNone(row, "license must appear in the report output")

        cell = row['items'].get('FRUIT/COCOA - E1')
        self.assertIsNotNone(cell, "FRUIT/COCOA - E1 column must exist for an E1 licence with a Cocoa Mass item")

        # The bug: these used to be blank ('' / 0) because attribution went
        # through the import item's (empty) own M2M tags instead of the
        # engine's step -> item-name mapping — and must resolve to THIS
        # licence's own Cocoa item, never the unrelated tagging licence's.
        self.assertEqual(cell['hs_code'], '18031000')
        self.assertEqual(cell['description'], 'Cocoa Mass HSN 1803')
        self.assertEqual(cell['quantity'], 500.0)
        self.assertEqual(cell['available_quantity'], 500.0)
        # And the planned CIF that was ALREADY correctly shown before the fix.
        self.assertEqual(cell['planned_cif'], 5000.0)  # 500 * $10.00 Cocoa Mass rate

        self.assertEqual(len(cell['planned_import_items']), 1)
        pit = cell['planned_import_items'][0]
        self.assertEqual(pit['import_item_id'], cocoa_item.id)
        self.assertEqual(pit['hs_code'], '18031000')
        self.assertEqual(pit['description'], 'Cocoa Mass HSN 1803')
        self.assertEqual(pit['planned_quantity'], 500.0)
        self.assertEqual(pit['planned_cif_fc'], 5000.0)

    def test_every_e1_category_resolves_its_import_item_with_no_persisted_plan(self):
        # Not a hardcoded single-category check — one item per category, none
        # M2M-tagged with the planner's own output label, none saved via
        # Auto-Plan. Every column must resolve to its OWN real import item.
        tagging_license = self._make_e1_license("E1-LIVE-TAGGING")
        tag_names = [
            'OTHER CONFECTIONERY INGREDIENTS - E1', 'FRUIT/COCOA - E1', 'DWP - E1', 'SWP - E1',
            'WPC - E1', 'FRUIT JUICE - E1', 'CITRIC ACID / TARTARIC ACID - E1',
            'ALUMINIUM FOIL - E1', 'PP - E1',
        ]
        for idx, nm in enumerate(tag_names, start=1):
            item_name = ItemNameModel.objects.create(name=nm, is_active=True)
            tagging_item = LicenseImportItemsModel.objects.create(
                license=tagging_license, serial_number=idx, description=f"Tagging-only {nm}",
                quantity=Decimal('1.000'), available_quantity=Decimal('1.000'),
            )
            tagging_item.items.add(item_name)

        license_obj = self._make_e1_license("E1-LIVE-ALL-CATS", balance_cif=Decimal('1000000.00'))

        specs = [
            ('Other Confectionery Ingredients', '08021100', 'OTHER CONFECTIONERY INGREDIENTS - E1'),
            ('Cocoa Mass HSN 1803', '18031000', 'FRUIT/COCOA - E1'),
            ('Skimmed Milk Powder', '04041000', None),  # milk -> DWP/SWP handled separately below
            ('Egg Albumin', '35021100', 'WPC - E1'),
            ('Fruit Juice Concentrate', '20091100', 'FRUIT JUICE - E1'),
            ('Tartaric Acid', '29182000', 'CITRIC ACID / TARTARIC ACID - E1'),
            ('Aluminium Foil', '76071190', 'ALUMINIUM FOIL - E1'),
            ('Polypropylene Granules', '39021000', 'PP - E1'),
        ]
        created = {}
        for idx, (desc, hsn, _expected_col) in enumerate(specs, start=1):
            ii = LicenseImportItemsModel.objects.create(
                license=license_obj, serial_number=idx, description=desc,
                hs_code=_hs(hsn),
                quantity=Decimal('100.000'), available_quantity=Decimal('100.000'),
            )
            self.assertEqual(ii.items.count(), 0)
            created[desc] = ii

        view = ItemPivotReportView()
        report = view.generate_report(min_balance=0, license_status='all')
        row = self._find_row(report, "E1-LIVE-ALL-CATS")
        self.assertIsNotNone(row)

        for desc, hsn, expected_col in specs:
            if expected_col is None:
                continue
            cell = row['items'].get(expected_col)
            self.assertIsNotNone(cell, f"{expected_col} column must exist")
            self.assertNotEqual(cell['hs_code'], '', f"{expected_col} HSN must not be blank")
            self.assertNotEqual(cell['description'], '', f"{expected_col} Description must not be blank")
            self.assertEqual(cell['hs_code'], hsn, f"{expected_col} HSN must match its actual import item")
            self.assertEqual(cell['description'], desc, f"{expected_col} Description must match its actual import item")
            self.assertGreater(cell['quantity'], 0, f"{expected_col} Total Qty must not be blank")

        # Milk: 0404 item is priced via DWP/SWP — verify both resolve too.
        for col in ('DWP - E1', 'SWP - E1'):
            cell = row['items'].get(col)
            if cell is None or not cell.get('planned_import_items'):
                continue  # this licence's balance/qty may route entirely to one of DWP/SWP
            self.assertEqual(cell['hs_code'], '04041000')
            self.assertEqual(cell['description'], 'Skimmed Milk Powder')

    def test_two_pp_items_with_duplicate_hsn_are_never_string_concatenated(self):
        # Reported corruption pattern: two PP import items both under HSN
        # 39021000 landing in one "PP - E1" column showed a glued-together
        # HSN string ("3902100039021000") instead of two distinct records.
        # Neither is M2M-tagged and neither has a persisted plan — this
        # exercises the LIVE E1 waterfall attribution path exactly like the
        # other classify-only items above.
        tagging_license = self._make_e1_license("E1-DUP-HSN-TAGGING")
        tag_name = ItemNameModel.objects.create(name="PP - E1", is_active=True)
        tagging_item = LicenseImportItemsModel.objects.create(
            license=tagging_license, serial_number=1, description="Tagging-only PP",
            quantity=Decimal('1.000'), available_quantity=Decimal('1.000'),
        )
        tagging_item.items.add(tag_name)

        license_obj = self._make_e1_license("E1-DUP-HSN", balance_cif=Decimal('100000.00'))
        item_a = LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=1, description="Polypropylene Granules Batch A",
            hs_code=_hs('39021000'),
            quantity=Decimal('100.000'), available_quantity=Decimal('100.000'),
        )
        item_b = LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=2, description="Polypropylene Granules Batch B",
            hs_code=_hs('39021000'),
            quantity=Decimal('200.000'), available_quantity=Decimal('200.000'),
        )

        view = ItemPivotReportView()
        report = view.generate_report(min_balance=0, license_status='all')
        row = self._find_row(report, "E1-DUP-HSN")
        self.assertIsNotNone(row)

        cell = row['items'].get('PP - E1')
        self.assertIsNotNone(cell, "PP - E1 column must exist")

        # Two distinct import items behind one column -> top-level scalar
        # fields are blanked (never merged/concatenated), never a string
        # like "3902100039021000".
        self.assertEqual(cell['hs_code'], '')
        self.assertEqual(cell['description'], '')
        self.assertNotIn('39021000', str(cell['hs_code']))

        planned = {p['import_item_id']: p for p in cell['planned_import_items']}
        self.assertEqual(len(planned), 2)
        self.assertEqual(planned[item_a.id]['hs_code'], '39021000')
        self.assertEqual(planned[item_b.id]['hs_code'], '39021000')
        # Each item's own quantity stays an independent number, never glued
        # to the other's (e.g. never "100.0200.0" / concatenated strings).
        self.assertIsInstance(planned[item_a.id]['quantity'], float)
        self.assertIsInstance(planned[item_b.id]['quantity'], float)
        self.assertEqual(planned[item_a.id]['quantity'], 100.0)
        self.assertEqual(planned[item_b.id]['quantity'], 200.0)

    def test_two_aluminium_foil_items_with_different_quantities_are_never_concatenated(self):
        # Reported corruption pattern: two Aluminium Foil import items with
        # different quantities (e.g. 9125.120 and 37985.810) landing in one
        # column showed "9125.12037985.810" instead of two distinct numbers.
        tagging_license = self._make_e1_license("E1-DUP-QTY-TAGGING")
        tag_name = ItemNameModel.objects.create(name="ALUMINIUM FOIL - E1", is_active=True)
        tagging_item = LicenseImportItemsModel.objects.create(
            license=tagging_license, serial_number=1, description="Tagging-only Foil",
            quantity=Decimal('1.000'), available_quantity=Decimal('1.000'),
        )
        tagging_item.items.add(tag_name)

        license_obj = self._make_e1_license("E1-DUP-QTY", balance_cif=Decimal('1000000.00'))
        item_a = LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=1, description="Aluminium Foil Batch A",
            hs_code=_hs('76071190'),
            quantity=Decimal('9125.120'), available_quantity=Decimal('9125.120'),
        )
        item_b = LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=2, description="Aluminium Foil Batch B",
            hs_code=_hs('76072000'),
            quantity=Decimal('37985.810'), available_quantity=Decimal('37985.810'),
        )

        view = ItemPivotReportView()
        report = view.generate_report(min_balance=0, license_status='all')
        row = self._find_row(report, "E1-DUP-QTY")
        self.assertIsNotNone(row)

        cell = row['items'].get('ALUMINIUM FOIL - E1')
        self.assertIsNotNone(cell, "ALUMINIUM FOIL - E1 column must exist")

        self.assertEqual(cell['quantity'], 0.0)
        self.assertEqual(cell['hs_code'], '')

        planned = {p['import_item_id']: p for p in cell['planned_import_items']}
        self.assertEqual(len(planned), 2)
        self.assertEqual(planned[item_a.id]['quantity'], 9125.120)
        self.assertEqual(planned[item_b.id]['quantity'], 37985.810)
        self.assertEqual(planned[item_a.id]['hs_code'], '76071190')
        self.assertEqual(planned[item_b.id]['hs_code'], '76072000')
