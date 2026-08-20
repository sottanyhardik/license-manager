"""
Test suite for CanonicalLedgerService.

Tests all 14 golden scenarios from LEDGER_GOLDEN_DATASET.md to verify:
- License running balance calculation (correct and deterministic)
- Company utilization (independent per-company calculation)
- COMMISSION exclusion (visible but not counted)
- Decimal precision (exactly 2 decimal places)
- Deterministic ordering (date + ID)
- Edge cases (empty, zero, large datasets)

**GATE 4A REQUIREMENT:** All 14 scenarios must PASS before proceeding to Gate 4B.
"""

from decimal import Decimal
from datetime import date, timedelta
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.license.models import (
    LicenseDetailsModel,
    LicenseImportItemsModel,
    LicenseExportItemModel,
    IncentiveLicense,
)
from apps.license.services.canonical_ledger_service import CanonicalLedgerService
from apps.trade.models import LicenseTrade, IncentiveTradeLine
from apps.core.models import (
    CompanyModel,
    PortModel,
    ItemNameModel,
    SionNormClassModel,
    HeadSIONNormsModel,
)
from apps.bill_of_entry.models import BillOfEntryModel, RowDetails


class CanonicalLedgerServiceTestBase(TestCase):
    """Base class for canonical ledger tests with helper methods."""

    def setUp(self):
        """Create test license and companies."""
        self.license = LicenseDetailsModel.objects.create(
            license_number='TEST-LICENSE-001',
            exporter=CompanyModel.objects.create(name='Test Exporter', iec='0000000001'),
            license_date=date(2026, 1, 1),
            license_expiry_date=date(2026, 12, 31),
        )

        self.company_a = CompanyModel.objects.create(name='Company A', iec='0000000002')
        self.company_b = CompanyModel.objects.create(name='Company B', iec='0000000003')
        self.company_c = CompanyModel.objects.create(name='Company C', iec='0000000004')
        self._sr_counter = 0

    def _set_opening_balance(self, amount: Decimal):
        """Create export items that contribute to opening balance (computed property)."""
        if amount > 0:
            LicenseExportItemModel.objects.create(
                license=self.license,
                description='Opening Balance Export',
                cif_fc=amount,
            )

    def _get_next_sr_number(self):
        """Get next serial number for sr_number creation."""
        self._sr_counter += 1
        return self._sr_counter

    def assert_ledger_balance(self, license_id, expected_balance):
        """Assert that canonical ledger returns expected balance."""
        result = CanonicalLedgerService.build_canonical_ledger_dataset(license_id)
        actual = result['license_running_balance']
        self.assertEqual(
            actual,
            Decimal(str(expected_balance)).quantize(Decimal('0.01')),
            f"License balance mismatch: expected {expected_balance}, got {actual}"
        )

    def assert_company_utilization(self, license_id, company_id, expected_balance):
        """Assert that company utilization matches expected."""
        result = CanonicalLedgerService.build_canonical_ledger_dataset(license_id)
        util = result['company_utilizations'].get(company_id)
        self.assertIsNotNone(util, f"Company {company_id} not found in utilizations")
        actual = util['utilization_balance']
        self.assertEqual(
            actual,
            Decimal(str(expected_balance)).quantize(Decimal('0.01')),
            f"Company utilization mismatch: expected {expected_balance}, got {actual}"
        )

    def _create_purchase_trade(self, license, company, amount, date_of_trade=None):
        """Create a PURCHASE trade (company buys from exporter)."""
        if date_of_trade is None:
            date_of_trade = date(2026, 1, 15)

        trade = LicenseTrade.objects.create(
            from_company=license.exporter,
            to_company=company,
            direction='PURCHASE',
            invoice_number=f'INV-PURCH-{self._get_next_sr_number()}',
            invoice_date=date_of_trade,
            license_type='DFIA',
        )

        # Add line item with CIF amount
        sr_number = LicenseImportItemsModel.objects.create(
            license=license,
            serial_number=self._get_next_sr_number(),
            description='Test Item'
        )
        trade.lines.create(
            sr_number=sr_number,
            cif_fc=amount,
            mode='CIF_INR',
            pct=100,
            amount_inr=amount,
        )

        return trade

    def _create_sale_trade(self, license, company, amount, date_of_trade=None):
        """Create a SALE trade (company sells to buyer)."""
        if date_of_trade is None:
            date_of_trade = date(2026, 2, 1)

        trade = LicenseTrade.objects.create(
            from_company=company,
            to_company=CompanyModel.objects.create(name='Buyer', iec=f'00{1000 + self._get_next_sr_number():06d}'),
            direction='SALE',
            invoice_number=f'INV-SALE-{self._get_next_sr_number()}',
            invoice_date=date_of_trade,
            license_type='DFIA',
        )

        # Add line item with CIF amount
        sr_number = LicenseImportItemsModel.objects.create(
            license=license,
            serial_number=self._get_next_sr_number(),
            description='Test Item'
        )
        trade.lines.create(
            sr_number=sr_number,
            cif_fc=amount,
            mode='CIF_INR',
            pct=100,
            amount_inr=amount,
        )

        return trade

    def _create_commission_trade(self, license, company, amount, direction='COMMISSION_PURCHASE', date_of_trade=None):
        """Create a COMMISSION trade."""
        if date_of_trade is None:
            date_of_trade = date(2026, 2, 1)

        if direction == 'COMMISSION_PURCHASE':
            from_company = license.exporter
            to_company = company
        else:
            from_company = company
            to_company = license.exporter

        trade = LicenseTrade.objects.create(
            from_company=from_company,
            to_company=to_company,
            direction=direction,
            invoice_number=f'INV-COMM-{self._get_next_sr_number()}',
            invoice_date=date_of_trade,
            license_type='DFIA',
        )

        # Add line item with CIF amount
        sr_number = LicenseImportItemsModel.objects.create(
            license=license,
            serial_number=self._get_next_sr_number(),
            description='Commission'
        )
        trade.lines.create(
            sr_number=sr_number,
            cif_fc=amount,
            mode='CIF_INR',
            pct=100,
            amount_inr=amount,
        )

        return trade


