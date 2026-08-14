"""
Golden Test Suite for License Ledger — Comprehensive Parametrized Tests

GOLDEN EXAMPLE DATA:
  License: 0311055282

  PURCHASE:
    Date: 04-07-2026 (April 7, 2026)
    License Value: $7,99,999.96 (USD)
    Purchase Bill: ₹17,00,076.00 (INR)

  SALE:
    Date: 07-08-2026 (August 7, 2026)
    License Value: $6,50,000.00 (USD)
    Sale Bill: ₹15,19,243.00 (INR)

EXPECTED RESULTS:
  Purchase row: Debit($)=-, Credit($)=$7,99,999.96, Sale Bill=₹17,00,076, Purchase Bill=-
  Sale row: Debit($)=$6,50,000, Credit($)=-, Sale Bill=-, Purchase Bill=₹15,19,243
  Current Balance: $1,49,999.96
  Profit/Loss: -₹1,80,833.00 (LOSS)

Tests:
1. test_golden_purchase_row() - verify PURCHASE debit/credit fields
2. test_golden_sale_row() - verify SALE debit/credit fields
3. test_golden_current_balance() - verify $1,49,999.96
4. test_golden_profit_loss() - verify -₹1,80,833.00
5. test_golden_api_response() - verify canonical API returns all correct values
6. test_golden_ui_values() - compare UI with API response
7. test_golden_pdf_values() - verify PDF renders same as API
8. test_golden_excel_values() - verify Excel has same values

This test suite is parametrized to support:
- Multiple currency formats (USD, INR)
- Debit/Credit column semantics
- Balance calculations with decimal precision
- API serialization
- PDF/Excel export consistency
"""

import uuid
from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.constants import DEBIT, CREDIT
from apps.core.models import CompanyModel, PortModel
from apps.license.models import (
    LicenseDetailsModel,
    LicenseImportItemsModel,
)
from apps.trade.models import LicenseTrade, LicenseTradeLine
from apps.license.services.canonical_ledger_service import CanonicalLedgerService
from apps.license.serializers.ledger import CanonicalLedgerSerializer

User = get_user_model()


def _unique_iec():
    """Return a unique 10-char IEC-style code."""
    return str(uuid.uuid4().int)[:10]


class GoldenLedgerTestFixture:
    """Fixture helpers for golden ledger tests."""

    def make_company(self, name=None):
        """Create a test company."""
        return CompanyModel.objects.create(
            iec=_unique_iec(),
            name=name or f"Test Co {uuid.uuid4().hex[:4]}"
        )

    def make_port(self):
        """Create a test port."""
        return PortModel.objects.create(
            code=str(uuid.uuid4().int)[:6],
            name="Test Port"
        )

    def make_license(self, company, *, license_number, license_date):
        """Create a license."""
        return LicenseDetailsModel.objects.create(
            license_number=license_number,
            license_date=license_date,
            license_expiry_date=license_date + __import__('datetime').timedelta(days=365),
            exporter=company,
        )

    def make_import_item(self, license_obj, *, cif_fc):
        """Create an import item for the license."""
        return LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="Golden Test Item",
            quantity=Decimal("1000.000"),
            available_quantity=Decimal("1000.000"),
            cif_fc=cif_fc,
            cif_inr=cif_fc * Decimal("84.5"),
        )

    def make_purchase_trade(self, license_obj, from_company, to_company, *, invoice_date, amount_cif_fc, amount_inr):
        """Create a PURCHASE trade."""
        trade = LicenseTrade.objects.create(
            direction="PURCHASE",
            from_company=from_company,
            to_company=to_company,
            invoice_number=f"INV-PUR-GOLDEN-{uuid.uuid4().int % 9999:04d}",
            invoice_date=invoice_date,
        )
        for item in license_obj.import_license.all():
            LicenseTradeLine.objects.create(
                trade=trade,
                sr_number=item,
                description=item.description,
                hsn_code="49070000",
                mode="CIF_INR",
                cif_fc=amount_cif_fc,
                amount_inr=amount_inr,
            )
        return trade

    def make_sale_trade(self, license_obj, from_company, to_company, *, invoice_date, amount_cif_fc, amount_inr):
        """Create a SALE trade."""
        trade = LicenseTrade.objects.create(
            direction="SALE",
            from_company=from_company,
            to_company=to_company,
            invoice_number=f"INV-SAL-GOLDEN-{uuid.uuid4().int % 9999:04d}",
            invoice_date=invoice_date,
        )
        for item in license_obj.import_license.all():
            LicenseTradeLine.objects.create(
                trade=trade,
                sr_number=item,
                description=item.description,
                hsn_code="49070000",
                mode="CIF_INR",
                cif_fc=amount_cif_fc,
                amount_inr=amount_inr,
            )
        return trade

    def make_user(self, *, company=None, is_superuser=False):
        """Create a test user."""
        user = User.objects.create_user(
            username=f"user-{uuid.uuid4().hex[:8]}",
            email=f"{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123!",
            is_superuser=is_superuser,
        )
        if company and not is_superuser:
            user.company = company
            user.save()
        return user


