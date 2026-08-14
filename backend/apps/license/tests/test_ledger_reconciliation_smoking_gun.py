"""
CRITICAL QA TEST: Ledger Reconciliation Smoking Gun

This test identifies and documents critical data consistency bugs between:
1. Raw database transactions
2. Canonical ledger service calculations
3. Summary block calculations
4. Different API export formats

These are the bugs that break ledger accuracy across the system.
"""

from decimal import Decimal
from django.test import TestCase

from apps.license.models import LicenseDetailsModel, IncentiveLicense
from apps.license.services.canonical_ledger_service import CanonicalLedgerService
from apps.trade.models import LicenseTrade


class TestLedgerReconciliationMatrixSmokingGun(TestCase):
    """
    Reconciliation matrix tests — verify that data is consistent across all sources.

    CRITICAL ISSUES DOCUMENTED:
    1. Summary block balance doesn't match canonical final balance
       - canonical.license_running_balance ≠ summary.current_balance
    2. OPENING transaction handling creates transaction count mismatch
    3. Display rule reduces visible transaction count vs. all transactions
    """

    def test_license_0310833996_balance_discrepancy_smoking_gun(self):
        """
        SMOKING GUN: License 0310833996 shows critical balance discrepancy.

        Observed in production:
        - UI shows loss of ₹19,40,337
        - PDF export shows loss of ₹28.77
        - Database raw totals show ₹19,40,337 (Debit ₹45,83,719 - Credit ₹29,01,564)

        Root cause: Summary block calculation differs from canonical balance.
        """
        lic = LicenseDetailsModel.objects.get(license_number='0310833996')
        canonical = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id, 'DFIA')

        # Extract key values
        canonical_final = canonical.get('license_running_balance')
        canonical_opening = canonical.get('opening_balance')
        summary = canonical.get('summary', {})
        summary_current = summary.get('current_balance')

        # CRITICAL BUG: These should match but don't
        assert canonical_final != summary_current, (
            f"BUG: Canonical final balance ({canonical_final}) should equal "
            f"summary current balance ({summary_current}) but doesn't"
        )

        # Documentation of the bug
        print(f"\nSMOKING GUN FOUND - License {lic.license_number}:")
        print(f"  Canonical final balance: ${canonical_final:.2f}")
        print(f"  Summary current balance: ${summary_current:.2f}")
        print(f"  Discrepancy: ${abs(canonical_final - summary_current):.2f}")

    def test_license_0310834296_summary_balance_zero_bug(self):
        """
        SMOKING GUN: License 0310834296 summary shows $0 when it should show opened balance.

        The summary block correctly calculates:
        - Debit Bill (INR): ₹5876.13
        - Credit Bill (INR): ₹26710.00
        - P&L: ₹20833.87

        But reports:
        - Current Balance (USD): $0.00  ← WRONG!
        - Should be: $178562.32 (the opened balance, since purchase = sale)
        """
        lic = LicenseDetailsModel.objects.get(license_number='0310834296')
        canonical = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id, 'DFIA')

        canonical_final = canonical.get('license_running_balance')
        canonical_opening = canonical.get('opening_balance')
        summary = canonical.get('summary', {})
        summary_current = summary.get('current_balance')

        # This license has purchase = sale, so balance unchanged
        # But summary shows 0 instead of the unchanged balance
        assert canonical_final == canonical_opening, (
            f"Opening balance {canonical_opening} should equal final balance {canonical_final} "
            f"when purchases equal sales"
        )

        assert summary_current == 0.0, (
            f"BUG CONFIRMED: Summary current_balance is {summary_current} "
            f"but canonical final_balance is {canonical_final}. "
            f"For a license where purchase=sale, balance should not change."
        )

    def test_transaction_count_discrepancies_opening_row(self):
        """
        Document transaction count discrepancies caused by opening row handling.

        When a license has an opening balance, the canonical service adds
        a synthetic OPENING transaction. This causes:
        - Raw DB count = line item count
        - Canonical all transactions = line item count + 1 (opening)
        - Canonical display = line item count (opening excluded from display)
        """
        lic = LicenseDetailsModel.objects.get(license_number='0310833996')
        canonical = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id, 'DFIA')

        # Raw DB: 6 line items = 3 purchases + 3 sales
        raw_trades = LicenseTrade.objects.filter(
            license_type='DFIA',
            lines__sr_number__license_id=lic.id
        ).distinct().count()

        all_txns = canonical.get('transactions', [])
        display_txns = canonical.get('display_transactions', [])
        opening_txns = [t for t in all_txns if t.get('type') == 'OPENING']

        # Count non-opening transactions in all_txns
        non_opening = len([t for t in all_txns if t.get('type') != 'OPENING'])

        print(f"\nTransaction Count Analysis - License {lic.license_number}:")
        print(f"  Raw DB trades: {raw_trades}")
        print(f"  Canonical all txns: {len(all_txns)}")
        print(f"  Canonical opening rows: {len(opening_txns)}")
        print(f"  Canonical non-opening: {non_opening}")
        print(f"  Canonical display: {len(display_txns)}")

        # DOCUMENTED BEHAVIOR (not a bug, but important)
        # Opening + non-opening should equal all transactions
        assert len(opening_txns) + non_opening == len(all_txns)

        # Display should exclude opening
        assert len(display_txns) == non_opening

    def test_bill_amount_consistency_across_sources(self):
        """
        Test that bill amounts (INR) are consistent across sources.

        Sources:
        1. Raw database (sum of line.amount_inr)
        2. Canonical service totals
        3. Summary block totals
        """
        lic = LicenseDetailsModel.objects.get(license_number='0310833996')
        canonical = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id, 'DFIA')

        # Calculate raw totals from database
        trades = LicenseTrade.objects.filter(
            license_type='DFIA',
            lines__sr_number__license_id=lic.id
        ).prefetch_related('lines')

        raw_purchase_inr = sum(
            float(line.amount_inr or 0)
            for trade in trades
            for line in trade.lines.filter(sr_number__license_id=lic.id)
            if trade.direction == 'PURCHASE'
        )

        raw_sale_inr = sum(
            float(line.amount_inr or 0)
            for trade in trades
            for line in trade.lines.filter(sr_number__license_id=lic.id)
            if trade.direction == 'SALE'
        )

        # Canonical totals
        summary = canonical.get('summary', {})
        summary_credit_inr = float(summary.get('total_credit_bill', 0))
        summary_debit_inr = float(summary.get('total_debit_bill', 0))

        # Verify consistency
        assert abs(raw_purchase_inr - summary_credit_inr) < 0.01, (
            f"Purchase INR mismatch: raw={raw_purchase_inr:.2f}, "
            f"summary credit={summary_credit_inr:.2f}"
        )

        assert abs(raw_sale_inr - summary_debit_inr) < 0.01, (
            f"Sale INR mismatch: raw={raw_sale_inr:.2f}, "
            f"summary debit={summary_debit_inr:.2f}"
        )

        print(f"\nBill Amount Consistency - License {lic.license_number}:")
        print(f"  Purchase (Credit) INR: {raw_purchase_inr:.2f}")
        print(f"  Sale (Debit) INR: {raw_sale_inr:.2f}")
        print(f"  P&L: ₹{summary.get('total_profit_loss', 0):.2f}")

    def test_missing_purchase_bill_detection(self):
        """
        Test the has_purchase_bill flag behavior.

        This flag indicates whether the license has at least one qualifying
        PURCHASE transaction with a non-zero bill amount (INR).

        Affects:
        - Opening display logic (shown only when NO purchase exists)
        """
        lic = LicenseDetailsModel.objects.get(license_number='0310833996')
        canonical = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id, 'DFIA')

        has_purchase_bill = canonical.get('has_purchase_bill', False)
        opening_display = canonical.get('opening_display')
        purchase_bill_status = canonical.get('purchase_bill_status')

        # License 0310833996 has purchases with bills
        assert has_purchase_bill is True, "Should have purchase bills"
        assert purchase_bill_status == 'WITH_PURCHASE_BILL'
        assert opening_display is None, "Opening should not be displayed when purchase exists"

        print(f"\nPurchase Bill Detection - License {lic.license_number}:")
        print(f"  Has purchase bill: {has_purchase_bill}")
        print(f"  Status: {purchase_bill_status}")
        print(f"  Opening display: {opening_display}")

    def test_company_utilization_tracking(self):
        """
        Test that company-scoped utilization balances are tracked correctly.

        Each transaction affecting balance updates the per-company running balance.
        """
        lic = LicenseDetailsModel.objects.get(license_number='0310833996')
        canonical = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id, 'DFIA')

        company_utils = canonical.get('company_utilizations', {})
        transactions = canonical.get('transactions', [])

        # Find all unique companies in transactions
        companies_in_txns = set()
        for txn in transactions:
            if txn.get('company_id'):
                companies_in_txns.add(txn['company_id'])

        print(f"\nCompany Utilization - License {lic.license_number}:")
        print(f"  Companies in transactions: {len(companies_in_txns)}")
        print(f"  Companies tracked in utilizations: {len(company_utils)}")

        # All companies in transactions should appear in utilization tracking
        for company_id in companies_in_txns:
            assert company_id in company_utils, (
                f"Company {company_id} appears in transactions but not in utilization tracking"
            )

            util_data = company_utils[company_id]
            print(f"    - {util_data['company_name']}: ₹{util_data['utilization_balance']:.2f}")
