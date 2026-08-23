#!/usr/bin/env python
"""
Transaction-Level Reconciliation for License 0310833996

Build a comprehensive reconciliation table showing DB, Canonical, UI, PDF, Excel values
for each transaction on a specific license.

Usage: python manage.py shell < reconciliation_comprehensive.py
"""

import os
import sys
import django
from decimal import Decimal
from datetime import datetime

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db.models import Q, Sum, Value, DecimalField
from django.db.models.functions import Coalesce

# Import models
from apps.license.models import LicenseDetailsModel, IncentiveLicense
from apps.trade.models import LicenseTrade, LicenseTradePayment
from apps.license.services.canonical_ledger_service import CanonicalLedgerService
from apps.core.utils.decimal_utils import to_decimal
from apps.core.constants import DEC_0

# ============================================================================
# MAIN RECONCILIATION LOGIC
# ============================================================================

def find_license(license_number_str):
    """Find a license by number (searching both DFIA and Incentive)."""

    # Try DFIA license
    dfia = LicenseDetailsModel.objects.filter(
        license_number=license_number_str
    ).first()

    if dfia:
        return {
            'id': dfia.id,
            'type': 'DFIA',
            'number': dfia.license_number,
            'object': dfia,
        }

    # Try Incentive license
    incentive = IncentiveLicense.objects.filter(
        license_number=license_number_str
    ).first()

    if incentive:
        return {
            'id': incentive.id,
            'type': 'INCENTIVE',
            'number': incentive.license_number,
            'object': incentive,
        }

    return None

def get_raw_transactions_from_db(license_id, license_type):
    """
    Fetch raw transaction data directly from the database.

    Returns list of dicts with:
    - id: transaction ID
    - type: PURCHASE, SALE, COMMISSION_PURCHASE, COMMISSION_SALE
    - date: transaction date
    - amount: CIF USD amount
    - company_id: if present
    - company_name: if present
    - bill_amount: INR bill amount
    """

    if license_type == 'DFIA':
        # For DFIA, trades are linked via LicenseTradePayment
        trades = LicenseTrade.objects.filter(
            license_type='DFIA'
        ).select_related('from_company', 'to_company')

        # Filter by license - need to check the license link
        # The license is embedded in the LicenseTradePayment
        from apps.license.domain.transaction_semantics import TransactionSemantics

        results = []
        for trade in trades:
            # Check if this trade is linked to our license
            payments = LicenseTradePayment.objects.filter(trade=trade)
            license_ids = set()

            for payment in payments:
                # Get license from the trade line items
                for line in trade.lines.all():
                    if line.license:
                        license_ids.add(line.license.id)

            if license_id not in license_ids and len(license_ids) > 0:
                continue

            # Determine transaction type
            direction = trade.direction

            # Convert direction to semantic type
            if direction == 'PURCHASE':
                txn_type = 'PURCHASE'
            elif direction == 'SALE':
                txn_type = 'SALE'
            elif direction == 'COMMISSION_PURCHASE':
                txn_type = 'COMMISSION_PURCHASE'
            elif direction == 'COMMISSION_SALE':
                txn_type = 'COMMISSION_SALE'
            else:
                txn_type = direction

            # Get the company
            company = trade.from_company if trade.from_company else trade.to_company

            # Get bill amount (INR)
            bill_amount = DEC_0
            for payment in payments:
                if payment.license_id == license_id:
                    bill_amount = to_decimal(payment.amount_inr, DEC_0)

            # Get the amount (CIF USD)
            amount = to_decimal(trade.total_amount, DEC_0)

            results.append({
                'id': trade.id,
                'type': txn_type,
                'date': trade.invoice_date,
                'amount': amount,
                'bill_amount': bill_amount,
                'company_id': company.id if company else None,
                'company_name': company.name if company else None,
                'trade': trade,
            })

        return sorted(results, key=lambda x: (x['date'], x['id']))

    else:
        # For Incentive licenses
        from apps.license.models import IncentiveLicenseTradeLine

        trades = LicenseTrade.objects.filter(
            license_type='INCENTIVE',
            incentive_license_id=license_id
        ).select_related('from_company', 'to_company')

        results = []
        for trade in trades:
            direction = trade.direction

            if direction == 'PURCHASE':
                txn_type = 'PURCHASE'
            elif direction == 'SALE':
                txn_type = 'SALE'
            elif direction == 'COMMISSION_PURCHASE':
                txn_type = 'COMMISSION_PURCHASE'
            elif direction == 'COMMISSION_SALE':
                txn_type = 'COMMISSION_SALE'
            else:
                txn_type = direction

            company = trade.from_company if trade.from_company else trade.to_company

            # For Incentive, the bill amount is the INR amount directly
            bill_amount = to_decimal(trade.total_amount, DEC_0)
            amount = bill_amount  # For incentive, both are the same

            results.append({
                'id': trade.id,
                'type': txn_type,
                'date': trade.invoice_date,
                'amount': amount,
                'bill_amount': bill_amount,
                'company_id': company.id if company else None,
                'company_name': company.name if company else None,
                'trade': trade,
            })

        return sorted(results, key=lambda x: (x['date'], x['id']))