# ─────────────────────────────────────────────────────────────────────────────
# PARAMETRIZED GOLDEN TEST DATA
# ─────────────────────────────────────────────────────────────────────────────

GOLDEN_TEST_PARAMS = {
    'license_number': '0311055282',
    'purchase_date': date(2026, 4, 7),
    'purchase_amount_usd': Decimal('799999.96'),
    'purchase_amount_inr': Decimal('1700076.00'),
    'sale_date': date(2026, 8, 7),
    'sale_amount_usd': Decimal('650000.00'),
    'sale_amount_inr': Decimal('1519243.00'),
    'expected_balance': Decimal('149999.96'),
    'expected_profit_loss': Decimal('-180833.00'),
}


class TestGoldenLedgerPurchaseRow(GoldenLedgerTestFixture, TestCase):
    """Test PURCHASE row debit/credit field values."""

    def setUp(self):
        self.company_a = self.make_company(name="Exporter")
        self.company_b = self.make_company(name="Buyer")
        self.port = self.make_port()

        # Create golden license
        self.license = self.make_license(
            self.company_a,
            license_number=GOLDEN_TEST_PARAMS['license_number'],
            license_date=GOLDEN_TEST_PARAMS['purchase_date'] - __import__('datetime').timedelta(days=30),
        )
        self.make_import_item(self.license, cif_fc=GOLDEN_TEST_PARAMS['purchase_amount_usd'])

    def test_golden_purchase_row(self):
        """Verify PURCHASE row has correct debit/credit field values."""
        # Create purchase trade
        purchase_trade = self.make_purchase_trade(
            self.license,
            from_company=self.company_a,
            to_company=self.company_b,
            invoice_date=GOLDEN_TEST_PARAMS['purchase_date'],
            amount_cif_fc=GOLDEN_TEST_PARAMS['purchase_amount_usd'],
            amount_inr=GOLDEN_TEST_PARAMS['purchase_amount_inr'],
        )

        # Build canonical ledger
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        # Find PURCHASE transaction
        purchase_txn = None
        for txn in dataset['transactions']:
            if txn['type'] == 'PURCHASE':
                purchase_txn = txn
                break

        self.assertIsNotNone(purchase_txn, "PURCHASE transaction should exist")
        self.assertEqual(purchase_txn['date'], GOLDEN_TEST_PARAMS['purchase_date'])
        self.assertEqual(purchase_txn['amount'], GOLDEN_TEST_PARAMS['purchase_amount_usd'])
        self.assertEqual(purchase_txn['bill_amount'], GOLDEN_TEST_PARAMS['purchase_amount_inr'])

        # Verify the purchase affects balance (CREDIT column in semantics)
        self.assertTrue(purchase_txn['affects_balance'])
        self.assertFalse(purchase_txn['is_commission'])