# ========== GOLDEN SCENARIOS (14 total) ==========

class Scenario1SingleCompanySimpleFlow(CanonicalLedgerServiceTestBase):
    """
    Scenario 1: Single License, Single Company, Simple Flow

    Opening/acquisition metadata: 1000.00
    + PURCHASE (A): 500.00  → Balance: 500.00
    - SALE (A): 200.00      → Balance: 300.00

    Expected:
    - License balance: 300.00; the opening is the same acquisition represented
      by the valid purchase and must not be counted twice.
    - Company A utilization: 300.00
    """

    def test_scenario_1_single_company(self):
        # Setup
        self._set_opening_balance(Decimal('1000.00'))

        self._create_purchase_trade(self.license, self.company_a, Decimal('500.00'), date(2026, 1, 15))
        self._create_sale_trade(self.license, self.company_a, Decimal('200.00'), date(2026, 2, 1))

        # Execute
        result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        # Assert
        self.assertEqual(result['license_running_balance'], Decimal('300.00'))
        self.assertEqual(result['company_utilizations'][self.company_a.id]['utilization_balance'], Decimal('300.00'))
        self.assertEqual(len(result['transactions']), 2)  # PURCHASE + SALE; no duplicate opening


class PurchasedLicenseOpeningPolicyTests(CanonicalLedgerServiceTestBase):
    def test_purchase_credit_is_counted_once_for_canonical_balance(self):
        """89,283.10 purchase − 80,359.10 sale must be 8,924.00, not 98,207.10."""
        self._set_opening_balance(Decimal('89283.10'))
        self._create_purchase_trade(self.license, self.company_a, Decimal('89283.10'), date(2026, 1, 15))
        self._create_sale_trade(self.license, self.company_a, Decimal('80359.10'), date(2026, 2, 1))

        result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        self.assertEqual(result['opening_balance'], Decimal('0.00'))
        self.assertEqual(result['license_running_balance'], Decimal('8924.00'))
        self.assertEqual(result['transactions'][-1]['license_running_balance'], Decimal('8924.00'))
        self.assertEqual([row['type'] for row in result['transactions']], ['PURCHASE', 'SALE'])

    def test_purchase_only_uses_purchase_credit_not_duplicate_opening(self):
        self._set_opening_balance(Decimal('89283.10'))
        self._create_purchase_trade(self.license, self.company_a, Decimal('89283.10'))

        result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        self.assertEqual(result['license_running_balance'], Decimal('89283.10'))
        self.assertEqual(result['transactions'][0]['type'], 'PURCHASE')

    def test_zero_purchase_does_not_suppress_legacy_opening_balance(self):
        """A zero-value non-acquisition is not a valid purchase credit."""
        self._set_opening_balance(Decimal('89283.10'))
        self._create_purchase_trade(self.license, self.company_a, Decimal('0.00'))

        result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        self.assertEqual(result['license_running_balance'], Decimal('89283.10'))
        self.assertEqual(result['transactions'][0]['type'], 'OPENING')

    def test_multiple_sales_are_subtracted_once_in_ledger_order(self):
        self._set_opening_balance(Decimal('89283.10'))
        self._create_purchase_trade(self.license, self.company_a, Decimal('89283.10'), date(2026, 1, 15))
        self._create_sale_trade(self.license, self.company_a, Decimal('30000.00'), date(2026, 2, 1))
        self._create_sale_trade(self.license, self.company_a, Decimal('50359.10'), date(2026, 2, 2))

        result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        self.assertEqual(result['license_running_balance'], Decimal('8924.00'))
        self.assertEqual(
            [row['license_running_balance'] for row in result['transactions']],
            [Decimal('89283.10'), Decimal('59283.10'), Decimal('8924.00')],
        )

    def test_complete_sale_closes_purchased_license_to_zero(self):
        self._set_opening_balance(Decimal('89283.10'))
        self._create_purchase_trade(self.license, self.company_a, Decimal('89283.10'))
        self._create_sale_trade(self.license, self.company_a, Decimal('89283.10'))

        result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        self.assertEqual(result['license_running_balance'], Decimal('0.00'))


