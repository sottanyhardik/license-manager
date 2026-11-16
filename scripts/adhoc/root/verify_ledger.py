#!/usr/bin/env python
"""
Verify license ledger API for license 0310833996
"""
import os
import sys
import django

# Setup Django environment
project_root = '/Users/drushahardiksottany/Developer/projects/license-manager/backend'
sys.path.insert(0, project_root)
os.chdir(project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from decimal import Decimal
from apps.license.models import LicenseDetailsModel
from apps.license.services.canonical_ledger_service import CanonicalLedgerService

# License to verify
license_number = '0310833996'

# Step 1: Query the license
print("=" * 70)
print("STEP 1: QUERY LICENSE")
print("=" * 70)

try:
    license = LicenseDetailsModel.objects.get(license_number=license_number)
    print(f"✓ Found license: {license_number}")
    print(f"  - License ID: {license.id}")
    print(f"  - License Type: DFIA")
    print(f"  - License Date: {license.license_date}")
    print(f"  - Expiry Date: {license.license_expiry_date}")
    print(f"  - Exporter: {license.exporter.company_name if license.exporter else 'N/A'}")
except LicenseDetailsModel.DoesNotExist:
    print(f"✗ License {license_number} not found")
    sys.exit(1)

# Step 2: Run CanonicalLedgerService
print("\n" + "=" * 70)
print("STEP 2: FETCH LEDGER DATASET")
print("=" * 70)

try:
    ledger_dataset = CanonicalLedgerService.build_canonical_ledger_dataset(license.id, 'DFIA')
    print(f"✓ Ledger dataset built successfully")
    print(f"  - Total transactions: {len(ledger_dataset['transactions'])}")
    print(f"  - Display transactions: {len(ledger_dataset['display_transactions'])}")
    print(f"  - Opening display: {ledger_dataset.get('opening_display') is not None}")
except Exception as e:
    print(f"✗ Error building ledger dataset: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 3: Extract and report license metadata
print("\n" + "=" * 70)
print("LICENSE METADATA")
print("=" * 70)

print(f"License Number: {ledger_dataset.get('license_number')}")
print(f"License Type: {ledger_dataset.get('license_type')}")
print(f"Exporter: {ledger_dataset.get('exporter_name')}")
print(f"License Date: {ledger_dataset.get('license_date')}")
print(f"Expiry Date: {ledger_dataset.get('expiry_date')}")
print(f"Port: {ledger_dataset.get('port_name')}")
print(f"First Purchase Date: {ledger_dataset.get('first_purchase_date')}")
print(f"Has Purchase Bill: {ledger_dataset.get('has_purchase_bill')}")
print(f"Purchase Bill Status: {ledger_dataset.get('purchase_bill_status')}")

# Step 4: Report balances and totals
print("\n" + "=" * 70)
print("BALANCES AND TOTALS")
print("=" * 70)

print(f"Opening Balance: {ledger_dataset.get('opening_balance')} USD")
print(f"License Running Balance: {ledger_dataset.get('license_running_balance')} USD")
print(f"Closing Balance: {ledger_dataset.get('closing_balance')} USD")

totals = ledger_dataset.get('totals', {})
print(f"\nTotal Purchases: {totals.get('total_purchases')} USD")
print(f"Total Sales: {totals.get('total_sales')} USD")
print(f"Total Commission: {totals.get('total_commission')} USD")

# Step 5: Report summary block
print("\n" + "=" * 70)
print("SUMMARY BLOCK (Display Values)")
print("=" * 70)

summary = ledger_dataset.get('summary', {})
print(f"Total Credit (displayed): {summary.get('total_credit')} {summary.get('balance_currency', 'USD')}")
print(f"Total Debit (displayed): {summary.get('total_debit')} {summary.get('balance_currency', 'USD')}")
print(f"Total Credit Bill (INR): {summary.get('total_credit_bill')} INR")
print(f"Total Debit Bill (INR): {summary.get('total_debit_bill')} INR")
print(f"Opening Balance: {summary.get('opening_balance')} {summary.get('balance_currency', 'USD')}")
print(f"Opening in Debit: {summary.get('opening_in_debit')}")
print(f"Current Balance: {summary.get('current_balance')} {summary.get('balance_currency', 'USD')}")
print(f"Total Profit/Loss: {summary.get('total_profit_loss')} {summary.get('profit_currency', 'USD')}")
print(f"Profit State: {summary.get('profit_state')}")

# Step 6: Report all transactions (full list)
print("\n" + "=" * 70)
print("ALL TRANSACTIONS (Full List)")
print("=" * 70)

transactions = ledger_dataset.get('transactions', [])
print(f"Total transactions in full list: {len(transactions)}\n")

for i, txn in enumerate(transactions):
    print(f"[{i}] Transaction ID: {txn.get('id')}")
    print(f"    Date: {txn.get('date')}")
    print(f"    Type: {txn.get('type')}")
    print(f"    Amount: {txn.get('amount')} USD")
    print(f"    Bill Amount: {txn.get('bill_amount')} INR")
    print(f"    Company: {txn.get('company_name')} (ID: {txn.get('company_id')})")
    print(f"    Party: {txn.get('party_name')} (ID: {txn.get('party_id')})")
    print(f"    Is Commission: {txn.get('is_commission')}")
    print(f"    Affects Balance: {txn.get('affects_balance')}")
    print(f"    Running Balance: {txn.get('license_running_balance')} USD")
    print(f"    Company Utilization: {txn.get('company_utilization_after')}")
    print(f"    SION Norms: {txn.get('sion_norms')}")
    print()

# Step 7: Analyze display transactions vs full transactions
print("\n" + "=" * 70)
print("DISPLAY ANALYSIS")
print("=" * 70)

full_transactions = ledger_dataset.get('transactions', [])
display_transactions = ledger_dataset.get('display_transactions', [])
opening_display = ledger_dataset.get('opening_display')

# Count transaction types in full list
opening_count = sum(1 for t in full_transactions if t.get('type') == 'OPENING')
purchase_count = sum(1 for t in full_transactions if t.get('type') == 'PURCHASE')
sale_count = sum(1 for t in full_transactions if t.get('type') == 'SALE')
commission_count = sum(1 for t in full_transactions if 'COMMISSION' in t.get('type', ''))

print(f"Full transactions count: {len(full_transactions)}")
print(f"  - OPENING: {opening_count}")
print(f"  - PURCHASE: {purchase_count}")
print(f"  - SALE: {sale_count}")
print(f"  - COMMISSION: {commission_count}")

print(f"\nDisplay transactions count: {len(display_transactions)}")
# Count types in display list
if display_transactions:
    display_purchase = sum(1 for t in display_transactions if t.get('type') == 'PURCHASE')
    display_sale = sum(1 for t in display_transactions if t.get('type') == 'SALE')
    print(f"  - PURCHASE: {display_purchase}")
    print(f"  - SALE: {display_sale}")

print(f"\nOpening Display: {opening_display is not None}")
if opening_display:
    print(f"  - Date: {opening_display.get('date')}")
    print(f"  - Type: {opening_display.get('type')}")
    print(f"  - Amount: {opening_display.get('amount')}")

# Explain why opening is shown or not
print(f"\n--- Display Rule Analysis ---")
has_purchase = purchase_count > 0
print(f"Has PURCHASE transactions: {has_purchase}")
if opening_display:
    print(f"Opening is displayed because: NO PURCHASE exists")
else:
    if has_purchase:
        print(f"Opening is NOT displayed because: PURCHASE exists (opening suppressed when purchase is present)")
    else:
        print(f"Opening is NOT displayed because: NO opening balance or NO opening transaction")

# Step 8: Report company utilizations
print("\n" + "=" * 70)
print("COMPANY UTILIZATIONS")
print("=" * 70)

company_utilizations = ledger_dataset.get('company_utilizations', {})
if company_utilizations:
    print(f"Total companies: {len(company_utilizations)}\n")
    for company_id, util in company_utilizations.items():
        print(f"Company ID: {company_id}")
        print(f"  - Name: {util.get('company_name')}")
        print(f"  - Utilization Balance: {util.get('utilization_balance')} USD")
        print()
else:
    print("No company utilizations found")

# Step 9: Check for data quality issues
print("\n" + "=" * 70)
print("DATA QUALITY CHECKS")
print("=" * 70)

issues = []

# Check 1: Opening balance consistency
opening_balance = ledger_dataset.get('opening_balance')
if ledger_dataset['transactions'] and ledger_dataset['transactions'][0].get('type') == 'OPENING':
    first_txn_opening = ledger_dataset['transactions'][0].get('amount')
    if opening_balance != first_txn_opening:
        issues.append(f"Opening balance mismatch: dataset={opening_balance}, first_txn={first_txn_opening}")

# Check 2: Final balance consistency
final_balance = ledger_dataset.get('license_running_balance')
if ledger_dataset['transactions']:
    last_txn_balance = ledger_dataset['transactions'][-1].get('license_running_balance')
    if final_balance != last_txn_balance:
        issues.append(f"Final balance mismatch: dataset={final_balance}, last_txn={last_txn_balance}")

# Check 3: Summary block consistency
summary = ledger_dataset.get('summary', {})
current_balance = summary.get('current_balance')
total_profit_loss = summary.get('total_profit_loss')
if current_balance != total_profit_loss:
    issues.append(f"Summary consistency: current_balance={current_balance} != total_profit_loss={total_profit_loss}")

# Check 4: Profit state validity
profit_state = summary.get('profit_state')
valid_states = ['PROFIT', 'LOSS', 'BREAK_EVEN', 'UNAVAILABLE']
if profit_state not in valid_states:
    issues.append(f"Invalid profit_state: {profit_state}")

# Check 5: Verify profit state is correct
balance = summary.get('current_balance', Decimal('0.00'))
if balance > Decimal('0.00') and profit_state != 'PROFIT':
    issues.append(f"Profit state mismatch: balance={balance} (positive) but profit_state={profit_state} (not PROFIT)")
elif balance < Decimal('0.00') and profit_state != 'LOSS':
    issues.append(f"Profit state mismatch: balance={balance} (negative) but profit_state={profit_state} (not LOSS)")
elif balance == Decimal('0.00') and profit_state != 'BREAK_EVEN':
    issues.append(f"Profit state mismatch: balance={balance} (zero) but profit_state={profit_state} (not BREAK_EVEN)")

# Check 6: Display transactions should not contain OPENING
for txn in ledger_dataset.get('display_transactions', []):
    if txn.get('type') == 'OPENING':
        issues.append("Display transactions contains OPENING row (should be in opening_display only)")

# Check 7: Commission transactions should not affect balance
for txn in ledger_dataset.get('transactions', []):
    if 'COMMISSION' in txn.get('type', '') and txn.get('affects_balance'):
        issues.append(f"Commission transaction {txn.get('id')} marked as affects_balance=True")

# Report issues
if issues:
    print(f"Found {len(issues)} issues:\n")
    for issue in issues:
        print(f"  ✗ {issue}")
else:
    print("✓ No data quality issues found")

print("\n" + "=" * 70)
print("VERIFICATION COMPLETE")
print("=" * 70)
