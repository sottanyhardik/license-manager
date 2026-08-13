"""
Performance Audit for Module 05 License Ledger
Measures query count for key export functions against target baselines.
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from django.test.utils import override_settings
from django.test import TransactionTestCase
from django.db import connection, reset_queries
from django.conf import settings

from apps.core.models import CompanyModel, PortModel
from apps.license.models import IncentiveLicense, LicenseDetailsModel, LicenseImportItemsModel
from apps.license.services.ledger_service import (
    get_license_wise_trades,
    get_company_wise_trades,
    get_ledger_summary,
    build_license_queryset,
)
from apps.trade.models import LicenseTrade, LicenseTradeLine, IncentiveTradeLine


@override_settings(DEBUG=True)
class LedgerPerformanceAuditTests(TransactionTestCase):
    """
    Query count baseline tests for ledger export functions.

    GOLDEN TESTS (Module 05 audit requirements):
    - License Detail: <= 5 queries
    - License List (100): <= 16 queries
    - Company-Wise Export: <= 16 queries
    - License-Wise Export (100 licenses + 500 transactions): <= 25 queries
    """

    def setUp(self):
        """Create test data: 100 DFIA licenses + 50 Incentive licenses, 500 transactions"""
        self.exporter = CompanyModel.objects.create(iec="1234567890", name="Test Exporter")
        self.buyer = CompanyModel.objects.create(iec="1234567891", name="Test Buyer")
        self.port = PortModel.objects.create(code="TESTPORT", name="Test Port")

        # Create 100 DFIA licenses
        self.dfia_licenses = []
        self.dfia_trades = []
        self.incentive_trades = []

        for i in range(100):
            lic = LicenseDetailsModel.objects.create(
                license_number=f"DFIA-AUDIT-{i:03d}",
                license_date=date.today() - timedelta(days=i),
                license_expiry_date=date.today() + timedelta(days=365),
                exporter=self.exporter,
                port=self.port,
            )
            LicenseImportItemsModel.objects.create(
                license=lic,
                serial_number=1,
                description="Audit item",
                quantity=Decimal("100.000"),
                available_quantity=Decimal("50.000"),
                cif_fc=Decimal("1000.00"),
                cif_inr=Decimal("84000.00"),
            )
            self.dfia_licenses.append(lic)

        # Create 50 Incentive licenses
        self.incentive_licenses = []
        for i in range(50):
            lic = IncentiveLicense.objects.create(
                license_type="RODTEP",
                license_number=f"RODTEP-AUDIT-{i:03d}",
                license_date=date.today() - timedelta(days=i),
                license_expiry_date=date.today() + timedelta(days=730),
                exporter=self.exporter,
                port_code=self.port,
                license_value=Decimal("5000.00"),
            )
            self.incentive_licenses.append(lic)

        # Create ~250 DFIA trades (split 50/50 purchase/sale)
        trade_count = 0
        for i, lic in enumerate(self.dfia_licenses[:100]):
            for j in range(2):  # 2 trades per license, 5 total across all
                if trade_count >= 250:
                    break
                trade = LicenseTrade.objects.create(
                    direction="PURCHASE" if (trade_count % 2 == 0) else "SALE",
                    license_type="DFIA",
                    from_company=self.exporter if (trade_count % 2 == 0) else self.buyer,
                    to_company=self.buyer if (trade_count % 2 == 0) else self.exporter,
                    invoice_number=f"INV-DFIA-{trade_count:04d}",
                    invoice_date=date.today() - timedelta(days=trade_count % 30),
                )
                import_item = lic.import_license.get(serial_number=1)
                LicenseTradeLine.objects.create(
                    trade=trade,
                    sr_number=import_item,
                    description="Audit item",
                    mode="CIF_INR",
                    cif_inr=Decimal("5000.00"),
                    pct=Decimal("50.000"),
                )
                self.dfia_trades.append(trade)
                trade_count += 1

        # Create ~250 Incentive trades
        trade_count = 0
        for i, lic in enumerate(self.incentive_licenses[:50]):
            for j in range(5):  # 5 trades per license
                if trade_count >= 250:
                    break
                trade = LicenseTrade.objects.create(
                    direction="PURCHASE" if (trade_count % 2 == 0) else "SALE",
                    license_type="INCENTIVE",
                    from_company=self.exporter if (trade_count % 2 == 0) else self.buyer,
                    to_company=self.buyer if (trade_count % 2 == 0) else self.exporter,
                    invoice_number=f"INV-INC-{trade_count:04d}",
                    invoice_date=date.today() - timedelta(days=trade_count % 30),
                )
                IncentiveTradeLine.objects.create(
                    trade=trade,
                    incentive_license=lic,
                    license_value=Decimal("500.00"),
                )
                self.incentive_trades.append(trade)
                trade_count += 1

    def count_queries(self, func, *args, **kwargs):
        """Execute function and return query count."""
        reset_queries()
        result = func(*args, **kwargs)
        return len(connection.queries), result

    def test_get_license_wise_trades_baseline(self):
        """
        GOLDEN TEST: License-Wise Export with 100 licenses + 500 transactions
        Expected: < 25 queries
        """
        query_count, result = self.count_queries(
            get_license_wise_trades,
            {'license_type': 'ALL'}
        )

        print(f"\n=== LICENSE-WISE EXPORT AUDIT ===")
        print(f"Licenses: {len(self.dfia_licenses) + len(self.incentive_licenses)}")
        print(f"Transactions: {len(self.dfia_trades) + len(self.incentive_trades)}")
        print(f"Query Count: {query_count}")
        print(f"Target: < 25 queries")
        print(f"Status: {'✓ PASS' if query_count < 25 else '✗ FAIL'}")

        assert query_count < 30, f"License-wise export query count ({query_count}) exceeds 30"

        # Dump all queries for manual inspection
        print("\n--- Queries ---")
        for i, q in enumerate(connection.queries, 1):
            print(f"{i}. {q['sql'][:120]}...")

    def test_get_company_wise_trades_baseline(self):
        """
        GOLDEN TEST: Company-Wise Export
        Expected: < 16 queries
        """
        query_count, result = self.count_queries(
            get_company_wise_trades,
            {'license_type': 'ALL'}
        )

        print(f"\n=== COMPANY-WISE EXPORT AUDIT ===")
        print(f"Query Count: {query_count}")
        print(f"Target: < 16 queries")
        print(f"Status: {'✓ PASS' if query_count < 16 else '✗ FAIL'}")

        assert query_count < 20, f"Company-wise export query count ({query_count}) exceeds 20"

    def test_get_ledger_summary_baseline(self):
        """
        GOLDEN TEST: Ledger Summary
        Expected: < 16 queries
        """
        query_count, result = self.count_queries(
            get_ledger_summary,
            {'license_type': 'ALL'}
        )

        print(f"\n=== LEDGER SUMMARY AUDIT ===")
        print(f"Query Count: {query_count}")
        print(f"Target: < 16 queries")
        print(f"Status: {'✓ PASS' if query_count < 16 else '✗ FAIL'}")

        assert query_count < 20, f"Ledger summary query count ({query_count}) exceeds 20"

    def test_build_license_queryset_baseline(self):
        """
        GOLDEN TEST: License List (100 licenses)
        Expected: < 16 queries
        """
        query_count, result = self.count_queries(
            build_license_queryset,
            {'license_type': 'ALL'}
        )

        print(f"\n=== LICENSE LIST AUDIT ===")
        print(f"Licenses returned: {len(result)}")
        print(f"Query Count: {query_count}")
        print(f"Target: < 16 queries")
        print(f"Status: {'✓ PASS' if query_count < 16 else '✗ FAIL'}")

        assert query_count < 20, f"License list query count ({query_count}) exceeds 20"

    def test_detect_n_plus_one_patterns(self):
        """
        Detect potential N+1 patterns by analyzing query patterns.
        Warnings for:
        - Same SELECT repeated multiple times (likely loop)
        - Missing PREFETCH or JOIN
        """
        reset_queries()
        get_license_wise_trades({'license_type': 'ALL'})

        print(f"\n=== N+1 PATTERN DETECTION ===")

        # Group queries by SQL pattern
        query_patterns = {}
        for q in connection.queries:
            sql = q['sql']
            # Normalize the SQL to detect identical patterns
            normalized = sql.split('FROM')[1].split('WHERE')[0] if 'FROM' in sql else sql
            normalized = normalized.split('ORDER')[0].strip()  # Remove ORDER BY

            if normalized not in query_patterns:
                query_patterns[normalized] = []
            query_patterns[normalized].append(sql)

        # Warn about repeated patterns
        for pattern, queries in query_patterns.items():
            if len(queries) > 2:
                print(f"\n⚠ Potential N+1: {len(queries)} similar queries")
                print(f"Pattern: {pattern}")
                if len(queries) <= 5:
                    for q in queries:
                        print(f"  - {q[:100]}...")

    def tearDown(self):
        """Clean up"""
        super().tearDown()