class Scenario2MultipleCompanies(CanonicalLedgerServiceTestBase):
    """
    Scenario 2: Multiple Companies (A, B, C)

    Opening: 2000.00
    + PURCHASE (A): 400.00  → 2400.00
    - SALE (A): 150.00      → 2250.00
    + PURCHASE (B): 600.00  → 2850.00
    - SALE (B): 300.00      → 2550.00
    + PURCHASE (C): 200.00  → 2750.00
    - SALE (C): 100.00      → 2650.00

    Expected:
    - License balance: 2650.00
    - Company A: 250.00
    - Company B: 300.00
    - Company C: 100.00
    - Sum of companies ≠ license balance (by design)
    """

    def test_scenario_2_multiple_companies(self):
        self._set_opening_balance(Decimal('2000.00'))

        self._create_purchase_trade(self.license, self.company_a, Decimal('400.00'), date(2026, 1, 10))
        self._create_sale_trade(self.license, self.company_a, Decimal('150.00'), date(2026, 1, 20))
        self._create_purchase_trade(self.license, self.company_b, Decimal('600.00'), date(2026, 2, 1))
        self._create_sale_trade(self.license, self.company_b, Decimal('300.00'), date(2026, 2, 15))
        self._create_purchase_trade(self.license, self.company_c, Decimal('200.00'), date(2026, 3, 1))
        self._create_sale_trade(self.license, self.company_c, Decimal('100.00'), date(2026, 3, 15))

        result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        # Old result 2,650.00 included the 2,000.00 acquisition twice.
        self.assertEqual(result['license_running_balance'], Decimal('650.00'))
        self.assertEqual(result['company_utilizations'][self.company_a.id]['utilization_balance'], Decimal('250.00'))
        self.assertEqual(result['company_utilizations'][self.company_b.id]['utilization_balance'], Decimal('300.00'))
        self.assertEqual(result['company_utilizations'][self.company_c.id]['utilization_balance'], Decimal('100.00'))


class Scenario3CommissionExcluded(CanonicalLedgerServiceTestBase):
    """
    Scenario 3: COMMISSION Exclusion (Not Counted)

    Opening: 500.00
    + PURCHASE (A): 300.00       → 800.00
    + COMMISSION (B): 100.00     → 800.00 (NOT counted, visible only)
    - SALE (A): 80.00            → 720.00

    Expected:
    - License balance: 720.00 (NOT 820.00)
    - Company A: 220.00
    - Company B: 0.00 (COMMISSION not counted)
    - COMMISSION rows visible but not counted
    """

    def test_scenario_3_commission_excluded(self):
        self._set_opening_balance(Decimal('500.00'))

        self._create_purchase_trade(self.license, self.company_a, Decimal('300.00'), date(2026, 1, 15))
        self._create_commission_trade(
            self.license, self.company_b, Decimal('100.00'),
            direction='COMMISSION_PURCHASE', date_of_trade=date(2026, 2, 1)
        )
        self._create_sale_trade(self.license, self.company_a, Decimal('80.00'), date(2026, 2, 15))

        result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        # CRITICAL: Balance does NOT include COMMISSION
        # Old result 720.00 included the 500.00 acquisition twice.
        self.assertEqual(result['license_running_balance'], Decimal('220.00'))
        self.assertEqual(result['company_utilizations'][self.company_a.id]['utilization_balance'], Decimal('220.00'))

        # Company B should have 0 utilization (COMMISSION not counted)
        if self.company_b.id in result['company_utilizations']:
            self.assertEqual(result['company_utilizations'][self.company_b.id]['utilization_balance'], Decimal('0.00'))

        # COMMISSION row must be visible
        commission_rows = [t for t in result['transactions'] if t['is_commission']]
        self.assertEqual(len(commission_rows), 1)


class Scenario4CompanyIsolation(CanonicalLedgerServiceTestBase):
    """
    Scenario 4: Company Isolation (Independent Calculations)

    Tests that adding Company B doesn't change Company A balance.
    """

    def test_scenario_4_company_isolation(self):
        self._set_opening_balance(Decimal('0.00'))

        self._create_purchase_trade(self.license, self.company_a, Decimal('500.00'), date(2026, 1, 10))
        self._create_sale_trade(self.license, self.company_a, Decimal('200.00'), date(2026, 1, 20))
        self._create_purchase_trade(self.license, self.company_b, Decimal('800.00'), date(2026, 2, 10))
        self._create_sale_trade(self.license, self.company_b, Decimal('300.00'), date(2026, 2, 20))

        result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        # Company A balance unchanged by Company B
        self.assertEqual(result['company_utilizations'][self.company_a.id]['utilization_balance'], Decimal('300.00'))
        self.assertEqual(result['company_utilizations'][self.company_b.id]['utilization_balance'], Decimal('500.00'))
        self.assertEqual(result['license_running_balance'], Decimal('800.00'))


