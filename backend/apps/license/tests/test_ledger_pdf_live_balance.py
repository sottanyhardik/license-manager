"""
Regression coverage for BL-LEDGER-02's stale-balance reader in
`build_dfia_ledger_detail` (`apps/license/services/exporters/ledger_pdf.py`,
backing `GET /api/license-ledger/<pk>/`'s DFIA branch). `available_balance`/
`db_balance` used to read `license.balance_cif` (the cached column)
directly; both now call `LicenseBalanceCalculator.calculate_financial_
balance()` live, matching every other module.
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.license.models.core import LicenseBalance
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.services.exporters.ledger_pdf import build_dfia_ledger_detail
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


class BuildDfiaLedgerDetailLiveBalanceTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def test_available_and_db_balance_use_live_balance_not_stale_cache(self):
        from apps.license.models import LicenseExportItemModel

        company = self.make_company()
        license_obj = self.make_license(company)
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("5000.00"))
        item = self.make_item(license_obj, 1)
        boe = self.make_boe(company)
        self.make_debit_row(boe, item, cif_fc=Decimal("1000.00"))

        live_balance = LicenseBalanceCalculator.calculate_financial_balance(license_obj)
        self.assertEqual(live_balance, Decimal("4000.00"))

        # Deliberately desynchronize the cache from the live value.
        LicenseBalance.objects.filter(license=license_obj).update(balance_cif=Decimal("0.00"))
        license_obj.refresh_from_db()
        self.assertEqual(license_obj.balance.balance_cif, Decimal("0.00"))

        detail = build_dfia_ledger_detail(license_obj)
        self.assertEqual(detail["available_balance"], float(live_balance))
        self.assertEqual(detail["db_balance"], float(live_balance))
        self.assertNotEqual(detail["available_balance"], 0.00)


class LicenseLedgerPdfAvailableValueTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    def test_item_balance_uses_one_bulk_live_value_map(self):
        from apps.license.ledger_pdf import generate_license_ledger_pdf
        from apps.license.models import LicenseExportItemModel
        from apps.license.models.core import LicenseBalance
        from apps.license.services.condition_pool import available_value_bulk_map

        company = self.make_company()
        license_obj = self.make_license(company)
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("1000.00"))
        self.make_item(license_obj, 1)
        self.make_item(license_obj, 2)
        LicenseBalance.objects.filter(license=license_obj).update(balance_cif=Decimal("0.00"))

        with patch(
            "apps.license.services.condition_pool.available_value_bulk_map",
            wraps=available_value_bulk_map,
        ) as bulk_map:
            response = generate_license_ledger_pdf(license_obj)

        self.assertGreater(len(response), 0)
        bulk_map.assert_called_once()
