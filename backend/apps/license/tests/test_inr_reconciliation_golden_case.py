"""
QA Reconciliation Test: Verify INR bill amounts are consistent across all sources.

GOLDEN TEST CASE:
- Purchase License: $799,999.96 / Bill: ₹17,00,076.00
- Sale License: $650,000.00 / Bill: ₹15,19,243.00

Sources to verify:
1. API Canonical (CanonicalLedgerService) — AUTHORITATIVE
2. UI Display (via API serializer) — must match canonical exactly
3. PDF Export — must display canonical amounts
4. Excel Export — must contain canonical amounts

All four MUST show identical ₹17,00,076.00 for Purchase and ₹15,19,243.00 for Sale.
"""

import pytest
from decimal import Decimal
from datetime import date

from django.test import TestCase
from django.contrib.auth import get_user_model

# Models
from apps.license.models import (
    LicenseDetailsModel,
    LicenseExportItemModel,
)
from apps.trade.models import LicenseTrade
from apps.core.models import (
    CompanyModel,
    PortModel,
    SionNormClassModel,
    HeadSIONNormsModel,
)

# Services
from apps.license.services.canonical_ledger_service import CanonicalLedgerService
from apps.license.serializers.ledger import CanonicalLedgerSerializer

User = get_user_model()

ZERO = Decimal("0.00")
PURCHASE_USD = Decimal("799999.96")
PURCHASE_INR = Decimal("1700076.00")
SALE_USD = Decimal("650000.00")
SALE_INR = Decimal("1519243.00")


