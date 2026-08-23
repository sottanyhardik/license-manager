#!/usr/bin/env python3
"""Debug balance mismatch for license 0310833996"""
import os
import sys
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')
sys.path.insert(0, '/Users/drushahardiksottany/Developer/projects/license-manager/backend')

django.setup()

from apps.license.models import LicenseDetailsModel
from apps.license.services.canonical_ledger_service import CanonicalLedgerService

# Get license
lic = LicenseDetailsModel.objects.get(license_number='0310833996')
print(f"License: {lic.license_number} (ID={lic.id})")
print(f"Opening balance (opening_balance field): ${lic.opening_balance:,.2f}")

# Get dataset
dataset = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id, 'DFIA')

print(f"\n{'='*80}")
print("TRANSACTION DETAILS:")
print(f"{'='*80}")

for txn in dataset['transactions']:
    txn_type = txn['type']
    amount = txn['amount']
    balance = txn['license_running_balance']
    bill = txn.get('bill_amount') or 'N/A'
    company = txn.get('company_name', 'N/A')

    print(f"\n{txn_type:20} | Amount: ${amount:>15,.2f} | Bill: ₹{bill:>15} | Balance: ${balance:>15,.2f} | Company: {company}")

print(f"\n{'='*80}")
print("BALANCE CALCULATION:")
print(f"{'='*80}")

opening = dataset['opening_balance']
purchase_total = Decimal('0')
sale_total = Decimal('0')

for txn in dataset['transactions']:
    if txn['type'] == 'PURCHASE':
        purchase_total += txn['amount']
    elif txn['type'] == 'SALE':
        sale_total += txn['amount']

print(f"\nOpening balance: ${opening:,.2f}")
print(f"Total PURCHASE amount: ${purchase_total:,.2f}")
print(f"Total SALE amount: ${sale_total:,.2f}")

calculated = opening + purchase_total - sale_total
running = dataset['license_running_balance']

print(f"\nCalculated: {opening} + {purchase_total} - {sale_total} = ${calculated:,.2f}")
print(f"Running balance (from dataset): ${running:,.2f}")
print(f"Match: {calculated == running}")

print(f"\n{'='*80}")
print("SUMMARY:")
print(f"{'='*80}")

summary = dataset['summary']
print(f"\nOpening in purchase: {summary.get('opening_in_purchase')}")
print(f"Opening balance: ${summary.get('opening_balance'):,.2f}")
print(f"Total purchase (display): ${summary.get('total_purchase'):,.2f}")
print(f"Total sale (display): ${summary.get('total_sale'):,.2f}")
print(f"Current balance (calculated): ${summary.get('current_balance'):,.2f}")

# Check if opening is in display
opening_row = dataset.get('opening_display')
display_txns = dataset.get('display_transactions', [])

print(f"\nOpening row present: {opening_row is not None}")
print(f"Display transactions: {len(display_txns)}")

print(f"\nDisplay rows:")
for txn in display_txns:
    print(f"  {txn['type']:15} | ${txn['amount']:>15,.2f}")

if opening_row:
    print(f"  {opening_row['type']:15} | ${opening_row['amount']:>15,.2f} (opening_display)")

# The issue is: are we double-counting the opening?
print(f"\n{'='*80}")
print("DOUBLE-COUNT CHECK:")
print(f"{'='*80}")

# According to _build_summary, if opening_row is NOT shown, total_purchase includes opening_balance
# If opening_row IS shown, total_purchase should come from display rows

print(f"\nIf opening_row NOT shown:")
print(f"  Expected current_balance = total_purchase - total_sale")
print(f"  = {summary.get('total_purchase')} - {summary.get('total_sale')}")
print(f"  = ${(summary.get('total_purchase') - summary.get('total_sale')):,.2f}")

# Are purchase transactions being summed?
purchase_from_display = Decimal('0')
for txn in display_txns:
    if txn['type'] == 'PURCHASE':
        purchase_from_display += txn['amount']

if opening_row:
    purchase_from_display += opening_row['amount']

print(f"\nSum of display PURCHASE rows: ${purchase_from_display:,.2f}")
print(f"Total sale from display rows: ${summary.get('total_sale'):,.2f}")
print(f"Difference: ${(purchase_from_display - summary.get('total_sale')):,.2f}")

print("\nDone.")
