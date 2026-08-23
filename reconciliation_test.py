#!/usr/bin/env python
"""
CRITICAL QA RECONCILIATION TEST

Extracts ledger data from all sources for licenses 0310833996 and 2616,
then builds a comprehensive reconciliation matrix showing discrepancies.
"""

import os
import sys
import django
from decimal import Decimal
import json
from datetime import datetime

# Setup Django
backend_path = '/Users/drushahardiksottany/Developer/projects/license-manager/backend'
sys.path.insert(0, backend_path)
os.chdir(backend_path)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')

django.setup()

from apps.license.models import LicenseDetailsModel, IncentiveLicense
from apps.license.services.canonical_ledger_service import CanonicalLedgerService
from apps.trade.models import LicenseTrade, LicenseTradeLine, IncentiveTradeLine
from django.db.models import Q


def get_raw_transactions(license_id, license_type):
    """Get raw transactions directly from database."""
    transactions = []

    if license_type == 'DFIA':
        trades = LicenseTrade.objects.filter(
            license_type='DFIA',
            lines__sr_number__license_id=license_id
        ).prefetch_related('lines', 'from_company', 'to_company').distinct()

        for trade in trades:
            for line in trade.lines.filter(sr_number__license_id=license_id):
                transactions.append({
                    'id': trade.id,
                    'date': trade.invoice_date,
                    'type': trade.direction,
                    'from_company': trade.from_company.name if trade.from_company else None,
                    'to_company': trade.to_company.name if trade.to_company else None,
                    'amount_inr': float(line.amount_inr or 0),
                    'cif_fc': float(line.cif_fc or 0),
                    'cif_inr': float(line.cif_inr or 0),
                })
    else:
        trades = LicenseTrade.objects.filter(
            license_type='INCENTIVE',
            incentive_lines__incentive_license_id=license_id
        ).prefetch_related('incentive_lines', 'from_company', 'to_company').distinct()

        for trade in trades:
            for line in trade.incentive_lines.filter(incentive_license_id=license_id):
                transactions.append({
                    'id': trade.id,
                    'date': trade.invoice_date,
                    'type': trade.direction,
                    'from_company': trade.from_company.name if trade.from_company else None,
                    'to_company': trade.to_company.name if trade.to_company else None,
                    'amount_inr': float(line.amount_inr or 0),
                    'license_value': float(line.license_value or 0),
                })

    return sorted(transactions, key=lambda x: (x['date'] or datetime.min.date(), x['id']))


def get_canonical_ledger(license_id, license_type):
    """Get canonical ledger from service."""
    try:
        return CanonicalLedgerService.build_canonical_ledger_dataset(license_id, license_type)
    except Exception as e:
        return {'error': str(e)}


def find_license(license_number):
    """Find license by number in either DFIA or Incentive."""
    # Try DFIA first
    try:
        lic = LicenseDetailsModel.objects.get(license_number=license_number)
        return ('DFIA', lic)
    except LicenseDetailsModel.DoesNotExist:
        pass

    # Try Incentive
    try:
        lic = IncentiveLicense.objects.get(license_number=license_number)
        return ('INCENTIVE', lic)
    except IncentiveLicense.DoesNotExist:
        pass

    return (None, None)


def build_reconciliation_for_license(license_number):
    """Build complete reconciliation matrix for a license."""
    lic_type, lic = find_license(license_number)
    if not lic:
        return {'error': f'License {license_number} not found'}

    license_id = lic.id

    print(f"\n{'='*100}")
    print(f"RECONCILIATION FOR LICENSE: {license_number} (Type: {lic_type})")
    print(f"{'='*100}")

    # Get raw DB transactions
    raw_txns = get_raw_transactions(license_id, lic_type)

    # Get canonical ledger
    canonical = get_canonical_ledger(license_id, lic_type)

    # Build matrix
    matrix = {
        'license_number': license_number,
        'license_type': lic_type,
        'license_id': license_id,
        'raw_transactions': raw_txns,
        'canonical_dataset': {
            'balance': float(canonical.get('license_running_balance', 0)),
            'closing_balance': float(canonical.get('closing_balance', 0)),
            'opening_balance': float(canonical.get('opening_balance', 0)),
            'has_purchase_bill': canonical.get('has_purchase_bill', False),
            'transactions_count': len(canonical.get('transactions', [])),
            'display_transactions_count': len(canonical.get('display_transactions', [])),
            'summary': canonical.get('summary', {}),
            'totals': {
                'purchases': float(canonical.get('totals', {}).get('total_purchases', 0)),
                'sales': float(canonical.get('totals', {}).get('total_sales', 0)),
                'commission': float(canonical.get('totals', {}).get('total_commission', 0)),
            },
            'company_utilizations': canonical.get('company_utilizations', {}),
        },
    }

    # Print summary
    print(f"\n1. RAW DATABASE TRANSACTIONS ({len(raw_txns)} total):")
    for i, txn in enumerate(raw_txns[:10]):  # Show first 10
        print(f"   {txn['date']} | {txn['type']:20} | ₹{txn.get('amount_inr', 0):>12.2f}")
    if len(raw_txns) > 10:
        print(f"   ... and {len(raw_txns) - 10} more")

    print(f"\n2. CANONICAL LEDGER SERVICE:")
    print(f"   Opening Balance: {canonical.get('opening_balance', 0)}")
    print(f"   Final Balance: {canonical.get('license_running_balance', 0)}")
    print(f"   Has Purchase Bill: {canonical.get('has_purchase_bill', False)}")
    print(f"   Total Transactions (all): {len(canonical.get('transactions', []))}")
    print(f"   Total Transactions (display): {len(canonical.get('display_transactions', []))}")

    summary = canonical.get('summary', {})
    print(f"\n3. SUMMARY (from canonical service):")
    print(f"   Total Debit (USD): {summary.get('total_debit', 0)}")
    print(f"   Total Credit (USD): {summary.get('total_credit', 0)}")
    print(f"   Total Debit Bill (INR): {summary.get('total_debit_bill', 0)}")
    print(f"   Total Credit Bill (INR): {summary.get('total_credit_bill', 0)}")
    print(f"   Current Balance: {summary.get('current_balance', 0)}")
    print(f"   Profit/Loss: {summary.get('total_profit_loss', 0)}")
    print(f"   Profit State: {summary.get('profit_state', 'N/A')}")

    return matrix


def main():
    """Run reconciliation for both licenses."""
    licenses = ['0310833996', '2616']
    results = {}

    for license_num in licenses:
        result = build_reconciliation_for_license(license_num)
        results[license_num] = result

        # Save to JSON for detailed inspection
        with open(f'/tmp/reconciliation_{license_num}.json', 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n[INFO] Detailed JSON saved to /tmp/reconciliation_{license_num}.json")

    print(f"\n{'='*100}")
    print("RECONCILIATION COMPLETE")
    print(f"{'='*100}")

    # Print comparison
    for license_num in licenses:
        if 'error' in results[license_num]:
            print(f"{license_num}: ERROR - {results[license_num]['error']}")
        else:
            data = results[license_num]
            print(f"\n{license_num}:")
            print(f"  Balance: {data['canonical_dataset']['balance']}")
            print(f"  Transactions: {data['canonical_dataset']['transactions_count']}")
            print(f"  Display Txns: {data['canonical_dataset']['display_transactions_count']}")
            print(f"  Raw DB Txns: {len(data['raw_transactions'])}")


if __name__ == '__main__':
    main()
