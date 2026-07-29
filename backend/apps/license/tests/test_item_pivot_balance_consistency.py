"""
Regression tests for the Item Pivot Report's ("Item Summary") Balance CIF
consistency (`ItemPivotReportView.generate_report`/`_build_license_row`,
`apps/license/views/item_pivot_report.py`).

Prior to this fix, the report read the denormalized `LicenseBalance.
balance_cif` column directly — refreshed only by a background task/signal
on save, or the manual "Update Balance" button — instead of the live
`LicenseBalanceCalculator.calculate_balance()` every other surface (Overview,
Financial Ledger, Customs Ledger, Balance PDF) uses. These tests bypass the
save-time signal via `.update()` (a raw SQL UPDATE, matching how the field
can legitimately go stale between recalculations — e.g. right after a
Balance Engine formula change, before the next per-record save) to prove the
report now shows the LIVE value, never the stale stored one.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from apps.core.constants import GE
from apps.core.models import CompanyModel, PurchaseStatus
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.views.item_pivot_report import ItemPivotReportView


class ItemPivotBalanceConsistencyTests(TestCase):
    def _make_license_with_stale_balance(self, stale_value):
        company = CompanyModel.objects.create(iec="9990002222", name="Pivot Balance Exporter")
        purchase_status, _ = PurchaseStatus.objects.get_or_create(code=GE, defaults={"label": "Global Exim"})
        license_obj = LicenseDetailsModel.objects.create(
            license_number="PIVOT-BAL-001",
            license_date=date.today() - timedelta(days=30),
            license_expiry_date=date.today() + timedelta(days=30),
            exporter=company,
            purchase_status=purchase_status,
        )
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("1000.00"))
        LicenseImportItemsModel.objects.create(
            license=license_obj, serial_number=1, description="Pivot balance item",
            quantity=Decimal("100.000"), available_quantity=Decimal("100.000"),
        )
        # Force the denormalized column to a value that does NOT match the
        # live calculation — `.update()` is a raw SQL UPDATE, bypassing the
        # post_save signal that would otherwise recompute it.
        from apps.license.models.core import LicenseBalance
        LicenseBalance.objects.filter(license=license_obj).update(balance_cif=stale_value)
        license_obj.refresh_from_db()
        return license_obj

    def test_build_license_row_uses_live_balance_not_stale_stored_value(self):
        license_obj = self._make_license_with_stale_balance(Decimal("999999.99"))
        live_balance = LicenseBalanceCalculator.calculate_balance(license_obj)

        self.assertNotEqual(
            license_obj.balance_cif, live_balance,
            "fixture setup must actually desync stored vs. live to prove the fix",
        )

        view = ItemPivotReportView()
        row = view._build_license_row(license_obj, all_items=[])

        self.assertEqual(Decimal(str(row["balance_cif"])), live_balance)
        self.assertNotEqual(Decimal(str(row["balance_cif"])), Decimal("999999.99"))

    def test_generate_report_batches_live_balance_and_agrees_with_calculator(self):
        """The full `generate_report` pipeline (batched `calculate_balance_
        for_licenses`, not per-license `.balance_cif` reads) must produce
        the exact same figure `LicenseBalanceCalculator.calculate_balance`
        would for the same licence — single source of truth end to end."""
        license_obj = self._make_license_with_stale_balance(Decimal("1.00"))
        live_balance = LicenseBalanceCalculator.calculate_balance(license_obj)

        view = ItemPivotReportView()
        report = view.generate_report(min_balance=0, license_status="all")

        found = None
        for _norm, notifs in report["licenses_by_norm_notification"].items():
            for _notif, licenses_list in notifs.items():
                for lic_row in licenses_list:
                    if lic_row["license_number"] == license_obj.license_number:
                        found = lic_row
        self.assertIsNotNone(found, "license must appear in the report output")
        self.assertEqual(Decimal(str(found["balance_cif"])), live_balance)

    def test_never_returns_null_balance_cif_for_standalone_caller(self):
        """Standalone callers that don't pass a pre-batched `balance_cif`
        (e.g. code outside `generate_report`'s batched pipeline) must still
        get a real numeric value, never NULL/None — the live per-licence
        fallback (`balance_cif=None`) must never propagate a NULL through."""
        license_obj = self._make_license_with_stale_balance(Decimal("0"))

        view = ItemPivotReportView()
        row = view._build_license_row(license_obj, all_items=[], balance_cif=None)

        self.assertIsNotNone(row["balance_cif"])
        self.assertIsInstance(row["balance_cif"], float)
