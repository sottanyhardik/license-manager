"""
Detailed query breakdown for CanonicalLedgerService.
Shows exactly which queries are executed and in what order.
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


class QueryBreakdownTest(TestCase):
    """Show exact query execution order."""

    def test_query_breakdown_with_5_trades(self):
        """Capture and display all queries."""
        exporter = CompanyModel.objects.create(name='Test Exporter', iec='0000000001')
        license_obj = LicenseDetailsModel.objects.create(
            license_number='BREAKDOWN-TEST',
            exporter=exporter,
            license_date=date(2026, 1, 1),
            license_expiry_date=date(2026, 12, 31),
        )

        company_a = CompanyModel.objects.create(name='Company A', iec='0000000002')
        company_b = CompanyModel.objects.create(name='Company B', iec='0000000003')
        company_c = CompanyModel.objects.create(name='Company C', iec='0000000004')

        # Create 5 trades
        for trade_idx in range(5):
            trade = LicenseTrade.objects.create(
                from_company=exporter,
                to_company=[company_a, company_b, company_c][trade_idx % 3],
                direction='PURCHASE',
                invoice_number=f'INV-BREAKDOWN-{trade_idx}',
                invoice_date=date(2026, 1, 15 + trade_idx),
                license_type='DFIA',
            )
            
            sr = LicenseImportItemsModel.objects.create(
                license=license_obj,
                serial_number=trade_idx + 1,
                description='Test Item',
                quantity=Decimal('100.000'),
            )
            trade.lines.create(
                sr_number=sr,
                cif_fc=Decimal('1000.00'),
                mode='CIF_INR',
                cif_inr=Decimal('1000.00'),
                pct=Decimal('5.00'),
            )

        # Test with query capture
        with CaptureQueriesContext(connection) as ctx:
            result = CanonicalLedgerService.build_canonical_ledger_dataset(license_obj.id)

        print(f"\n=== QUERY BREAKDOWN (5 trades, 3 companies) ===")
        print(f"Total Queries: {len(ctx.captured_queries)}\n")

        for i, query in enumerate(ctx.captured_queries, 1):
            sql = query['sql']
            # Extract table name
            if 'FROM' in sql:
                parts = sql.split('FROM')
                table_part = parts[1].split()[0] if len(parts) > 1 else '?'
                print(f"{i}. {table_part:40} {sql[:100]}...")
            else:
                print(f"{i}. {sql[:140]}...")

        print(f"\n✓ has_purchase_bill: {result['has_purchase_bill']}")
        print(f"✓ purchase_bill_status: {result['purchase_bill_status']}")
        print(f"✓ transactions count: {len(result['transactions'])}")
        print(f"✓ company_utilizations: {len(result['company_utilizations'])}")
        
        # Assert expectations
        self.assertTrue(result['has_purchase_bill'])
        self.assertEqual(result['purchase_bill_status'], 'WITH_PURCHASE_BILL')
        # No export entitlement/opening balance was created in this fixture;
        # the canonical ledger therefore contains exactly the five purchases.
        self.assertEqual(len(result['transactions']), 5)
        self.assertEqual(len(result['company_utilizations']), 3)  # 3 companies
        
        # Query count should be ~7 regardless of trade count
        self.assertLessEqual(len(ctx.captured_queries), 10)
