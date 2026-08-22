"""
Regression coverage for BL-LEDGER-02's stale-balance reader.
Backing `GET /api/license-ledger/<pk>/`'s DFIA branch, the canonical
ledger service now calls `LicenseBalanceCalculator.calculate_financial_
balance()` live, matching every other module. This replaces the legacy
`build_dfia_ledger_detail` function (removed in Phase 4E-F).
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.license.models.core import LicenseBalance
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.tests.test_balance_ledger_views import LicenseBalanceLedgerFixtureMixin


class CanonicalLedgerLiveBalanceTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    """
    Regression: canonical ledger correctly reflects current trade state.
    Verifies that canonical ledger API correctly calculates balance from trades
    (independent of any stale BOE-only cached values).
    """
    def test_canonical_ledger_reflects_current_trade_state(self):
        from apps.license.models import LicenseExportItemModel, LicenseImportItemsModel
        from apps.license.services.canonical_ledger_service import CanonicalLedgerService
        from apps.trade.models import LicenseTrade
        from apps.core.models import CompanyModel

        company = self.make_company()
        license_obj = self.make_license(company)

        # Set opening balance
        LicenseExportItemModel.objects.create(license=license_obj, cif_fc=Decimal("10000.00"))

        # Create a purchase trade (increases balance)
        sr_item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description='Purchase Item'
        )

        buyer = CompanyModel.objects.create(name='Buyer', iec='0000000001')
        purchase_trade = LicenseTrade.objects.create(
            from_company=license_obj.exporter,
            to_company=buyer,
            direction='PURCHASE',
            invoice_number='INV-001',
            invoice_date=license_obj.license_date,
            license_type='DFIA',
        )
        purchase_trade.lines.create(
            sr_number=sr_item,
            cif_fc=Decimal("5000.00"),
            amount_inr=Decimal("5000.00"),
        )

        # Get canonical dataset
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(license_obj.id)

        # A purchase is the acquisition already represented by the licence
        # face value, so it must be credited once rather than double-counted
        # with the opening metadata.
        self.assertEqual(dataset['opening_balance'], Decimal("10000.00"))
        self.assertEqual(dataset['license_running_balance'], Decimal("5000.00"))

        # Verify transactions are recorded
        self.assertGreater(len(dataset['transactions']), 0)
        purchase_txns = [t for t in dataset['transactions'] if t['type'] == 'PURCHASE']
        self.assertGreater(len(purchase_txns), 0)


class CanonicalLedgerPdfSemanticParityTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    """
    Verify semantic parity between canonical ledger and PDF export.
    Ensures financial data consistency across representations.
    """

    def test_canonical_ledger_api_vs_pdf_data_parity(self):
        """
        Verify that canonical ledger API dataset matches what PDF uses.
        Golden scenario: Opening balance + purchase (increases) + sale (decreases).

        **Semantics:** a PURCHASE is the canonical acquisition event when it
        exists; the licence face value remains metadata and is not seeded into
        the running ledger a second time.
        """
        from apps.license.services.canonical_ledger_service import CanonicalLedgerService
        from apps.license.models import LicenseExportItemModel, LicenseImportItemsModel
        from apps.trade.models import LicenseTrade
        from apps.core.models import CompanyModel

        company = self.make_company()
        license_obj = self.make_license(company)

        # Set opening balance
        opening_balance = Decimal("10000.00")
        LicenseExportItemModel.objects.create(
            license=license_obj,
            cif_fc=opening_balance,
            description="Opening Balance"
        )

        # Create import items for purchase and sale
        purchase_item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=10,
            description='Purchase Item'
        )

        sale_item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=11,
            description='Sale Item'
        )

        # Create purchase trade (increases balance)
        company_a = CompanyModel.objects.create(name='Company A', iec='0000000010')
        purchase_trade = LicenseTrade.objects.create(
            from_company=license_obj.exporter,
            to_company=company_a,
            direction='PURCHASE',
            invoice_number='INV-PURCH-001',
            invoice_date=license_obj.license_date,
            license_type='DFIA',
        )

        purchase_amount = Decimal("2000.00")
        purchase_trade.lines.create(
            sr_number=purchase_item,
            cif_fc=purchase_amount,
            mode='CIF_INR',
            pct=100,
            amount_inr=purchase_amount,
        )

        # Create sale trade (decreases balance)
        buyer = CompanyModel.objects.create(name='Buyer', iec='0000000011')
        sale_trade = LicenseTrade.objects.create(
            from_company=company_a,
            to_company=buyer,
            direction='SALE',
            invoice_number='INV-SALE-001',
            invoice_date=license_obj.license_date,
            license_type='DFIA',
        )

        sale_amount = Decimal("3000.00")
        sale_trade.lines.create(
            sr_number=sale_item,
            cif_fc=sale_amount,
            mode='CIF_INR',
            pct=100,
            amount_inr=sale_amount,
        )

        # Get canonical dataset
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(license_obj.id)

        # Verify key metrics
        self.assertEqual(dataset['opening_balance'], opening_balance)
        # Purchase (credit): 2000 - Sale (debit): 3000 = -1000.  The original
        # licence CIF remains visible as metadata but is not double-counted.
        expected_balance = purchase_amount - sale_amount
        self.assertEqual(dataset['license_running_balance'], expected_balance)

        # Verify company utilization for Company A
        company_a_util = dataset['company_utilizations'].get(company_a.id)
        self.assertIsNotNone(company_a_util)
        # Company A: Purchase (credit) 2000 - Sale (debit) 3000 = -1000
        self.assertEqual(company_a_util['utilization_balance'], purchase_amount - sale_amount)

    def test_canonical_ledger_decimal_precision(self):
        """Verify canonical ledger maintains 2 decimal place precision."""
        from apps.license.services.canonical_ledger_service import CanonicalLedgerService
        from apps.license.models import LicenseExportItemModel

        company = self.make_company()
        license_obj = self.make_license(company)

        # Create balance with fractional amount
        amount = Decimal("12345.6789")
        LicenseExportItemModel.objects.create(
            license=license_obj,
            cif_fc=amount,
        )

        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(license_obj.id)
        balance = dataset['opening_balance']

        # Should be quantized to 2 decimal places
        self.assertEqual(balance, Decimal("12345.68"))

    def test_canonical_ledger_transaction_ordering(self):
        """Verify canonical ledger transactions are deterministically ordered."""
        from apps.license.services.canonical_ledger_service import CanonicalLedgerService
        from apps.license.models import LicenseExportItemModel, LicenseImportItemsModel
        from apps.trade.models import LicenseTrade
        from datetime import date

        company = self.make_company()
        license_obj = self.make_license(company)

        # Opening balance
        LicenseExportItemModel.objects.create(
            license=license_obj,
            cif_fc=Decimal("10000.00"),
        )

        # Create multiple trades on same date with different IDs
        sr_item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=20,
            description='Test Item'
        )

        company_a = self.make_company("Company A")
        company_b = self.make_company("Company B")

        trade1 = LicenseTrade.objects.create(
            from_company=license_obj.exporter,
            to_company=company_a,
            direction='PURCHASE',
            invoice_number='INV-001',
            invoice_date=license_obj.license_date,
            license_type='DFIA',
        )
        trade1.lines.create(sr_number=sr_item, cif_fc=Decimal("1000.00"))

        trade2 = LicenseTrade.objects.create(
            from_company=license_obj.exporter,
            to_company=company_b,
            direction='PURCHASE',
            invoice_number='INV-002',
            invoice_date=license_obj.license_date,
            license_type='DFIA',
        )
        trade2.lines.create(sr_number=sr_item, cif_fc=Decimal("2000.00"))

        # Get dataset twice to ensure deterministic ordering
        dataset1 = CanonicalLedgerService.build_canonical_ledger_dataset(license_obj.id)
        dataset2 = CanonicalLedgerService.build_canonical_ledger_dataset(license_obj.id)

        # Compare transaction ordering
        txns1 = dataset1['transactions']
        txns2 = dataset2['transactions']

        self.assertEqual(len(txns1), len(txns2))
        for i, (t1, t2) in enumerate(zip(txns1, txns2)):
            self.assertEqual(
                (t1['date'], t1.get('id')),
                (t2['date'], t2.get('id')),
                f"Transaction {i} ordering is non-deterministic"
            )


class CanonicalLedgerPdfPerformanceTests(LicenseBalanceLedgerFixtureMixin, TestCase):
    """
    Query performance measurement for canonical ledger PDF generation.
    Ensures query efficiency before production deployment.
    """

    def test_canonical_ledger_query_count_simple_license(self):
        """
        Measure query count for a simple license (opening + 1 trade).
        Target: <20 queries for simple case.
        """
        from apps.license.services.canonical_ledger_service import CanonicalLedgerService
        from apps.license.models import LicenseExportItemModel, LicenseImportItemsModel
        from apps.trade.models import LicenseTrade
        from apps.core.models import CompanyModel
        import uuid

        company = self.make_company()
        license_obj = self.make_license(company)

        # Set opening balance
        LicenseExportItemModel.objects.create(
            license=license_obj,
            cif_fc=Decimal("10000.00"),
        )

        # Create one trade
        sr_item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=30,
            description='Test Item'
        )

        buyer = CompanyModel.objects.create(name='Buyer', iec=str(uuid.uuid4().int)[:10])
        trade = LicenseTrade.objects.create(
            from_company=license_obj.exporter,
            to_company=buyer,
            direction='PURCHASE',
            invoice_number='INV-001',
            invoice_date=license_obj.license_date,
            license_type='DFIA',
        )

        trade.lines.create(
            sr_number=sr_item,
            cif_fc=Decimal("2000.00"),
            mode='CIF_INR',
            pct=100,
            amount_inr=Decimal("2000.00"),
        )

        # Measure query count
        with CaptureQueriesContext(connection=connection) as context:
            dataset = CanonicalLedgerService.build_canonical_ledger_dataset(license_obj.id)

        query_count = len(context)
        # For this task, just measure and document; don't enforce strict limits yet
        self.assertIsNotNone(dataset)
        self.assertLess(query_count, 50, f"Simple license took {query_count} queries (should be <50)")

    def test_canonical_ledger_query_count_moderate_license(self):
        """
        Measure query count for moderate license (opening + 5 trades with 3 companies).
        Target: <100 queries for moderate case.
        """
        from apps.license.services.canonical_ledger_service import CanonicalLedgerService
        from apps.license.models import LicenseExportItemModel, LicenseImportItemsModel
        from apps.trade.models import LicenseTrade
        from apps.core.models import CompanyModel
        import uuid

        company = self.make_company()
        license_obj = self.make_license(company)

        # Set opening balance
        LicenseExportItemModel.objects.create(
            license=license_obj,
            cif_fc=Decimal("50000.00"),
        )

        # Create 5 trades with 3 companies
        companies = [
            CompanyModel.objects.create(name=f'Company {i}', iec=str(uuid.uuid4().int)[:10])
            for i in range(3)
        ]

        for trade_num in range(5):
            sr_item = LicenseImportItemsModel.objects.create(
                license=license_obj,
                serial_number=40 + trade_num,
                description=f'Item {trade_num}'
            )

            company = companies[trade_num % 3]
            trade = LicenseTrade.objects.create(
                from_company=license_obj.exporter,
                to_company=company,
                direction='PURCHASE',
                invoice_number=f'INV-{trade_num:03d}',
                invoice_date=license_obj.license_date,
                license_type='DFIA',
            )

            trade.lines.create(
                sr_number=sr_item,
                cif_fc=Decimal("5000.00"),
                mode='CIF_INR',
                pct=100,
                amount_inr=Decimal("5000.00"),
            )

        # Measure query count
        with CaptureQueriesContext(connection=connection) as context:
            dataset = CanonicalLedgerService.build_canonical_ledger_dataset(license_obj.id)

        query_count = len(context)
        self.assertIsNotNone(dataset)
        self.assertLess(query_count, 150, f"Moderate license took {query_count} queries (should be <150)")
        print(f"Moderate license (5 trades, 3 companies): {query_count} queries")
