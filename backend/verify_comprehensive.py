#!/usr/bin/env python3
"""Comprehensive database and service verification"""
import os
import sys
import django
from decimal import Decimal
from collections import defaultdict

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')
sys.path.insert(0, '/Users/drushahardiksottany/Developer/projects/license-manager/backend')

django.setup()

from django.db import connection, reset_queries
from django.test.utils import override_settings
from apps.license.models import LicenseDetailsModel, IncentiveLicense
from apps.trade.models import LicenseTrade
from apps.license.services.canonical_ledger_service import CanonicalLedgerService

print("\n" + "="*80)
print("COMPREHENSIVE DATABASE & SERVICE VERIFICATION")
print("="*80)

# Test licenses
test_licenses = ['0310833996', '2616']

for license_num in test_licenses:
    print(f"\n{'='*80}")
    print(f"LICENSE: {license_num}")
    print(f"{'='*80}")

    # Find license
    try:
        lic = LicenseDetailsModel.objects.get(license_number=license_num)
        print(f"✓ Found license: ID={lic.id}, Type=DFIA")
    except LicenseDetailsModel.DoesNotExist:
        print(f"✗ License not found")
        continue

    # 1. VERIFY BILL AMOUNTS
    print(f"\n1️⃣  BILL AMOUNT VERIFICATION:")

    trades = LicenseTrade.objects.filter(
        lines__sr_number__license=lic
    ).distinct()

    purchase_bill = Decimal('0')
    sale_bill = Decimal('0')

    for t in trades.filter(direction='PURCHASE'):
        bill = sum((line.amount_inr or Decimal('0')) for line in t.lines.filter(sr_number__license=lic))
        purchase_bill += bill

    for t in trades.filter(direction='SALE'):
        bill = sum((line.amount_inr or Decimal('0')) for line in t.lines.filter(sr_number__license=lic))
        sale_bill += bill

    print(f"  Database query via amount_inr fields:")
    print(f"    PURCHASE: ₹{purchase_bill:,.2f}")
    print(f"    SALE:     ₹{sale_bill:,.2f}")

    # 2. VERIFY CANONICAL SERVICE
    print(f"\n2️⃣  CANONICAL SERVICE VERIFICATION:")

    reset_queries()
    with override_settings(DEBUG=True):
        dataset = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id, 'DFIA')

    query_count = len(connection.queries)

    print(f"  Service results:")
    print(f"    PURCHASE bill (summary): ₹{dataset['summary']['total_purchase_bill_inr']:,.2f}")
    print(f"    SALE bill (summary): ₹{dataset['summary']['total_sale_bill_inr']:,.2f}")
    print(f"    Profit/Loss (INR): ₹{dataset['summary']['total_profit_loss']:,.2f}")
    print(f"    Balance (USD): ${dataset['summary']['current_balance']:,.2f}")

    # Verify values match database
    purchase_match = dataset['summary']['total_purchase_bill_inr'] == purchase_bill
    sale_match = dataset['summary']['total_sale_bill_inr'] == sale_bill

    if purchase_match and sale_match:
        print(f"  ✓ Service bill values match database")
    else:
        print(f"  ✗ Service values differ from database")
        if not purchase_match:
            print(f"    Purchase: DB={purchase_bill}, Service={dataset['summary']['total_purchase_bill_inr']}")
        if not sale_match:
            print(f"    Sale: DB={sale_bill}, Service={dataset['summary']['total_sale_bill_inr']}")

    # 3. VERIFY NO WRONG USD USAGE
    print(f"\n3️⃣  WRONG USD MAPPING CHECK:")

    # Check that balance_currency is USD (for DFIA)
    balance_currency = dataset['summary']['balance_currency']
    bill_currency = dataset['summary']['bill_currency']
    profit_currency = dataset['summary']['profit_currency']

    print(f"  Currencies in summary:")
    print(f"    balance_currency: {balance_currency} (license value)")
    print(f"    bill_currency: {bill_currency} (invoice amounts)")
    print(f"    profit_currency: {profit_currency} (profit/loss)")

    if balance_currency == 'USD' and bill_currency == 'INR' and profit_currency == 'INR':
        print(f"  ✓ Currencies are correct (balance=USD, bills/profit=INR)")
    else:
        print(f"  ✗ Currency mismatch")

    # 4. PERFORMANCE BASELINE
    print(f"\n4️⃣  PERFORMANCE BASELINE:")
    print(f"  Query count: {query_count}")
    print(f"  Target: ≤5 queries")

    if query_count <= 5:
        print(f"  ✓ Performance target MET")
    else:
        print(f"  ⚠ Queries exceed target (N+1 risk?)")
        print(f"\n  Query breakdown:")
        for i, q in enumerate(connection.queries[:10], 1):
            sql = q['sql']
            if len(sql) > 100:
                sql = sql[:100] + "..."
            print(f"    {i}. {sql}")

    # 5. DATA INTEGRITY
    print(f"\n5️⃣  DATA INTEGRITY CHECKS:")

    # Opening balance
    opening = dataset['opening_balance']
    print(f"  Opening balance: ${opening:,.2f}")

    # First purchase date
    first_purchase = dataset['first_purchase_date']
    print(f"  First purchase date: {first_purchase}")

    # Purchase bill flag
    has_pb = dataset['has_purchase_bill']
    pb_status = dataset['purchase_bill_status']
    print(f"  Has purchase bill: {has_pb} ({pb_status})")

    # Company filtering
    companies = defaultdict(Decimal)
    for txn in dataset['transactions']:
        if txn.get('company_id') and txn.get('type') in ['PURCHASE', 'SALE']:
            companies[txn['company_name']] += txn.get('amount', Decimal('0'))

    print(f"  Companies in ledger: {len(companies)}")
    for name in sorted(companies.keys()):
        print(f"    - {name}")

    # Balance reconciliation
    running_balance = dataset['license_running_balance']
    calc_balance = dataset['summary']['current_balance']

    print(f"\n  Balance reconciliation:")
    print(f"    Running balance: ${running_balance:,.2f}")
    print(f"    Summary balance: ${calc_balance:,.2f}")

    if running_balance == calc_balance:
        print(f"    ✓ Balances match")
    else:
        print(f"    ✗ Balance mismatch")

    # Transaction count
    txn_count = len(dataset['transactions'])
    display_count = len(dataset['display_transactions'])

    print(f"\n  Transactions:")
    print(f"    Total (with OPENING): {txn_count}")
    print(f"    Display (PURCHASE/SALE only): {display_count}")
    print(f"    Opening row shown: {dataset.get('opening_display') is not None}")

print(f"\n{'='*80}")
print("✓ VERIFICATION COMPLETE")
print(f"{'='*80}\n")