class Scenario5DecimalPrecision(CanonicalLedgerServiceTestBase):
    """
    Scenario 5: Decimal Precision (2 Decimal Places)

    Tests that all values maintain exactly 2 decimal places.
    """

    def test_scenario_5_decimal_precision(self):
        self._set_opening_balance(Decimal('1000.00'))

        self._create_purchase_trade(self.license, self.company_a, Decimal('123.45'), date(2026, 1, 15))
        self._create_sale_trade(self.license, self.company_a, Decimal('67.89'), date(2026, 2, 1))

        result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        # Must be exactly 2 decimal places
        balance = result['license_running_balance']
        # Old result 1,055.56 included the 1,000.00 acquisition twice.
        self.assertEqual(balance, Decimal('55.56'))
        self.assertEqual(str(balance), '55.56')

        company_balance = result['company_utilizations'][self.company_a.id]['utilization_balance']
        self.assertEqual(company_balance, Decimal('55.56'))


class Scenario6SameDateOrdering(CanonicalLedgerServiceTestBase):
    """
    Scenario 6: Same-Date Transaction Ordering (Deterministic)

    Multiple transactions on same date must be ordered by ID deterministically.
    """

    def test_scenario_6_same_date_ordering(self):
        self._set_opening_balance(Decimal('0.00'))

        # Create 3 transactions on the same date
        # They will be ordered by trade ID (deterministic)
        txn_date = date(2026, 1, 15)
        trade1 = self._create_purchase_trade(self.license, self.company_a, Decimal('100.00'), txn_date)
        trade2 = self._create_sale_trade(self.license, self.company_a, Decimal('30.00'), txn_date)
        trade3 = self._create_purchase_trade(self.license, self.company_a, Decimal('50.00'), txn_date)

        result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        # Final balance must be deterministic (120.00)
        self.assertEqual(result['license_running_balance'], Decimal('120.00'))

        # Running again should produce same result
        result2 = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)
        self.assertEqual(result2['license_running_balance'], result['license_running_balance'])


class Scenario7ZeroAmountTransactions(CanonicalLedgerServiceTestBase):
    """
    Scenario 7: Zero-Amount Transactions

    Zero-amount transactions should be visible but not affect balance.
    """

    def test_scenario_7_zero_amount(self):
        self._set_opening_balance(Decimal('1000.00'))

        self._create_purchase_trade(self.license, self.company_a, Decimal('0.00'), date(2026, 1, 15))
        self._create_sale_trade(self.license, self.company_a, Decimal('0.00'), date(2026, 1, 20))
        self._create_purchase_trade(self.license, self.company_a, Decimal('100.00'), date(2026, 2, 1))

        result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        # Zero-amount transactions should not affect balance
        # The positive PURCHASE is the acquisition; zero PURCHASE does not alter it.
        self.assertEqual(result['license_running_balance'], Decimal('100.00'))
        self.assertEqual(result['company_utilizations'][self.company_a.id]['utilization_balance'], Decimal('100.00'))


class Scenario9EmptyLedger(CanonicalLedgerServiceTestBase):
    """
    Scenario 9: Empty Ledger (No Transactions)

    License with no transactions should show zero balances.
    """

    def test_scenario_9_empty_ledger(self):
        # No trades created
        result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        self.assertEqual(result['license_running_balance'], Decimal('0.00'))
        self.assertEqual(len(result['transactions']), 0)


class Scenario10CommissionOnly(CanonicalLedgerServiceTestBase):
    """
    Scenario 10: COMMISSION-Only Transactions

    Ledger with only COMMISSION should show unchanged balance.
    """

    def test_scenario_10_commission_only(self):
        self._set_opening_balance(Decimal('1000.00'))

        self._create_commission_trade(
            self.license, self.company_b, Decimal('100.00'),
            direction='COMMISSION_PURCHASE', date_of_trade=date(2026, 1, 15)
        )
        self._create_commission_trade(
            self.license, self.company_b, Decimal('50.00'),
            direction='COMMISSION_PURCHASE', date_of_trade=date(2026, 2, 1)
        )
        self._create_commission_trade(
            self.license, self.company_c, Decimal('200.00'),
            direction='COMMISSION_PURCHASE', date_of_trade=date(2026, 3, 1)
        )

        result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        # Balance unchanged (COMMISSION not counted)
        self.assertEqual(result['license_running_balance'], Decimal('1000.00'))

        # All company balances 0 (COMMISSION not counted)
        if self.company_b.id in result['company_utilizations']:
            self.assertEqual(result['company_utilizations'][self.company_b.id]['utilization_balance'], Decimal('0.00'))
        if self.company_c.id in result['company_utilizations']:
            self.assertEqual(result['company_utilizations'][self.company_c.id]['utilization_balance'], Decimal('0.00'))

        # COMMISSION rows visible
        commission_rows = [t for t in result['transactions'] if t['is_commission']]
        self.assertEqual(len(commission_rows), 3)