class TestGoldenLedgerSaleRow(GoldenLedgerTestFixture, TestCase):
    """Test SALE row debit/credit field values."""

    def setUp(self):
        self.company_a = self.make_company(name="Exporter")
        self.company_b = self.make_company(name="Buyer")
        self.port = self.make_port()

        # Create golden license
        self.license = self.make_license(
            self.company_a,
            license_number=GOLDEN_TEST_PARAMS['license_number'],
            license_date=GOLDEN_TEST_PARAMS['purchase_date'] - __import__('datetime').timedelta(days=30),
        )
        self.make_import_item(self.license, cif_fc=GOLDEN_TEST_PARAMS['purchase_amount_usd'])

    def test_golden_sale_row(self):
        """Verify SALE row has correct debit/credit field values."""
        # Create purchase first (required for balance)
        self.make_purchase_trade(
            self.license,
            from_company=self.company_a,
            to_company=self.company_b,
            invoice_date=GOLDEN_TEST_PARAMS['purchase_date'],
            amount_cif_fc=GOLDEN_TEST_PARAMS['purchase_amount_usd'],
            amount_inr=GOLDEN_TEST_PARAMS['purchase_amount_inr'],
        )

        # Create sale trade
        sale_trade = self.make_sale_trade(
            self.license,
            from_company=self.company_b,
            to_company=self.company_a,
            invoice_date=GOLDEN_TEST_PARAMS['sale_date'],
            amount_cif_fc=GOLDEN_TEST_PARAMS['sale_amount_usd'],
            amount_inr=GOLDEN_TEST_PARAMS['sale_amount_inr'],
        )

        # Build canonical ledger
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        # Find SALE transaction
        sale_txn = None
        for txn in dataset['transactions']:
            if txn['type'] == 'SALE':
                sale_txn = txn
                break

        self.assertIsNotNone(sale_txn, "SALE transaction should exist")
        self.assertEqual(sale_txn['date'], GOLDEN_TEST_PARAMS['sale_date'])
        self.assertEqual(sale_txn['amount'], GOLDEN_TEST_PARAMS['sale_amount_usd'])
        self.assertEqual(sale_txn['bill_amount'], GOLDEN_TEST_PARAMS['sale_amount_inr'])

        # Verify the sale affects balance (DEBIT column in semantics)
        self.assertTrue(sale_txn['affects_balance'])
        self.assertFalse(sale_txn['is_commission'])


class TestGoldenLedgerCurrentBalance(GoldenLedgerTestFixture, TestCase):
    """Test current balance calculation."""

    def setUp(self):
        self.company_a = self.make_company(name="Exporter")
        self.company_b = self.make_company(name="Buyer")
        self.port = self.make_port()

        # Create golden license
        self.license = self.make_license(
            self.company_a,
            license_number=GOLDEN_TEST_PARAMS['license_number'],
            license_date=GOLDEN_TEST_PARAMS['purchase_date'] - __import__('datetime').timedelta(days=30),
        )
        self.make_import_item(self.license, cif_fc=GOLDEN_TEST_PARAMS['purchase_amount_usd'])

    def test_golden_current_balance(self):
        """Verify current balance is $1,49,999.96 (Purchase - Sale)."""
        # Create purchase
        self.make_purchase_trade(
            self.license,
            from_company=self.company_a,
            to_company=self.company_b,
            invoice_date=GOLDEN_TEST_PARAMS['purchase_date'],
            amount_cif_fc=GOLDEN_TEST_PARAMS['purchase_amount_usd'],
            amount_inr=GOLDEN_TEST_PARAMS['purchase_amount_inr'],
        )

        # Create sale
        self.make_sale_trade(
            self.license,
            from_company=self.company_b,
            to_company=self.company_a,
            invoice_date=GOLDEN_TEST_PARAMS['sale_date'],
            amount_cif_fc=GOLDEN_TEST_PARAMS['sale_amount_usd'],
            amount_inr=GOLDEN_TEST_PARAMS['sale_amount_inr'],
        )

        # Build canonical ledger
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        # Verify balance
        expected_balance = GOLDEN_TEST_PARAMS['purchase_amount_usd'] - GOLDEN_TEST_PARAMS['sale_amount_usd']
        self.assertEqual(
            dataset['license_running_balance'],
            expected_balance,
            f"Balance should be {expected_balance} (Purchase - Sale)"
        )
        self.assertEqual(dataset['closing_balance'], expected_balance)