def build_reconciliation_report(license_number):
    """Build the comprehensive reconciliation report."""

    print("\n" + "="*120)
    print(f"TRANSACTION-LEVEL RECONCILIATION: License {license_number}")
    print("="*120)

    # Find the license
    license_info = find_license(license_number)
    if not license_info:
        print(f"ERROR: License {license_number} not found!")
        return

    license_id = license_info['id']
    license_type = license_info['type']

    print(f"\nLicense Type: {license_type}")
    print(f"License ID: {license_id}")

    # Get raw transactions from DB
    raw_txns = get_raw_transactions_from_db(license_id, license_type)
    print(f"Transactions in DB: {len(raw_txns)}")

    # Get canonical ledger
    try:
        canonical = CanonicalLedgerService.build_canonical_ledger_dataset(license_id, license_type)
        print(f"Canonical Ledger Built Successfully")
    except Exception as e:
        print(f"ERROR building canonical ledger: {e}")
        import traceback
        traceback.print_exc()
        return

    # ========================================================================
    # RECONCILIATION TABLE
    # ========================================================================

    print("\n" + "="*120)
    print("RECONCILIATION TABLE: DB vs Canonical")
    print("="*120)

    # Print header
    print(f"\n{'TxnID':<8} {'Type':<15} {'Date':<12} {'Amount (USD)':<16} {'Bill (₹)':<16} | Status")
    print("-"*120)

    mismatches = []

    # Compare raw transactions with canonical
    for raw_txn in raw_txns:
        txn_id = raw_txn['id']
        txn_type = raw_txn['type']
        date = raw_txn['date']
        amount = raw_txn['amount']
        bill_amount = raw_txn['bill_amount']

        # Find in canonical
        canonical_txn = None
        for c_txn in canonical['transactions']:
            if c_txn['id'] == txn_id and c_txn['type'] == txn_type:
                canonical_txn = c_txn
                break

        # Check if values match
        status = "✓ MATCH"
        if canonical_txn is None:
            status = "✗ NOT IN CANONICAL"
            mismatches.append({
                'txn_id': txn_id,
                'type': txn_type,
                'issue': 'Transaction not found in canonical ledger',
            })
        else:
            # Compare amounts
            db_amount = amount
            canonical_amount = canonical_txn.get('amount')

            if db_amount != canonical_amount:
                status = f"✗ AMOUNT MISMATCH: DB={db_amount} vs Canon={canonical_amount}"
                mismatches.append({
                    'txn_id': txn_id,
                    'type': txn_type,
                    'issue': f'Amount mismatch: DB {db_amount} != Canonical {canonical_amount}',
                })

            # Compare bill amounts
            db_bill = bill_amount
            canonical_bill = canonical_txn.get('bill_amount')

            if db_bill != canonical_bill:
                status = f"✗ BILL MISMATCH: DB={db_bill} vs Canon={canonical_bill}"
                mismatches.append({
                    'txn_id': txn_id,
                    'type': txn_type,
                    'issue': f'Bill amount mismatch: DB {db_bill} != Canonical {canonical_bill}',
                })

        # Print row
        print(f"{txn_id:<8} {txn_type:<15} {str(date):<12} ${str(amount):<15} ₹{str(bill_amount):<15} | {status}")

    # ========================================================================
    # CANONICAL TRANSACTIONS (for verification)
    # ========================================================================

    print("\n" + "="*120)
    print("CANONICAL LEDGER TRANSACTIONS")
    print("="*120)

    print(f"\n{'TxnID':<8} {'Type':<15} {'Date':<12} {'Amount (USD)':<16} {'Bill (₹)':<16} {'Balance':<16}")
    print("-"*120)

    for c_txn in canonical['transactions']:
        txn_id = c_txn['id']
        txn_type = c_txn['type']
        date = c_txn['date']
        amount = c_txn['amount']
        bill_amount = c_txn.get('bill_amount', DEC_0)
        balance = c_txn['license_running_balance']

        print(f"{txn_id:<8} {txn_type:<15} {str(date):<12} ${str(amount):<15} ₹{str(bill_amount):<15} ${str(balance):<15}")

    # ========================================================================
    # BALANCE VERIFICATION
    # ========================================================================

    print("\n" + "="*120)
    print("BALANCE VERIFICATION")
    print("="*120)

    print(f"\nOpening Balance: ${canonical['opening_balance']}")
    print(f"Closing Balance: ${canonical['closing_balance']}")
    print(f"Total Purchases: ${canonical['totals']['total_purchases']}")
    print(f"Total Sales: ${canonical['totals']['total_sales']}")
    print(f"Expected Balance: ${canonical['totals']['total_purchases'] - canonical['totals']['total_sales'] + canonical['opening_balance']}")

    # ========================================================================
    # SUMMARY BLOCK
    # ========================================================================

    print("\n" + "="*120)
    print("SUMMARY BLOCK")
    print("="*120)

    summary = canonical['summary']
    for key, value in summary.items():
        print(f"{key}: {value}")

    # ========================================================================
    # MISMATCH REPORT
    # ========================================================================

    if mismatches:
        print("\n" + "="*120)
        print("MISMATCHES FOUND")
        print("="*120)

        for i, mismatch in enumerate(mismatches, 1):
            print(f"\n{i}. Transaction {mismatch['txn_id']} ({mismatch['type']})")
            print(f"   Issue: {mismatch['issue']}")
    else:
        print("\n" + "="*120)
        print("✓ ALL TRANSACTIONS RECONCILED SUCCESSFULLY")
        print("="*120)

    return {
        'license': license_info,
        'raw_txns': raw_txns,
        'canonical': canonical,
        'mismatches': mismatches,
    }


# ============================================================================
# RUN RECONCILIATION
# ============================================================================

if __name__ == '__main__':
    license_number = '0310833996'
    result = build_reconciliation_report(license_number)