class Scenario12InterleavedCompanies(CanonicalLedgerServiceTestBase):
    """
    Scenario 12: Interleaved Company Transactions

    Companies interleaved (A, B, A, C, B, A) should calculate correctly.
    """

    def test_scenario_12_interleaved_companies(self):
        self._set_opening_balance(Decimal('3000.00'))

        self._create_purchase_trade(self.license, self.company_a, Decimal('100.00'), date(2026, 1, 10))
        self._create_purchase_trade(self.license, self.company_b, Decimal('200.00'), date(2026, 1, 15))
        self._create_sale_trade(self.license, self.company_a, Decimal('50.00'), date(2026, 1, 20))
        self._create_purchase_trade(self.license, self.company_c, Decimal('150.00'), date(2026, 2, 1))
        self._create_sale_trade(self.license, self.company_b, Decimal('100.00'), date(2026, 2, 15))
        self._create_purchase_trade(self.license, self.company_a, Decimal('75.00'), date(2026, 3, 1))

        result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        # Old result 3,375.00 included the 3,000.00 acquisition twice.
        self.assertEqual(result['license_running_balance'], Decimal('375.00'))
        self.assertEqual(result['company_utilizations'][self.company_a.id]['utilization_balance'], Decimal('125.00'))
        self.assertEqual(result['company_utilizations'][self.company_b.id]['utilization_balance'], Decimal('100.00'))
        self.assertEqual(result['company_utilizations'][self.company_c.id]['utilization_balance'], Decimal('150.00'))


class Scenario13MultipleCompaniesWithCommission(CanonicalLedgerServiceTestBase):
    """
    Scenario 13: Multiple Companies with COMMISSION Mix
    """

    def test_scenario_13_multiple_companies_with_commission(self):
        self._set_opening_balance(Decimal('2000.00'))

        self._create_purchase_trade(self.license, self.company_a, Decimal('500.00'), date(2026, 1, 10))
        self._create_commission_trade(
            self.license, self.company_a, Decimal('25.00'),
            direction='COMMISSION_PURCHASE', date_of_trade=date(2026, 1, 15)
        )
        self._create_sale_trade(self.license, self.company_a, Decimal('200.00'), date(2026, 1, 20))
        self._create_purchase_trade(self.license, self.company_b, Decimal('800.00'), date(2026, 2, 1))
        self._create_commission_trade(
            self.license, self.company_c, Decimal('50.00'),
            direction='COMMISSION_PURCHASE', date_of_trade=date(2026, 2, 15)
        )
        self._create_purchase_trade(self.license, self.company_c, Decimal('300.00'), date(2026, 3, 1))
        self._create_sale_trade(self.license, self.company_b, Decimal('300.00'), date(2026, 3, 15))

        result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        # Old result 3,100.00 included the 2,000.00 acquisition twice.
        self.assertEqual(result['license_running_balance'], Decimal('1100.00'))
        self.assertEqual(result['company_utilizations'][self.company_a.id]['utilization_balance'], Decimal('300.00'))
        self.assertEqual(result['company_utilizations'][self.company_b.id]['utilization_balance'], Decimal('500.00'))
        self.assertEqual(result['company_utilizations'][self.company_c.id]['utilization_balance'], Decimal('300.00'))


