#!/usr/bin/env python
"""
Accounting Validation Script for License 0310833996

Validates:
1. Debit/credit mapping
2. Current balance calculation
3. Profit/loss calculation
4. Canonical service correctness
"""

import os
import sys
import django
from decimal import Decimal
from pathlib import Path

# Setup Django
os.chdir('/Users/drushahardiksottany/Developer/projects/license-manager/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')
sys.path.insert(0, '/Users/drushahardiksottany/Developer/projects/license-manager/backend')
django.setup()

from apps.license.services.canonical_ledger_service import CanonicalLedgerService
from apps.license.models import LicenseDetailsModel
from apps.license.domain.transaction_semantics import TransactionSemantics

def validate_license(license_number):
    """Validate accounting for a specific license."""

    print(f"\n{'='*80}")
    print(f"ACCOUNTING VALIDATION: License {license_number}")
    print(f"{'='*80}\n")

    # Find the license
    try:
        license_obj = LicenseDetailsModel.objects.get(license_number=license_number)
    except LicenseDetailsModel.DoesNotExist:
        print(f"ERROR: License {license_number} not found")
        return

    print(f"License ID: {license_obj.id}")
    print(f"Opening Balance: {license_obj.opening_balance}")
    print(f"Expiry Date: {license_obj.license_expiry_date}\n")

    # Get the canonical ledger dataset
    try:
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(license_obj.id, 'DFIA')
    except Exception as e:
        print(f"ERROR building canonical dataset: {e}")
        import traceback
        traceback.print_exc()
        return

    # =========================================================================
    # PART 1: VERIFY TRANSACTION SEMANTICS
    # =========================================================================
    print(f"\n{'='*80}")
    print("PART 1: VERIFY TRANSACTION SEMANTICS")
    print(f"{'='*80}\n")

    print("Transaction Semantics (from authoritative domain definition):")
    print("-" * 80)
    for txn_type in ['OPENING', 'PURCHASE', 'SALE', 'COMMISSION']:
        semantics = TransactionSemantics.get_semantics(txn_type)
        direction = semantics.get('balance_direction')
        affects = semantics.get('is_balance_affecting')
        print(f"{txn_type:20} | Direction: {direction:8} | Affects Balance: {str(affects):5}")

    # =========================================================================
    # PART 2: ANALYZE TRANSACTIONS
    # =========================================================================
    print(f"\n{'='*80}")
    print("PART 2: TRANSACTION ANALYSIS")
    print(f"{'='*80}\n")

    transactions = dataset['transactions']
    print(f"Total transactions: {len(transactions)}")

    # Categorize transactions
    by_type = {}
    for txn in transactions:
        txn_type = txn['type']
        if txn_type not in by_type:
            by_type[txn_type] = []
        by_type[txn_type].append(txn)

    print("\nTransaction counts by type:")
    for txn_type in sorted(by_type.keys()):
        print(f"  {txn_type:20}: {len(by_type[txn_type]):3} transactions")

    # =========================================================================
    # PART 3: VALIDATE BALANCE CALCULATION
    # =========================================================================
    print(f"\n{'='*80}")
    print("PART 3: VALIDATE BALANCE CALCULATION")
    print(f"{'='*80}\n")

    # Manually calculate the running balance
    print("Manual running balance calculation:")
    print("-" * 80)

    running_balance = Decimal('0.00')
    if dataset['opening_balance'] > 0:
        running_balance = dataset['opening_balance']
        print(f"Opening Balance:        {running_balance:>15.2f}")

    total_purchases = Decimal('0.00')
    total_sales = Decimal('0.00')

    for txn in transactions:
        if txn['type'] == 'OPENING':
            continue

        txn_type = txn['type']
        amount = txn['amount']
        direction = TransactionSemantics.get_balance_direction(txn_type)
        affects = TransactionSemantics.is_balance_affecting(txn_type)

        if affects:
            if direction == 'CREDIT':
                running_balance += amount
                if txn_type == 'PURCHASE':
                    total_purchases += amount
                label = f"+ {txn_type}"
            elif direction == 'DEBIT':
                running_balance -= amount  # DEBIT means remove, so subtract
                if txn_type == 'SALE':
                    total_sales += amount
                label = f"- {txn_type}"
            else:
                label = f"  {txn_type} (no impact)"
        else:
            label = f"  {txn_type} (excluded)"

        print(f"{label:25} {amount:>15.2f}  → Balance: {running_balance:>15.2f}")

    canonical_balance = dataset['license_running_balance']
    print(f"\n{'Canonical Balance':25} {'':>15}  → Balance: {canonical_balance:>15.2f}")

    # Verify they match
    if running_balance == canonical_balance:
        print(f"\n✓ BALANCE MATCH: Manual calculation = Canonical = {canonical_balance}")
    else:
        print(f"\n✗ BALANCE MISMATCH:")
        print(f"  Manual:    {running_balance}")
        print(f"  Canonical: {canonical_balance}")
        print(f"  Difference: {abs(running_balance - canonical_balance)}")

    # =========================================================================
    # PART 4: VALIDATE PROFIT/LOSS CALCULATION
    # =========================================================================
    print(f"\n{'='*80}")
    print("PART 4: VALIDATE PROFIT/LOSS CALCULATION")
    print(f"{'='*80}\n")

    summary = dataset.get('summary', {})

    print("Summary Block (from canonical service):")
    print("-" * 80)
    print(f"Total Debit (USD):        {summary.get('total_debit', 'N/A'):>15}")
    print(f"Total Credit (USD):       {summary.get('total_credit', 'N/A'):>15}")
    print(f"Total Debit Bill (INR):   {summary.get('total_debit_bill', 'N/A'):>15}")
    print(f"Total Credit Bill (INR):  {summary.get('total_credit_bill', 'N/A'):>15}")
    print(f"Current Balance:          {summary.get('current_balance', 'N/A'):>15}")
    print(f"Total Profit/Loss (INR):  {summary.get('total_profit_loss', 'N/A'):>15}")
    print(f"Profit State:             {summary.get('profit_state', 'N/A'):>15}")

    # =========================================================================
    # PART 5: VERIFY BILL AMOUNT MAPPING
    # =========================================================================
    print(f"\n{'='*80}")
    print("PART 5: VERIFY BILL AMOUNT MAPPING")
    print(f"{'='*80}\n")

    print("Checking bill amount accumulation:")
    print("-" * 80)

    manual_debit_bill = Decimal('0.00')
    manual_credit_bill = Decimal('0.00')

    for txn in transactions:
        if txn['type'] == 'OPENING':
            continue

        txn_type = txn['type']
        bill_amount = txn.get('bill_amount') or Decimal('0.00')

        if TransactionSemantics.is_balance_affecting(txn_type):
            direction = TransactionSemantics.get_balance_direction(txn_type)
            # In _build_summary, CREDIT direction → debit_bill, DEBIT direction → credit_bill
            if direction == 'CREDIT':
                manual_debit_bill += bill_amount
                print(f"{txn_type:15} ({bill_amount:>10.2f} INR) → Debit Bill")
            elif direction == 'DEBIT':
                manual_credit_bill += bill_amount
                print(f"{txn_type:15} ({bill_amount:>10.2f} INR) → Credit Bill")

    print(f"\nManual debit_bill:   {manual_debit_bill:>15.2f}")
    print(f"Canonical debit_bill: {summary.get('total_debit_bill', 'N/A'):>15}")

    print(f"\nManual credit_bill:   {manual_credit_bill:>15.2f}")
    print(f"Canonical credit_bill: {summary.get('total_credit_bill', 'N/A'):>15}")

    manual_profit_loss = manual_credit_bill - manual_debit_bill
    canonical_profit_loss = summary.get('total_profit_loss')

    print(f"\nManual P&L (credit_bill - debit_bill): {manual_profit_loss:>15.2f}")
    print(f"Canonical P&L:                         {canonical_profit_loss:>15}")

    if manual_profit_loss == canonical_profit_loss:
        print(f"\n✓ PROFIT/LOSS MATCH: Manual = Canonical = {canonical_profit_loss}")
    else:
        print(f"\n✗ PROFIT/LOSS MISMATCH:")
        print(f"  Manual:    {manual_profit_loss}")
        print(f"  Canonical: {canonical_profit_loss}")

    # =========================================================================
    # PART 6: TRANSACTION DISPLAY RULE VALIDATION
    # =========================================================================
    print(f"\n{'='*80}")
    print("PART 6: TRANSACTION DISPLAY RULE VALIDATION")
    print(f"{'='*80}\n")

    display_txns = dataset.get('display_transactions', [])
    opening_display = dataset.get('opening_display')

    print(f"Display transactions (PURCHASE + SALE): {len(display_txns)}")
    print(f"Opening display row present: {opening_display is not None}")

    if opening_display:
        print(f"\nOpening row displayed (license has no PURCHASE or only OPENING)")
        print(f"  Date: {opening_display.get('date')}")
        print(f"  Amount: {opening_display.get('amount')}")

    # =========================================================================
    # PART 7: IDENTITY VERIFICATION
    # =========================================================================
    print(f"\n{'='*80}")
    print("PART 7: IDENTITY VERIFICATION")
    print(f"{'='*80}\n")

    print("The accounting identity must hold:")
    print("  current_balance = total_credit − total_debit")
    print("  total_profit_loss = total_credit_bill − total_debit_bill")
    print()

    current_balance = summary.get('current_balance')
    total_credit = summary.get('total_credit')
    total_debit = summary.get('total_debit')

    calculated_balance = total_credit - total_debit

    print(f"Current Balance:           {current_balance:>15.2f}")
    print(f"Total Credit - Debit:      {calculated_balance:>15.2f}")

    if current_balance == calculated_balance:
        print(f"\n✓ IDENTITY HOLDS")
    else:
        print(f"\n✗ IDENTITY BROKEN")
        print(f"  Difference: {abs(current_balance - calculated_balance)}")

    # =========================================================================
    # FINAL SUMMARY
    # =========================================================================
    print(f"\n{'='*80}")
    print("FINAL ACCOUNTING SUMMARY")
    print(f"{'='*80}\n")

    print(f"License:                  {license_number}")
    print(f"Current Balance (USD):     {dataset['license_running_balance']:>15.2f}")
    print(f"Profit/Loss (INR):        {summary.get('total_profit_loss', 'N/A'):>15}")
    print(f"Profit State:             {summary.get('profit_state', 'N/A'):>15}")
    print()

if __name__ == '__main__':
    validate_license('0310833996')
