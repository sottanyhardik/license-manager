#!/usr/bin/env python
"""
CRITICAL QA RECONCILIATION TEST - SMOKING GUN

Creates comprehensive reconciliation matrices for licenses showing:
1. Raw transaction counts from database
2. Canonical ledger calculations
3. Comparison across all data sources
4. Root cause analysis of discrepancies
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
from apps.trade.models import LicenseTrade, LicenseTradeLine
from django.db.models import Q, Sum


def build_reconciliation_matrix(license_number):
    """Build comprehensive reconciliation matrix for a single license."""

    # Find license
    try:
        lic = LicenseDetailsModel.objects.get(license_number=license_number)
        lic_type = 'DFIA'
    except LicenseDetailsModel.DoesNotExist:
        try:
            lic = IncentiveLicense.objects.get(license_number=license_number)
            lic_type = 'INCENTIVE'
        except IncentiveLicense.DoesNotExist:
            return None

    license_id = lic.id

    # 1. RAW DATABASE EXTRACTION
    # Get all trades and line items
    if lic_type == 'DFIA':
        trades = LicenseTrade.objects.filter(
            license_type='DFIA',
            lines__sr_number__license_id=license_id
        ).prefetch_related('lines', 'from_company', 'to_company').distinct()
    else:
        trades = LicenseTrade.objects.filter(
            license_type='INCENTIVE',
            incentive_lines__incentive_license_id=license_id
        ).prefetch_related('incentive_lines', 'from_company', 'to_company').distinct()

    # Build raw transaction list
    raw_txns = []
    for trade in trades:
        if lic_type == 'DFIA':
            lines = trade.lines.filter(sr_number__license_id=license_id)
        else:
            lines = trade.incentive_lines.filter(incentive_license_id=license_id)

        for line in lines:
            if lic_type == 'DFIA':
                amount_inr = float(line.amount_inr or 0)
                cif_usd = float(line.cif_fc or 0)
            else:
                amount_inr = float(line.amount_inr or 0)
                cif_usd = 0

            raw_txns.append({
                'trade_id': trade.id,
                'invoice_date': trade.invoice_date,
                'direction': trade.direction,
                'from_company': trade.from_company.name if trade.from_company else None,
                'to_company': trade.to_company.name if trade.to_company else None,
                'amount_inr': amount_inr,
                'cif_usd': cif_usd,
                'line_id': line.id,
            })

    raw_txns.sort(key=lambda x: (x['invoice_date'] or datetime.min.date(), x['trade_id'], x['line_id']))

    # Aggregate raw data
    raw_purchases_inr = sum(t['amount_inr'] for t in raw_txns if t['direction'] == 'PURCHASE')
    raw_sales_inr = sum(t['amount_inr'] for t in raw_txns if t['direction'] == 'SALE')
    raw_purchases_usd = sum(t['cif_usd'] for t in raw_txns if t['direction'] == 'PURCHASE')
    raw_sales_usd = sum(t['cif_usd'] for t in raw_txns if t['direction'] == 'SALE')

    # 2. CANONICAL LEDGER SERVICE
    try:
        canonical = CanonicalLedgerService.build_canonical_ledger_dataset(license_id, lic_type)
    except Exception as e:
        canonical = {'error': str(e)}

    # Extract canonical values
    canonical_error = canonical.get('error')
    canonical_txns_all = canonical.get('transactions', [])
    canonical_txns_display = canonical.get('display_transactions', [])
    canonical_totals = canonical.get('totals', {})
    canonical_summary = canonical.get('summary', {})
    canonical_balance = canonical.get('license_running_balance', 0)
    canonical_opening = canonical.get('opening_balance', 0)

    # 3. BUILD RECONCILIATION TABLE
    reconciliation = {
        'license_number': license_number,
        'license_type': lic_type,
        'license_id': license_id,
        'data_sources': {
            'raw_database': {
                'transaction_count': len(raw_txns),
                'purchases_count': len([t for t in raw_txns if t['direction'] == 'PURCHASE']),
                'sales_count': len([t for t in raw_txns if t['direction'] == 'SALE']),
                'purchases_inr': raw_purchases_inr,
                'sales_inr': raw_sales_inr,
                'purchases_usd': raw_purchases_usd,
                'sales_usd': raw_sales_usd,
            },
            'canonical_service': {
                'all_transactions_count': len(canonical_txns_all),
                'display_transactions_count': len(canonical_txns_display),
                'opening_transaction': 1 if canonical_opening > 0 else 0,
                'commission_count': len([t for t in canonical_txns_all if t.get('is_commission')]),
                'purchases_total_usd': float(canonical_totals.get('total_purchases', 0)),
                'sales_total_usd': float(canonical_totals.get('total_sales', 0)),
                'commission_total_usd': float(canonical_totals.get('total_commission', 0)),
                'opening_balance_usd': float(canonical_opening),
                'final_balance_usd': float(canonical_balance),
            },
            'summary_block': {
                'total_debit_usd': float(canonical_summary.get('total_debit', 0)),
                'total_credit_usd': float(canonical_summary.get('total_credit', 0)),
                'total_debit_bill_inr': float(canonical_summary.get('total_debit_bill', 0)),
                'total_credit_bill_inr': float(canonical_summary.get('total_credit_bill', 0)),
                'current_balance_usd': float(canonical_summary.get('current_balance', 0)),
                'profit_loss_inr': float(canonical_summary.get('total_profit_loss', 0)),
                'profit_state': canonical_summary.get('profit_state', 'UNKNOWN'),
            }
        },
        'raw_transactions': raw_txns,
        'canonical_transactions': [
            {
                'date': str(t.get('date')),
                'id': t.get('id'),
                'type': t.get('type'),
                'company': t.get('company_name'),
                'amount': float(t.get('amount', 0)),
                'is_commission': t.get('is_commission', False),
                'affects_balance': t.get('affects_balance', False),
                'running_balance': float(t.get('license_running_balance', 0)),
            }
            for t in canonical_txns_all
        ]
    }

    return reconciliation


def print_reconciliation_report(reconciliation):
    """Print human-readable reconciliation report."""

    if not reconciliation:
        print("License not found")
        return

    lic_num = reconciliation['license_number']
    lic_type = reconciliation['license_type']

    print(f"\n{'='*120}")
    print(f"RECONCILIATION REPORT: License {lic_num} ({lic_type})")
    print(f"{'='*120}")

    raw = reconciliation['data_sources']['raw_database']
    canonical = reconciliation['data_sources']['canonical_service']
    summary = reconciliation['data_sources']['summary_block']

    # Transaction counts
    print(f"\n1. TRANSACTION COUNTS:")
    print(f"   Raw DB Transactions: {raw['transaction_count']}")
    print(f"     - Purchases: {raw['purchases_count']}")
    print(f"     - Sales: {raw['sales_count']}")
    print(f"   Canonical All Txns: {canonical['all_transactions_count']}")
    print(f"     - Opening: {canonical['opening_transaction']}")
    print(f"   Canonical Display Txns: {canonical['display_transactions_count']}")

    discrepancy_all = canonical['all_transactions_count'] - raw['transaction_count']
    if discrepancy_all != 0:
        reason = " (Opening row added by service)" if canonical['opening_transaction'] == 1 else ""
        print(f"   *** DISCREPANCY: {discrepancy_all} more in canonical than raw{reason}")

    # Amount reconciliation (USD)
    print(f"\n2. AMOUNT RECONCILIATION (USD):")
    print(f"   Raw DB:")
    print(f"     Purchases: ${raw['purchases_usd']:.2f}")
    print(f"     Sales: ${raw['sales_usd']:.2f}")
    print(f"   Canonical Service Totals:")
    print(f"     Purchases: ${canonical['purchases_total_usd']:.2f}")
    print(f"     Sales: ${canonical['sales_total_usd']:.2f}")

    if abs(raw['purchases_usd'] - canonical['purchases_total_usd']) > 0.01:
        print(f"   *** DISCREPANCY IN PURCHASES: ${abs(raw['purchases_usd'] - canonical['purchases_total_usd']):.2f}")
    if abs(raw['sales_usd'] - canonical['sales_total_usd']) > 0.01:
        print(f"   *** DISCREPANCY IN SALES: ${abs(raw['sales_usd'] - canonical['sales_total_usd']):.2f}")

    # Bill amounts (INR)
    print(f"\n3. BILL AMOUNTS (INR) - Summary Block:")
    print(f"   Total Debit Bill: ₹{summary['total_debit_bill_inr']:.2f}")
    print(f"   Total Credit Bill: ₹{summary['total_credit_bill_inr']:.2f}")
    print(f"   Raw DB:")
    print(f"     Purchases: ₹{raw['purchases_inr']:.2f}")
    print(f"     Sales: ₹{raw['sales_inr']:.2f}")

    # Balances
    print(f"\n4. BALANCE RECONCILIATION (USD):")
    print(f"   Canonical Opening: ${canonical['opening_balance_usd']:.2f}")
    print(f"   Canonical Final: ${canonical['final_balance_usd']:.2f}")
    print(f"   Summary Block Current: ${summary['current_balance_usd']:.2f}")

    if abs(canonical['final_balance_usd'] - summary['current_balance_usd']) > 0.01:
        print(f"   *** DISCREPANCY: Canonical final (${canonical['final_balance_usd']:.2f}) vs Summary current (${summary['current_balance_usd']:.2f})")

    # P&L
    print(f"\n5. PROFIT/LOSS (INR):")
    print(f"   Summary Block P&L: ₹{summary['profit_loss_inr']:.2f}")
    print(f"   Profit State: {summary['profit_state']}")
    calculated_pl = summary['total_credit_bill_inr'] - summary['total_debit_bill_inr']
    if abs(summary['profit_loss_inr'] - calculated_pl) > 0.01:
        print(f"   *** DISCREPANCY: Summary P&L (₹{summary['profit_loss_inr']:.2f}) != Credit-Debit (₹{calculated_pl:.2f})")

    # Show detailed transaction breakdown
    print(f"\n6. DETAILED CANONICAL TRANSACTIONS:")
    print(f"   {'Date':<12} {'ID':<5} {'Type':<15} {'Company':<20} {'Amount (USD)':<15} {'Running Balance':<15}")
    print(f"   {'-'*88}")
    for txn in reconciliation['canonical_transactions'][:15]:
        print(f"   {txn['date']:<12} {txn['id']:<5} {txn['type']:<15} {(txn['company'] or '')[:19]:<20} ${txn['amount']:<14.2f} ${txn['running_balance']:<14.2f}")
    if len(reconciliation['canonical_transactions']) > 15:
        print(f"   ... and {len(reconciliation['canonical_transactions']) - 15} more transactions")


def main():
    """Run full reconciliation for multiple licenses."""

    test_licenses = ['0310833996', '0310834296']
    all_reconciliations = {}

    print(f"\nSTARTING QA RECONCILIATION TEST")
    print(f"Licenses: {', '.join(test_licenses)}")

    for lic_num in test_licenses:
        reconciliation = build_reconciliation_matrix(lic_num)
        all_reconciliations[lic_num] = reconciliation
        print_reconciliation_report(reconciliation)

    # Save full data to JSON
    with open('/tmp/reconciliation_full.json', 'w') as f:
        json.dump(all_reconciliations, f, indent=2, default=str)
    print(f"\n[INFO] Full reconciliation data saved to /tmp/reconciliation_full.json")

    # Final summary
    print(f"\n{'='*120}")
    print("RECONCILIATION TEST COMPLETE")
    print(f"{'='*120}")


if __name__ == '__main__':
    main()