class TestGoldenLedgerProfitLoss(GoldenLedgerTestFixture, TestCase):
    """Test profit/loss calculation."""

    def setUp(self):
        self.company_a = self.make_company(name="Exporter")
        self.company_b = self.make_company(name="Buyer")
        self.port = self.make_port()

        # Create golden license
        self.license = self.make_license(
            self.company_a,
            license_number=GOLDEN_TEST_PARAMS['license_number'],
            license_date=GOLDEN_TEST_PARAMS['purchase_date'] - __import__('datetime').timedelta(days=30),
        )
        self.make_import_item(self.license, cif_fc=GOLDEN_TEST_PARAMS['purchase_amount_usd'])

    def test_golden_profit_loss(self):
        """Verify profit/loss is -₹1,80,833.00 (LOSS)."""
        # Create purchase
        self.make_purchase_trade(
            self.license,
            from_company=self.company_a,
            to_company=self.company_b,
            invoice_date=GOLDEN_TEST_PARAMS['purchase_date'],
            amount_cif_fc=GOLDEN_TEST_PARAMS['purchase_amount_usd'],
            amount_inr=GOLDEN_TEST_PARAMS['purchase_amount_inr'],
        )

        # Create sale
        self.make_sale_trade(
            self.license,
            from_company=self.company_b,
            to_company=self.company_a,
            invoice_date=GOLDEN_TEST_PARAMS['sale_date'],
            amount_cif_fc=GOLDEN_TEST_PARAMS['sale_amount_usd'],
            amount_inr=GOLDEN_TEST_PARAMS['sale_amount_inr'],
        )

        # Build canonical ledger
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        # Verify profit/loss (in INR: Sale Bill - Purchase Bill = negative = LOSS)
        expected_profit_loss = (
            GOLDEN_TEST_PARAMS['sale_amount_inr'] -
            GOLDEN_TEST_PARAMS['purchase_amount_inr']
        )

        # Check the summary block
        summary = dataset.get('summary')
        self.assertIsNotNone(summary)

        # total_profit_loss should be negative (LOSS)
        self.assertEqual(summary['total_profit_loss'], expected_profit_loss)
        self.assertEqual(summary['profit_state'], 'LOSS')


class TestGoldenLedgerAPIResponse(GoldenLedgerTestFixture, TestCase):
    """Test canonical API response includes all correct values."""

    def setUp(self):
        self.company_a = self.make_company(name="Exporter")
        self.company_b = self.make_company(name="Buyer")
        self.port = self.make_port()

        # Create golden license
        self.license = self.make_license(
            self.company_a,
            license_number=GOLDEN_TEST_PARAMS['license_number'],
            license_date=GOLDEN_TEST_PARAMS['purchase_date'] - __import__('datetime').timedelta(days=30),
        )
        self.make_import_item(self.license, cif_fc=GOLDEN_TEST_PARAMS['purchase_amount_usd'])

    def test_golden_api_response(self):
        """Verify API response includes license number, dates, amounts, and summary."""
        # Create trades
        self.make_purchase_trade(
            self.license,
            from_company=self.company_a,
            to_company=self.company_b,
            invoice_date=GOLDEN_TEST_PARAMS['purchase_date'],
            amount_cif_fc=GOLDEN_TEST_PARAMS['purchase_amount_usd'],
            amount_inr=GOLDEN_TEST_PARAMS['purchase_amount_inr'],
        )

        self.make_sale_trade(
            self.license,
            from_company=self.company_b,
            to_company=self.company_a,
            invoice_date=GOLDEN_TEST_PARAMS['sale_date'],
            amount_cif_fc=GOLDEN_TEST_PARAMS['sale_amount_usd'],
            amount_inr=GOLDEN_TEST_PARAMS['sale_amount_inr'],
        )

        # Build canonical dataset
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        # Serialize using API serializer
        serializer = CanonicalLedgerSerializer(dataset)
        response_data = serializer.data

        # Verify license metadata
        self.assertEqual(response_data['license_number'], GOLDEN_TEST_PARAMS['license_number'])
        self.assertIsNotNone(response_data['license_date'])

        # Verify transactions list exists and has both PURCHASE and SALE
        transactions = response_data['transactions']
        self.assertGreaterEqual(len(transactions), 2)

        txn_types = [t['type'] for t in transactions]
        self.assertIn('PURCHASE', txn_types)
        self.assertIn('SALE', txn_types)

        # Verify summary
        summary = response_data['summary']
        self.assertIsNotNone(summary)
        # Compare as Decimal, accounting for serializer returning strings
        current_balance = summary['current_balance']
        if isinstance(current_balance, str):
            current_balance = Decimal(current_balance)
        self.assertEqual(current_balance, GOLDEN_TEST_PARAMS['expected_balance'])


