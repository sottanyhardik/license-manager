"""
Performance audit for CanonicalLedgerService.

Tests N+1 query issues and overall query performance across ledger scenarios.
"""

from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection

from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.license.services.canonical_ledger_service import CanonicalLedgerService
from apps.trade.models import LicenseTrade
from apps.core.models import CompanyModel


class CanonicalLedgerPerformanceTests(TestCase):
    """Test query performance and N+1 detection."""

    def setUp(self):
        """Create test license and companies."""
        exporter = CompanyModel.objects.create(
            name='Test Exporter',
            iec='0000000001'
        )
        self.license = LicenseDetailsModel.objects.create(
            license_number='PERF-TEST-001',
            exporter=exporter,
            license_date=date(2026, 1, 1),
            license_expiry_date=date(2026, 12, 31),
        )

        self.company_a = CompanyModel.objects.create(name='Company A', iec='0000000002')
        self.company_b = CompanyModel.objects.create(name='Company B', iec='0000000003')
        self.company_c = CompanyModel.objects.create(name='Company C', iec='0000000004')

        self.trade_counter = 0

    def _create_purchase_trade(self, company, amount, date_of_trade=None):
        """Create a PURCHASE trade."""
        if date_of_trade is None:
            date_of_trade = date(2026, 1, 15)

        self.trade_counter += 1
        trade = LicenseTrade.objects.create(
            from_company=self.license.exporter,
            to_company=company,
            direction='PURCHASE',
            invoice_number=f'INV-PERF-{self.trade_counter}',
            invoice_date=date_of_trade,
            license_type='DFIA',
        )

        # Add line item
        sr = LicenseImportItemsModel.objects.create(
            license=self.license,
            serial_number=len(LicenseImportItemsModel.objects.filter(license=self.license)) + 1,
            description='Test Item',
            quantity=Decimal('100.000'),
        )
        trade.lines.create(
            sr_number=sr,
            cif_fc=amount,
            mode='CIF_INR',
            cif_inr=amount,
            pct=Decimal('5.00'),
        )

        return trade

    def test_query_count_small_ledger(self):
        """Test query count with small ledger (3 transactions)."""
        # Create 3 transactions
        self._create_purchase_trade(self.company_a, Decimal('1000.00'), date(2026, 1, 5))
        self._create_purchase_trade(self.company_b, Decimal('2000.00'), date(2026, 1, 15))
        self._create_purchase_trade(self.company_c, Decimal('1500.00'), date(2026, 1, 25))

        with CaptureQueriesContext(connection) as ctx:
            result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        # Verify results
        self.assertIsNotNone(result)
        self.assertIn('license_running_balance', result)
        self.assertIn('transactions', result)
        self.assertIn('company_utilizations', result)

        query_count = len(ctx.captured_queries)
        print(f"\nSmall Ledger Performance:")
        print(f"  Transactions: 3")
        print(f"  Companies: 3")
        print(f"  Query Count: {query_count}")
        print(f"  Expected: ~8-12 (selects + metadata)")

        # Should not be excessive
        self.assertLess(query_count, 15, f"Too many queries: {query_count}")

    def test_query_count_large_ledger(self):
        """Test query count with large ledger (20+ transactions)."""
        # Create 20 transactions
        companies = [self.company_a, self.company_b, self.company_c]
        for i in range(20):
            company = companies[i % 3]
            self._create_purchase_trade(
                company,
                Decimal(str(1000 + i * 100)),
                date(2026, 1, 5 + i)
            )

        with CaptureQueriesContext(connection) as ctx:
            result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        # Verify results
        self.assertIsNotNone(result)
        query_count = len(ctx.captured_queries)
        print(f"\nLarge Ledger Performance:")
        print(f"  Transactions: 20")
        print(f"  Companies: 3")
        print(f"  Query Count: {query_count}")
        print(f"  Expected: ~8-15 (should not scale with transaction count)")

        # Should still be minimal (not growing with transaction count)
        self.assertLess(query_count, 25, f"Too many queries (possible N+1): {query_count}")

    def test_no_n_plus_one_issue(self):
        """Verify no N+1 query pattern."""
        # Create baseline with 3 transactions
        self._create_purchase_trade(self.company_a, Decimal('1000.00'), date(2026, 1, 5))
        self._create_purchase_trade(self.company_b, Decimal('2000.00'), date(2026, 1, 15))
        self._create_purchase_trade(self.company_c, Decimal('1500.00'), date(2026, 1, 25))

        with CaptureQueriesContext(connection) as ctx:
            result_small = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)
        small_query_count = len(ctx.captured_queries)

        # Now add 7 more transactions (total 10)
        for i in range(7):
            self._create_purchase_trade(
                [self.company_a, self.company_b][i % 2],
                Decimal(str(500 + i * 100)),
                date(2026, 2, 5 + i)
            )

        with CaptureQueriesContext(connection) as ctx:
            result_large = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)
        large_query_count = len(ctx.captured_queries)

        print(f"\nN+1 Detection:")
        print(f"  3 transactions: {small_query_count} queries")
        print(f"  10 transactions: {large_query_count} queries")
        print(f"  Growth ratio: {large_query_count / max(small_query_count, 1):.2f}x")

        # Query count should not scale linearly with transaction count
        growth_ratio = large_query_count / max(small_query_count, 1)
        self.assertLess(growth_ratio, 1.5, f"Possible N+1 pattern: {growth_ratio:.2f}x growth")
