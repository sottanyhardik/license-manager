"""
Characterization tests for the D2 balance-semantics discrepancy.

These tests PIN CURRENT BEHAVIOUR. They do not assert that the current
values are the approved business meaning. Each pinned value is annotated
with the formula that produced it, so that a deliberate change to D2 must
update both the formula and the expected value in the same change.

Fixture (synthetic, same shape as `TestHiddenBoeExclusion`'s repro case):
    Export CIF                         100,000.00
    Hidden (previous-owner) BOE debit   30,000.00   (BOE invoice_no = OTH + audit trail)
    Visible BOE debit                    5,000.00
    Outstanding (BOE-unlinked) allot.    2,000.00
    Purchase (CIF)                      20,000.00
    Sale (CIF)                          15,000.00

Formulas exercised:
    calculate_balance()          Credit - (non-hidden BOE + Allotment)           = 93,000.00
    calculate_customs_balance()  Credit - (all BOE incl. hidden + Allotment)     = 63,000.00
    calculate_financial_balance() Opening + Purchase - Sale - Our BOE - Allot.   = 48,000.00

The Customs Ledger (`build_customs_ledger`) folds hidden rows in
unconditionally, so its final computed balance must equal
`calculate_customs_balance()` (63,000.00). The snapshot's `customs_balance`
field is fed by `calculate_balance()`, so it reports 93,000.00. That gap is
the discrepancy under review.
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.bill_of_entry.models import OTH_INVOICE_MARKER, BillOfEntryModel, RowDetails
from apps.core.constants import DEBIT
from apps.core.models import CompanyModel
from apps.license.models import LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel
from apps.license.services.balance_calculator import LicenseBalanceCalculator
from apps.license.services.balance_snapshot import get_snapshot
from apps.license.services.license_balance_ledger_builder import LicenseBalanceLedgerBuilder
from apps.trade.models import LicenseTrade, LicenseTradeLine


class TestD2BalanceSemanticsCharacterization(TestCase):
    """Pins the three balance formulas and the snapshot field mapping."""

    def setUp(self):
        self.today = datetime.now().date()
        self.company = CompanyModel.objects.create(
            iec=str(uuid.uuid4().int)[:10],
            name="D2 Characterization Exporter",
        )
        self.license = LicenseDetailsModel.objects.create(
            license_number="04" + str(uuid.uuid4().int)[:8],
            license_date=self.today,
            license_expiry_date=self.today + timedelta(days=365),
            exporter=self.company,
        )
        self.item = LicenseImportItemsModel.objects.create(
            license=self.license,
            serial_number=1,
            description="D2 Characterization Item",
            quantity=Decimal("1000.000"),
            available_quantity=Decimal("1000.000"),
        )
        LicenseExportItemModel.objects.create(license=self.license, cif_fc=Decimal("100000.00"))
        self._build_fixture()

    def _make_boe(self, invoice_no=""):
        boe = BillOfEntryModel.objects.create(
            company=self.company,
            bill_of_entry_number=str(uuid.uuid4().int)[:9],
            bill_of_entry_date=self.today,
            exchange_rate=Decimal("84.50"),
            invoice_no=invoice_no,
        )
        if invoice_no == OTH_INVOICE_MARKER:
            # A hidden BOE needs its audit trail, otherwise `OTH` is treated
            # as unrelated legacy free text (see TestHiddenBoeExclusion).
            from apps.reconciliation.models import ReconciliationLog

            ReconciliationLog.objects.create(
                action=ReconciliationLog.ACTION_HIDE_BOE,
                bill_of_entry=boe,
                before={"is_hidden": False, "invoice_no": ""},
                after={"is_hidden": True, "bill_of_entry_number": boe.bill_of_entry_number},
            )
        return boe

    def _build_fixture(self):
        hidden_boe = self._make_boe(invoice_no=OTH_INVOICE_MARKER)
        RowDetails.objects.create(
            bill_of_entry=hidden_boe, sr_number=self.item, transaction_type=DEBIT,
            cif_fc=Decimal("30000.00"), cif_inr=Decimal("30000.00") * Decimal("84.5"),
            qty=Decimal("300.000"),
        )

        visible_boe = self._make_boe()
        RowDetails.objects.create(
            bill_of_entry=visible_boe, sr_number=self.item, transaction_type=DEBIT,
            cif_fc=Decimal("5000.00"), cif_inr=Decimal("5000.00") * Decimal("84.5"),
            qty=Decimal("50.000"),
        )

        allotment = AllotmentModel.objects.create(
            company=self.company, item_name="D2 Allotment", estimated_arrival_date=self.today,
        )
        AllotmentItems.objects.create(
            item=self.item, allotment=allotment, cif_fc=Decimal("2000.00"),
            cif_inr=Decimal("2000.00") * Decimal("84.5"), qty=Decimal("20.000"),
        )

        purchase = LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_PURCHASE, to_company=self.company,
            invoice_number="D2-PUR", invoice_date=self.today,
        )
        LicenseTradeLine.objects.create(
            trade=purchase, sr_number=self.item, description=self.item.description,
            mode=LicenseTradeLine.MODE_CIF_INR,
            cif_fc=Decimal("20000.00"), cif_inr=Decimal("20000.00") * Decimal("84.5"),
        )

        sale = LicenseTrade.objects.create(
            direction=LicenseTrade.DIR_SALE, from_company=self.company,
            invoice_number="D2-SALE", invoice_date=self.today,
        )
        LicenseTradeLine.objects.create(
            trade=sale, sr_number=self.item, description=self.item.description,
            mode=LicenseTradeLine.MODE_CIF_INR,
            cif_fc=Decimal("15000.00"), cif_inr=Decimal("15000.00") * Decimal("84.5"),
        )

    def test_formula_calculate_balance_excludes_hidden_boe(self):
        # PINNED (D2): Credit - (non-hidden BOE + Allotment)
        self.assertEqual(LicenseBalanceCalculator.calculate_balance(self.license), Decimal("93000.00"))

    def test_formula_calculate_customs_balance_includes_hidden_boe(self):
        # PINNED (D2): Credit - (all BOE incl. hidden + Allotment)
        self.assertEqual(LicenseBalanceCalculator.calculate_customs_balance(self.license), Decimal("63000.00"))

    def test_formula_calculate_financial_balance(self):
        # PINNED (D2): Opening + Purchase - Sale - Our BOE - Outstanding Allotment
        self.assertEqual(LicenseBalanceCalculator.calculate_financial_balance(self.license), Decimal("48000.00"))

    def test_customs_ledger_final_balance_matches_customs_formula(self):
        _rows, summary = LicenseBalanceLedgerBuilder.build_customs_ledger(self.license)
        self.assertEqual(summary["computed_balance"], Decimal("63000.00"))
        self.assertEqual(summary["computed_balance"], LicenseBalanceCalculator.calculate_customs_balance(self.license))

    def test_snapshot_financial_fields_agree_with_financial_engine(self):
        snapshot = get_snapshot(self.license.id)
        self.assertEqual(snapshot["balance_cif"], Decimal("48000.00"))
        self.assertEqual(snapshot["financial_balance"], Decimal("48000.00"))
        self.assertEqual(snapshot["financial_available_balance"], Decimal("48000.00"))

    def test_snapshot_customs_balance_diverges_from_customs_ledger(self):
        """KNOWN DISCREPANCY (D2). The snapshot's `customs_balance` pins the
        non-hidden formula (93,000.00). The Customs Ledger's own final figure
        and `calculate_customs_balance` both give 63,000.00. This test records
        the divergence; it does not endorse either figure. Resolve through D2
        before changing either side."""
        snapshot = get_snapshot(self.license.id)
        _rows, summary = LicenseBalanceLedgerBuilder.build_customs_ledger(self.license)

        self.assertEqual(snapshot["customs_balance"], Decimal("93000.00"))
        self.assertEqual(summary["computed_balance"], Decimal("63000.00"))
        self.assertNotEqual(snapshot["customs_balance"], summary["computed_balance"])
        # The derived difference inherits the same divergence.
        self.assertEqual(snapshot["balance_difference"], Decimal("-45000.00"))