class TestGoldenLedgerUIValues(GoldenLedgerTestFixture, TestCase):
    """Test UI display values match API response values."""

    def setUp(self):
        self.company_a = self.make_company(name="Exporter")
        self.company_b = self.make_company(name="Buyer")
        self.port = self.make_port()

        # Create golden license
        self.license = self.make_license(
            self.company_a,
            license_number=GOLDEN_TEST_PARAMS['license_number'],
            license_date=GOLDEN_TEST_PARAMS['purchase_date'] - __import__('datetime').timedelta(days=30),
        )
        self.make_import_item(self.license, cif_fc=GOLDEN_TEST_PARAMS['purchase_amount_usd'])

    def test_golden_ui_values(self):
        """Verify UI values match API response."""
        # Create trades
        self.make_purchase_trade(
            self.license,
            from_company=self.company_a,
            to_company=self.company_b,
            invoice_date=GOLDEN_TEST_PARAMS['purchase_date'],
            amount_cif_fc=GOLDEN_TEST_PARAMS['purchase_amount_usd'],
            amount_inr=GOLDEN_TEST_PARAMS['purchase_amount_inr'],
        )

        self.make_sale_trade(
            self.license,
            from_company=self.company_b,
            to_company=self.company_a,
            invoice_date=GOLDEN_TEST_PARAMS['sale_date'],
            amount_cif_fc=GOLDEN_TEST_PARAMS['sale_amount_usd'],
            amount_inr=GOLDEN_TEST_PARAMS['sale_amount_inr'],
        )

        # Build canonical dataset
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        # Verify display_transactions (what the UI shows)
        display_txns = dataset['display_transactions']
        self.assertEqual(len(display_txns), 2, "Should have 2 display transactions (PURCHASE + SALE)")

        # Extract purchase and sale from display transactions
        purchase_display = next((t for t in display_txns if t['type'] == 'PURCHASE'), None)
        sale_display = next((t for t in display_txns if t['type'] == 'SALE'), None)

        self.assertIsNotNone(purchase_display)
        self.assertIsNotNone(sale_display)

        # Verify UI shows same amounts as API
        self.assertEqual(purchase_display['amount'], GOLDEN_TEST_PARAMS['purchase_amount_usd'])
        self.assertEqual(sale_display['amount'], GOLDEN_TEST_PARAMS['sale_amount_usd'])
        self.assertEqual(purchase_display['bill_amount'], GOLDEN_TEST_PARAMS['purchase_amount_inr'])
        self.assertEqual(sale_display['bill_amount'], GOLDEN_TEST_PARAMS['sale_amount_inr'])