class Scenario8LargeDataset(CanonicalLedgerServiceTestBase):
    """
    Scenario 8: Large Transaction Count (100+ Transactions)

    Purpose: Verify system handles large datasets correctly without accumulation errors or truncation.

    Structure:
    - Opening: 10000.00
    - Company A: 50 transactions (mix of PURCHASE/SALE)
    - Company B: 25 transactions (mix of PURCHASE/SALE/COMMISSION)
    - Company C: 26 transactions (mix of PURCHASE/SALE/COMMISSION)
    - Total: 101+ transactions

    Expected:
    - All transactions included (no truncation)
    - Final balance correct (sum of all balance-affecting txns)
    - No accumulation errors
    - Running balance sequence complete
    """

    def test_scenario_8_large_dataset(self):
        self._set_opening_balance(Decimal('10000.00'))

        # Valid purchases establish this licence's acquisition; do not add the
        # same 10,000.00 opening metadata to the complete trade history.
        running_total = Decimal('0.00')

        # Company A: 50 transactions
        for i in range(25):
            amt = Decimal(str(100.00 + i * 0.50))
            self._create_purchase_trade(self.license, self.company_a, amt, date(2026, 1, 1) + timedelta(days=i))
            running_total += amt

        for i in range(25):
            amt = Decimal(str(50.00 + i * 0.25))
            self._create_sale_trade(self.license, self.company_a, amt, date(2026, 2, 1) + timedelta(days=i))
            running_total -= amt

        # Company B: 25 transactions (mixed with COMMISSION)
        for i in range(12):
            amt = Decimal(str(200.00 + i * 1.00))
            self._create_purchase_trade(self.license, self.company_b, amt, date(2026, 3, 1) + timedelta(days=i*2))
            running_total += amt

        for i in range(8):
            amt = Decimal(str(100.00 + i * 0.50))
            self._create_sale_trade(self.license, self.company_b, amt, date(2026, 4, 1) + timedelta(days=i*2))
            running_total -= amt

        # COMMISSION (not counted but included)
        for i in range(5):
            amt = Decimal(str(25.00 + i * 0.10))
            self._create_commission_trade(
                self.license, self.company_b, amt,
                direction='COMMISSION_PURCHASE', date_of_trade=date(2026, 5, 1) + timedelta(days=i)
            )

        # Company C: 26 transactions (mixed with COMMISSION)
        for i in range(13):
            amt = Decimal(str(150.00 + i * 0.75))
            self._create_purchase_trade(self.license, self.company_c, amt, date(2026, 6, 1) + timedelta(days=i*2))
            running_total += amt

        for i in range(8):
            amt = Decimal(str(75.00 + i * 0.30))
            self._create_sale_trade(self.license, self.company_c, amt, date(2026, 7, 1) + timedelta(days=i*2))
            running_total -= amt

        # COMMISSION (not counted but included)
        for i in range(5):
            amt = Decimal(str(30.00 + i * 0.15))
            self._create_commission_trade(
                self.license, self.company_c, amt,
                direction='COMMISSION_PURCHASE', date_of_trade=date(2026, 8, 1) + timedelta(days=i)
            )

        result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        # Verify: all transactions included (100+ txns)
        transaction_count = len(result['transactions'])
        self.assertGreaterEqual(transaction_count, 100, f"Expected 100+ transactions, got {transaction_count}")

        # Verify: final balance is correct
        self.assertEqual(result['license_running_balance'], running_total.quantize(Decimal('0.01')))

        # Verify: all companies present
        self.assertIn(self.company_a.id, result['company_utilizations'])
        self.assertIn(self.company_b.id, result['company_utilizations'])
        self.assertIn(self.company_c.id, result['company_utilizations'])

        # Verify: COMMISSION excluded from balance
        commission_rows = [t for t in result['transactions'] if t['is_commission']]
        self.assertEqual(len(commission_rows), 10)  # 5 from B, 5 from C


class Scenario11OpeningAndCompanyBalances(CanonicalLedgerServiceTestBase):
    """
    Scenario 11: Opening + Company Balances Only (No Mixed Transactions)

    Purpose: Verify ledger with opening and per-company activity (companies grouped, not interleaved).

    Structure:
    - Opening: 5000.00
    - Company A: PURCHASE 1000 + 1000, SALE 500 (all sequential)
    - Company B: PURCHASE 2000, SALE 1000 (all sequential)

    Expected:
    - License balance: 2500.00 (the 5000.00 opening is represented by purchases)
    - Company A: 1500.00
    - Company B: 1000.00
    """

    def test_scenario_11_opening_and_company_balances(self):
        self._set_opening_balance(Decimal('5000.00'))

        # Company A: all transactions grouped
        self._create_purchase_trade(self.license, self.company_a, Decimal('1000.00'), date(2026, 1, 15))
        self._create_purchase_trade(self.license, self.company_a, Decimal('1000.00'), date(2026, 1, 20))
        self._create_sale_trade(self.license, self.company_a, Decimal('500.00'), date(2026, 1, 25))

        # Company B: all transactions grouped
        self._create_purchase_trade(self.license, self.company_b, Decimal('2000.00'), date(2026, 2, 1))
        self._create_sale_trade(self.license, self.company_b, Decimal('1000.00'), date(2026, 2, 10))

        result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        # License balance: 5000 + 1000 + 1000 - 500 + 2000 - 1000 = 7500
        # Old result 7,500.00 included the 5,000.00 acquisition twice.
        self.assertEqual(result['license_running_balance'], Decimal('2500.00'))

        # Company A: 1000 + 1000 - 500 = 1500
        self.assertEqual(result['company_utilizations'][self.company_a.id]['utilization_balance'], Decimal('1500.00'))

        # Company B: 2000 - 1000 = 1000
        self.assertEqual(result['company_utilizations'][self.company_b.id]['utilization_balance'], Decimal('1000.00'))