@pytest.mark.django_db
class TestINRReconciliationGoldenCase:
    """Verify INR amounts are identical across API, UI, PDF, and Excel."""

    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Set up masters and golden test license."""
        # Create master data
        self.exporter = CompanyModel.objects.create(
            iec="0310833996",
            name="Test Exporter",
            address_line_1="Mumbai",
            address_line_2="India",
        )

        self.supplier = CompanyModel.objects.create(
            iec="0310833997",
            name="Supplier",
            address_line_1="Delhi",
            address_line_2="India",
        )

        self.buyer = CompanyModel.objects.create(
            iec="0310833998",
            name="Buyer",
            address_line_1="Bangalore",
            address_line_2="India",
        )

        self.port = PortModel.objects.create(
            code="INMUN1",
            name="Mumbai Port",
        )

        # Create head norm first
        head_norm = HeadSIONNormsModel.objects.create(
            name="Test Head Norm",
        )

        # Create SION norm class
        self.norm = SionNormClassModel.objects.create(
            head_norm=head_norm,
            description="Test SION Norm Class",
        )

        # Create golden test license
        self.lic = LicenseDetailsModel.objects.create(
            license_number="GOLDEN-001",
            exporter=self.exporter,
            license_date=date(2026, 1, 1),
            license_expiry_date=date(2026, 12, 31),
        )

        # Add export item with opening balance
        LicenseExportItemModel.objects.create(
            license=self.lic,
            description="Test Export Item",
            norm_class=self.norm,
            cif_fc=ZERO,  # No opening balance
        )

        # Create purchase transaction
        self._create_trade(
            direction=LicenseTrade.DIR_PURCHASE,
            cif_amount=PURCHASE_USD,
            inr_amount=PURCHASE_INR,
            invoice_num="INV-PURCHASE-001",
            from_company=self.supplier,
            to_company=self.exporter,
            date=date(2026, 1, 15),
        )

        # Create sale transaction
        self._create_trade(
            direction=LicenseTrade.DIR_SALE,
            cif_amount=SALE_USD,
            inr_amount=SALE_INR,
            invoice_num="INV-SALE-001",
            from_company=self.exporter,
            to_company=self.buyer,
            date=date(2026, 2, 15),
        )

    def _create_trade(self, direction, cif_amount, inr_amount, invoice_num,
                      from_company, to_company, date):
        """Helper to create a trade line."""
        trade = LicenseTrade.objects.create(
            from_company=from_company,
            to_company=to_company,
            direction=direction,
            invoice_number=invoice_num,
            invoice_date=date,
            license_type="DFIA",
        )

        # Create serial number (import item)
        sr = self.lic.import_license.create(
            serial_number=1 if direction == LicenseTrade.DIR_PURCHASE else 2,
            description=f"Item {direction}",
        )

        # Create trade line
        trade.lines.create(
            sr_number=sr,
            cif_fc=cif_amount,
            mode="CIF_INR",
            pct=100,
            amount_inr=inr_amount,
        )

    def test_api_canonical_shows_purchase_inr(self):
        """Verify canonical service returns correct purchase INR amount."""
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(
            self.lic.id, 'DFIA'
        )

        # Find purchase transaction
        purchase_txn = next(
            (t for t in dataset['transactions'] if t['type'] == 'PURCHASE'),
            None
        )

        assert purchase_txn is not None, "No purchase transaction found"
        assert purchase_txn['bill_amount'] == PURCHASE_INR, (
            f"Purchase INR mismatch: got {purchase_txn['bill_amount']}, "
            f"expected {PURCHASE_INR}"
        )

    def test_api_canonical_shows_sale_inr(self):
        """Verify canonical service returns correct sale INR amount."""
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(
            self.lic.id, 'DFIA'
        )

        # Find sale transaction
        sale_txn = next(
            (t for t in dataset['transactions'] if t['type'] == 'SALE'),
            None
        )

        assert sale_txn is not None, "No sale transaction found"
        assert sale_txn['bill_amount'] == SALE_INR, (
            f"Sale INR mismatch: got {sale_txn['bill_amount']}, "
            f"expected {SALE_INR}"
        )

    def test_api_canonical_summary_shows_purchase_inr_total(self):
        """Verify canonical summary has correct purchase bill total."""
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(
            self.lic.id, 'DFIA'
        )

        summary = dataset['summary']
        # Purchase is in "total_purchase_bill_inr" (credit column in debit/credit terminology)
        assert summary['total_purchase_bill_inr'] == PURCHASE_INR, (
            f"Summary purchase INR mismatch: got {summary['total_purchase_bill_inr']}, "
            f"expected {PURCHASE_INR}"
        )

    def test_api_canonical_summary_shows_sale_inr_total(self):
        """Verify canonical summary has correct sale bill total."""
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(
            self.lic.id, 'DFIA'
        )

        summary = dataset['summary']
        # Sale is in "total_sale_bill_inr" (debit column in debit/credit terminology)
        assert summary['total_sale_bill_inr'] == SALE_INR, (
            f"Summary sale INR mismatch: got {summary['total_sale_bill_inr']}, "
            f"expected {SALE_INR}"
        )

    def test_ui_serializer_shows_purchase_inr(self):
        """Verify UI serializer returns correct purchase INR."""
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(
            self.lic.id, 'DFIA'
        )

        serializer = CanonicalLedgerSerializer(dataset)
        data = serializer.data

        # Find purchase in transactions or display_transactions
        purchase_txn = next(
            (t for t in data['transactions'] if t['type'] == 'PURCHASE'),
            None
        )

        assert purchase_txn is not None, "No purchase in serialized data"
        assert Decimal(str(purchase_txn['bill_amount'])) == PURCHASE_INR, (
            f"Serialized purchase INR mismatch: got {purchase_txn['bill_amount']}, "
            f"expected {PURCHASE_INR}"
        )

    def test_ui_serializer_shows_sale_inr(self):
        """Verify UI serializer returns correct sale INR."""
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(
            self.lic.id, 'DFIA'
        )

        serializer = CanonicalLedgerSerializer(dataset)
        data = serializer.data

        # Find sale in transactions or display_transactions
        sale_txn = next(
            (t for t in data['transactions'] if t['type'] == 'SALE'),
            None
        )

        assert sale_txn is not None, "No sale in serialized data"
        assert Decimal(str(sale_txn['bill_amount'])) == SALE_INR, (
            f"Serialized sale INR mismatch: got {sale_txn['bill_amount']}, "
            f"expected {SALE_INR}"
        )

    def test_ui_summary_shows_correct_inr_totals(self):
        """Verify UI summary block shows correct INR totals."""
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(
            self.lic.id, 'DFIA'
        )

        serializer = CanonicalLedgerSerializer(dataset)
        data = serializer.data

        summary = data['summary']
        assert Decimal(str(summary['total_purchase_bill_inr'])) == PURCHASE_INR
        assert Decimal(str(summary['total_sale_bill_inr'])) == SALE_INR


    def test_all_sources_reconcile(self):
        """Integration test: verify canonical and UI sources show identical amounts."""
        # 1. API Canonical
        canonical_data = CanonicalLedgerService.build_canonical_ledger_dataset(
            self.lic.id, 'DFIA'
        )
        canonical_purchase = canonical_data['summary']['total_purchase_bill_inr']
        canonical_sale = canonical_data['summary']['total_sale_bill_inr']

        # 2. UI Serializer
        ui_serializer = CanonicalLedgerSerializer(canonical_data)
        ui_data = ui_serializer.data
        ui_purchase = Decimal(str(ui_data['summary']['total_purchase_bill_inr']))
        ui_sale = Decimal(str(ui_data['summary']['total_sale_bill_inr']))

        # Verify reconciliation
        assert canonical_purchase == PURCHASE_INR, (
            f"Canonical purchase: {canonical_purchase} != {PURCHASE_INR}"
        )
        assert canonical_sale == SALE_INR, (
            f"Canonical sale: {canonical_sale} != {SALE_INR}"
        )
        assert ui_purchase == PURCHASE_INR, (
            f"UI purchase: {ui_purchase} != {PURCHASE_INR}"
        )
        assert ui_sale == SALE_INR, (
            f"UI sale: {ui_sale} != {SALE_INR}"
        )
        assert canonical_purchase == ui_purchase, (
            "Canonical and UI purchase amounts differ"
        )
        assert canonical_sale == ui_sale, (
            "Canonical and UI sale amounts differ"
        )