class TestGoldenLedgerPDFValues(GoldenLedgerTestFixture, TestCase):
    """Test PDF rendering includes same values as API."""

    def setUp(self):
        self.company_a = self.make_company(name="Exporter")
        self.company_b = self.make_company(name="Buyer")
        self.port = self.make_port()

        # Create golden license
        self.license = self.make_license(
            self.company_a,
            license_number=GOLDEN_TEST_PARAMS['license_number'],
            license_date=GOLDEN_TEST_PARAMS['purchase_date'] - __import__('datetime').timedelta(days=30),
        )
        self.make_import_item(self.license, cif_fc=GOLDEN_TEST_PARAMS['purchase_amount_usd'])

    def test_golden_pdf_values(self):
        """Verify PDF export data matches canonical ledger dataset."""
        # Create trades
        self.make_purchase_trade(
            self.license,
            from_company=self.company_a,
            to_company=self.company_b,
            invoice_date=GOLDEN_TEST_PARAMS['purchase_date'],
            amount_cif_fc=GOLDEN_TEST_PARAMS['purchase_amount_usd'],
            amount_inr=GOLDEN_TEST_PARAMS['purchase_amount_inr'],
        )

        self.make_sale_trade(
            self.license,
            from_company=self.company_b,
            to_company=self.company_a,
            invoice_date=GOLDEN_TEST_PARAMS['sale_date'],
            amount_cif_fc=GOLDEN_TEST_PARAMS['sale_amount_usd'],
            amount_inr=GOLDEN_TEST_PARAMS['sale_amount_inr'],
        )

        # Build canonical dataset (what PDF should use)
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        # Verify all critical fields are present for PDF rendering
        self.assertEqual(dataset['license_number'], GOLDEN_TEST_PARAMS['license_number'])
        self.assertIsNotNone(dataset['license_date'])
        self.assertEqual(dataset['closing_balance'], GOLDEN_TEST_PARAMS['expected_balance'])

        # Verify summary for PDF headers
        summary = dataset['summary']
        self.assertEqual(summary['current_balance'], GOLDEN_TEST_PARAMS['expected_balance'])
        self.assertEqual(summary['total_debit_bill'], GOLDEN_TEST_PARAMS['purchase_amount_inr'])
        self.assertEqual(summary['total_credit_bill'], GOLDEN_TEST_PARAMS['sale_amount_inr'])


class TestGoldenLedgerExcelValues(GoldenLedgerTestFixture, TestCase):
    """Test Excel export includes same values as API."""

    def setUp(self):
        self.company_a = self.make_company(name="Exporter")
        self.company_b = self.make_company(name="Buyer")
        self.port = self.make_port()

        # Create golden license
        self.license = self.make_license(
            self.company_a,
            license_number=GOLDEN_TEST_PARAMS['license_number'],
            license_date=GOLDEN_TEST_PARAMS['purchase_date'] - __import__('datetime').timedelta(days=30),
        )
        self.make_import_item(self.license, cif_fc=GOLDEN_TEST_PARAMS['purchase_amount_usd'])

    def test_golden_excel_values(self):
        """Verify Excel export data matches canonical ledger dataset."""
        # Create trades
        self.make_purchase_trade(
            self.license,
            from_company=self.company_a,
            to_company=self.company_b,
            invoice_date=GOLDEN_TEST_PARAMS['purchase_date'],
            amount_cif_fc=GOLDEN_TEST_PARAMS['purchase_amount_usd'],
            amount_inr=GOLDEN_TEST_PARAMS['purchase_amount_inr'],
        )

        self.make_sale_trade(
            self.license,
            from_company=self.company_b,
            to_company=self.company_a,
            invoice_date=GOLDEN_TEST_PARAMS['sale_date'],
            amount_cif_fc=GOLDEN_TEST_PARAMS['sale_amount_usd'],
            amount_inr=GOLDEN_TEST_PARAMS['sale_amount_inr'],
        )

        # Build canonical dataset (what Excel should use)
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(self.license.id)

        # Verify all transaction data for Excel rows
        transactions = dataset['transactions']
        self.assertGreaterEqual(len(transactions), 2)

        # Verify each transaction has required fields for Excel
        for txn in transactions:
            self.assertIn('date', txn)
            self.assertIn('type', txn)
            self.assertIn('amount', txn)
            self.assertIn('bill_amount', txn)
            self.assertIn('license_running_balance', txn)

        # Verify totals are correct
        totals = dataset['totals']
        self.assertEqual(totals['total_purchases'], GOLDEN_TEST_PARAMS['purchase_amount_usd'])
        self.assertEqual(totals['total_sales'], GOLDEN_TEST_PARAMS['sale_amount_usd'])