class Scenario14ComprehensiveRealWorld(CanonicalLedgerServiceTestBase):
    """
    Scenario 14: Real-World Multi-Company Scenario (Comprehensive)

    Purpose: Comprehensive scenario combining all features: opening, multiple companies, COMMISSION,
    interleaving, spanning months. This is the master golden dataset.

    Structure:
    - Opening: 10000.00
    - 3 companies (A, B, C)
    - 12 transactions total (transactions interleaved, mix of PURCHASE/SALE/COMMISSION)
    - Spans 4 months

    Expected:
    - License balance: 4800.00 (the 10000.00 opening is represented by purchases)
    - Company A: 2100.00
    - Company B: 2000.00
    - Company C: 700.00
    - Opening counted once
    - COMMISSION excluded (3 rows visible)
    """

    def test_scenario_14_comprehensive_real_world(self):
        self._set_opening_balance(Decimal('10000.00'))

        # Transactions in chronological order with interleaving
        # Txn 1: Opening (auto-created)
        # Txn 2: A PURCHASE 2500
        self._create_purchase_trade(self.license, self.company_a, Decimal('2500.00'), date(2026, 1, 15))

        # Txn 3: A COMMISSION 125 (not counted)
        self._create_commission_trade(
            self.license, self.company_a, Decimal('125.00'),
            direction='COMMISSION_PURCHASE', date_of_trade=date(2026, 1, 20)
        )

        # Txn 4: A SALE 1000
        self._create_sale_trade(self.license, self.company_a, Decimal('1000.00'), date(2026, 2, 1))

        # Txn 5: B PURCHASE 3500
        self._create_purchase_trade(self.license, self.company_b, Decimal('3500.00'), date(2026, 2, 10))

        # Txn 6: C PURCHASE 1500
        self._create_purchase_trade(self.license, self.company_c, Decimal('1500.00'), date(2026, 2, 15))

        # Txn 7: B COMMISSION 175 (not counted)
        self._create_commission_trade(
            self.license, self.company_b, Decimal('175.00'),
            direction='COMMISSION_PURCHASE', date_of_trade=date(2026, 2, 20)
        )

        # Txn 8: C SALE 800
        self._create_sale_trade(self.license, self.company_c, Decimal('800.00'), date(2026, 3, 1))

        # Txn 9: A PURCHASE 1200
        self._create_purchase_trade(self.license, self.company_a, Decimal('1200.00'), date(2026, 3, 10))

        # Txn 10: B SALE 1500
        self._create_sale_trade(self.license, self.company_b, Decimal('1500.00'), date(2026, 3, 20))

        # Txn 11: C COMMISSION 100 (not counted)
        self._create_commission_trade(
            self.license, self.company_c, Decimal('100.00'),
            direction='COMMISSION_PURCHASE', date_of_trade=date(2026, 4, 1)
        )

        # Txn 12: A SALE 600
        self._create_sale_trade(self.license, self.company_a, Decimal('600.00'), date(2026, 4, 15))

        result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        # Verify final balance
        # Purchases 8,700 − sales 3,900 = 4,800.  The old 14,800.00 result
        # counted the 10,000.00 acquisition once as opening and again as trade.
        self.assertEqual(result['license_running_balance'], Decimal('4800.00'))

        # Company A: 2500 - 1000 + 1200 - 600 = 2100
        self.assertEqual(result['company_utilizations'][self.company_a.id]['utilization_balance'], Decimal('2100.00'))

        # Company B: 3500 - 1500 = 2000
        self.assertEqual(result['company_utilizations'][self.company_b.id]['utilization_balance'], Decimal('2000.00'))

        # Company C: 1500 - 800 = 700
        self.assertEqual(result['company_utilizations'][self.company_c.id]['utilization_balance'], Decimal('700.00'))

        # Verify COMMISSION rows visible but not counted
        commission_rows = [t for t in result['transactions'] if t['is_commission']]
        self.assertEqual(len(commission_rows), 3, "Should have 3 COMMISSION rows")

        # Verify opening is counted once
        opening_rows = [t for t in result['transactions'] if 'opening' in t.get('description', '').lower()]
        # Opening balance should be visible in the initial state

        # Verify determinism (run again and get same result)
        result2 = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)
        self.assertEqual(result['license_running_balance'], result2['license_running_balance'])
        self.assertEqual(
            result['company_utilizations'][self.company_a.id]['utilization_balance'],
            result2['company_utilizations'][self.company_a.id]['utilization_balance']
        )


# ========== SION NORMS (presentation metadata, not a ledger fact) ==========

class CanonicalLedgerSionNormsTests(CanonicalLedgerServiceTestBase):
    """
    `transactions[].sion_norms` — the SION norms of the LICENCE ITEMS billed on
    a trade, resolved via line.sr_number -> .items -> .sion_norm_class.

    DFIA-only by construction: incentive trade lines reference an
    IncentiveLicense directly and carry no licence items, so there are no norms
    to resolve and the field must be empty rather than raising.
    """

    def _make_norm(self, code):
        head = HeadSIONNormsModel.objects.create(name=f'{code} Head')
        return SionNormClassModel.objects.create(head_norm=head, norm_class=code)

    def _make_item(self, name, norm=None, display_order=1):
        return ItemNameModel.objects.create(
            name=name, sion_norm_class=norm, display_order=display_order
        )

    def _billed_sr_number(self, trade):
        """The licence item (sr_number) billed by this trade's single line."""
        return trade.lines.first().sr_number

    def test_sion_norms_populated_for_dfia_license_with_norm_bearing_items(self):
        trade = self._create_purchase_trade(self.license, self.company_a, Decimal('1000.00'))
        sr_number = self._billed_sr_number(trade)
        e1 = self._make_norm('E1')
        e5 = self._make_norm('E5')
        sr_number.items.add(
            self._make_item('Item E1', e1, display_order=1),
            self._make_item('Item E5', e5, display_order=2),
            # Same norm again on a different item -> must be de-duplicated.
            self._make_item('Item E1 Duplicate', e1, display_order=3),
        )

        result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)
        txn = result['transactions'][0]

        # Exact legacy shape: comma-space joined, first-seen order, de-duplicated.
        self.assertEqual(txn['sion_norms'], 'E1, E5')
        # And it survives the frontend's split(', ') contract.
        self.assertEqual(str(txn['sion_norms']).split(', '), ['E1', 'E5'])

    def test_sion_norms_serializes_through_canonical_serializer(self):
        from apps.license.serializers import CanonicalLedgerSerializer

        trade = self._create_purchase_trade(self.license, self.company_a, Decimal('500.00'))
        norm = self._make_norm('E132')
        self._billed_sr_number(trade).items.add(self._make_item('Nuts', norm))

        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)
        data = CanonicalLedgerSerializer(dataset).data

        self.assertEqual(data['transactions'][0]['sion_norms'], 'E132')

    def test_sion_norms_empty_when_billed_items_have_no_norm(self):
        trade = self._create_purchase_trade(self.license, self.company_a, Decimal('750.00'))
        # Item with NO sion_norm_class at all.
        self._billed_sr_number(trade).items.add(self._make_item('Unclassified Item'))

        result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        self.assertEqual(result['transactions'][0]['sion_norms'], '')

    def test_sion_norms_empty_when_no_items_are_linked(self):
        self._create_purchase_trade(self.license, self.company_a, Decimal('300.00'))

        result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        self.assertEqual(result['transactions'][0]['sion_norms'], '')

    def test_sion_norms_empty_on_synthetic_opening_row(self):
        self._set_opening_balance(Decimal('2000.00'))

        result = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)
        opening = result['transactions'][0]

        self.assertEqual(opening['type'], 'OPENING')
        self.assertEqual(opening['sion_norms'], '')

    def test_sion_norms_empty_for_incentive_license_without_error(self):
        exporter = CompanyModel.objects.create(name='Incentive Exporter', iec='0000000099')
        port = PortModel.objects.create(code='INCP1', name='Incentive Port')
        incentive = IncentiveLicense.objects.create(
            license_type='RODTEP',
            license_number='RODTEP-SION-001',
            license_date=date(2026, 1, 1),
            license_expiry_date=date(2027, 12, 31),
            exporter=exporter,
            port_code=port,
            license_value=Decimal('5000.00'),
        )
        trade = LicenseTrade.objects.create(
            from_company=exporter,
            to_company=self.company_a,
            direction='PURCHASE',
            invoice_number='INV-INC-SION-1',
            invoice_date=date(2026, 1, 15),
            license_type='INCENTIVE',
        )
        IncentiveTradeLine.objects.create(
            trade=trade,
            incentive_license=incentive,
            license_value=Decimal('5000.00'),
            rate_pct=Decimal('50.000'),
            amount_inr=Decimal('2500.00'),
        )

        result = CanonicalLedgerService.build_canonical_ledger_dataset(
            incentive.id, license_type='RODTEP'
        )

        self.assertEqual(len(result['transactions']), 1)
        self.assertEqual(result['transactions'][0]['sion_norms'], '')
        # Metadata still resolves off the differently-named port FK.
        self.assertEqual(result['license_number'], 'RODTEP-SION-001')
        self.assertEqual(result['port_name'], 'Incentive Port')
        self.assertEqual(result['exporter_name'], 'Incentive Exporter')

    def test_sion_norms_resolution_is_not_n_plus_one(self):
        """Query count must not grow with the number of norm-bearing trades."""
        def build_with_trades(n):
            for _ in range(n):
                # Unique per call: HeadSIONNormsModel derives a natural-key uid
                # from `name`, so norm codes must not repeat across batches.
                tag = self._get_next_sr_number()
                trade = self._create_purchase_trade(
                    self.license, self.company_a, Decimal('100.00'), date(2026, 1, 10)
                )
                norm = self._make_norm(f'N{tag}')
                self._billed_sr_number(trade).items.add(self._make_item(f'Item {tag}', norm))
            with CaptureQueriesContext(connection) as ctx:
                CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)
            return len(ctx.captured_queries)

        queries_2 = build_with_trades(2)
        queries_6 = build_with_trades(4)  # 6 trades total

        self.assertEqual(
            queries_2, queries_6,
            f'sion_norms resolution scales with trade count: {queries_2} -> {queries_6} queries'
        )
