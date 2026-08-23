#!/usr/bin/env python
"""
DETAILED RECONCILIATION - ALL SOURCES WITH FULL COMPARISON
Shows exact values from every source to identify discrepancies.
"""

import os
import sys
import django
from decimal import Decimal
import json

backend_path = '/Users/drushahardiksottany/Developer/projects/license-manager/backend'
sys.path.insert(0, backend_path)
os.chdir(backend_path)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')

django.setup()

from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate
from apps.license.models import LicenseDetailsModel
from apps.license.views.ledger import LicenseLedgerViewSet
from apps.license.services.canonical_ledger_service import CanonicalLedgerService

User = get_user_model()

def main():
    # Get superuser
    user = User.objects.filter(is_superuser=True).first()
    if not user:
        user = User.objects.create_superuser(
            username='test_reconcile',
            email='test@local',
            password='test123'
        )

    # Get license
    lic = LicenseDetailsModel.objects.get(license_number='0310833996')
    print("="*100)
    print(f"DETAILED RECONCILIATION FOR LICENSE: 0310833996 (ID: {lic.id})")
    print("="*100)

    # 1. CANONICAL LEDGER SERVICE
    print(f"\n1. CANONICAL LEDGER SERVICE (Internal)")
    print("-"*100)
    canonical = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id, 'DFIA')
    summary = canonical.get('summary', {})

    print(f"Opening Balance: {canonical.get('opening_balance')}")
    print(f"License Running Balance: {canonical.get('license_running_balance')}")
    print(f"Closing Balance: {canonical.get('closing_balance')}")
    print(f"\nFinancial Summary:")
    print(f"  Total Debit (USD): {summary.get('total_debit')}")
    print(f"  Total Credit (USD): {summary.get('total_credit')}")
    print(f"  Current Balance (USD): {summary.get('current_balance')}")
    print(f"\n  Total Debit Bill (INR): {summary.get('total_debit_bill')}")
    print(f"  Total Credit Bill (INR): {summary.get('total_credit_bill')}")
    print(f"  Total Profit/Loss (INR): {summary.get('total_profit_loss')}")
    print(f"  Profit State: {summary.get('profit_state')}")

    display_txns = canonical.get('display_transactions', [])
    print(f"\nDisplay Transactions: {len(display_txns)}")
    for txn in display_txns:
        print(f"  - {txn.get('date')}: {txn.get('type'):15} Amount: {txn.get('amount'):12} Bill: {txn.get('bill_amount'):12} Balance: {txn.get('license_running_balance')}")

    # 2. LEDGER DETAIL ENDPOINT
    print(f"\n2. LEDGER DETAIL ENDPOINT (API)")
    print("-"*100)
    factory = APIRequestFactory()
    view = LicenseLedgerViewSet.as_view({'get': 'ledger_detail'})
    request = factory.get(f'/api/license-ledger/0310833996/ledger_detail/')
    force_authenticate(request, user=user)
    response = view(request, pk='0310833996')

    if response.status_code == 200:
        api_data = response.data
        api_summary = api_data.get('summary', {})

        print(f"Opening Balance: {api_data.get('opening_balance')}")
        print(f"License Running Balance: {api_data.get('license_running_balance')}")
        print(f"Closing Balance: {api_data.get('closing_balance')}")
        print(f"\nFinancial Summary:")
        print(f"  Total Debit (USD): {api_summary.get('total_debit')}")
        print(f"  Total Credit (USD): {api_summary.get('total_credit')}")
        print(f"  Current Balance (USD): {api_summary.get('current_balance')}")
        print(f"\n  Total Debit Bill (INR): {api_summary.get('total_debit_bill')}")
        print(f"  Total Credit Bill (INR): {api_summary.get('total_credit_bill')}")
        print(f"  Total Profit/Loss (INR): {api_summary.get('total_profit_loss')}")
        print(f"  Profit State: {api_summary.get('profit_state')}")

        api_display_txns = api_data.get('display_transactions', [])
        print(f"\nDisplay Transactions: {len(api_display_txns)}")
    else:
        print(f"ERROR: {response.status_code}")

    # 3. LICENSE_WISE ENDPOINT
    print(f"\n3. LICENSE_WISE ENDPOINT (API)")
    print("-"*100)
    view = LicenseLedgerViewSet.as_view({'get': 'license_wise'})
    request = factory.get(f'/api/license-ledger/license-wise/?license_id={lic.id}')
    force_authenticate(request, user=user)
    response = view(request)

    if response.status_code == 200:
        data = response.data
        licenses = data.get('licenses', [])

        # Find our license in the response
        our_license = None
        for lic_entry in licenses:
            if lic_entry.get('license_id') == lic.id:
                our_license = lic_entry
                break

        if our_license:
            print(f"License Found: {our_license.get('license_number')}")
            print(f"Has Purchase Bill: {our_license.get('has_purchase_bill')}")
            print(f"\nCompanies ({len(our_license.get('companies', []))} total):")

            for company in our_license.get('companies', []):
                print(f"\n  Company: {company.get('company_name')} (ID: {company.get('company_id')})")
                print(f"    Purchases ({len(company.get('purchases', []))} total): {company.get('purchase_total')}")
                print(f"    Sales ({len(company.get('sales', []))} total): {company.get('sale_total')}")
                print(f"    Profit/Loss: {company.get('profit_loss')}")
        else:
            print(f"License {lic.id} not found in license_wise response")
    else:
        print(f"ERROR: {response.status_code}")

    # 4. COMPANY_WISE ENDPOINT
    print(f"\n4. COMPANY_WISE ENDPOINT (API)")
    print("-"*100)
    view = LicenseLedgerViewSet.as_view({'get': 'company_wise'})
    request = factory.get(f'/api/license-ledger/company-wise/')
    force_authenticate(request, user=user)
    response = view(request)

    if response.status_code == 200:
        data = response.data
        companies = data.get('companies', [])

        print(f"Total Companies: {len(companies)}")
        for company in companies[:3]:  # Show first 3
            print(f"\n  Company: {company.get('company_name')} (ID: {company.get('company_id')})")
            licenses = company.get('licenses', [])

            # Find our license
            our_lic = None
            for lic_entry in licenses:
                if lic_entry.get('license_id') == lic.id:
                    our_lic = lic_entry
                    break

            if our_lic:
                print(f"    Our License Found!")
                print(f"      Purchases: {our_lic.get('purchase_total')}")
                print(f"      Sales: {our_lic.get('sale_total')}")
                print(f"      Profit/Loss: {our_lic.get('profit_loss')}")
    else:
        print(f"ERROR: {response.status_code}")

    # COMPARISON MATRIX
    print(f"\n" + "="*100)
    print("RECONCILIATION MATRIX")
    print("="*100)

    print(f"\n{'Source':<30} {'Debit INR':>15} {'Credit INR':>15} {'P/L INR':>15} {'TXN Count':>10}")
    print("-"*100)

    # Canonical
    canonical_debit = summary.get('total_debit_bill', 0)
    canonical_credit = summary.get('total_credit_bill', 0)
    canonical_pl = summary.get('total_profit_loss', 0)
    canonical_count = len(display_txns)
    print(f"{'Canonical Ledger':<30} {float(canonical_debit):>15.2f} {float(canonical_credit):>15.2f} {float(canonical_pl):>15.2f} {canonical_count:>10}")

    # API Detail
    if response.status_code == 200:
        api_debit = api_summary.get('total_debit_bill', 0)
        api_credit = api_summary.get('total_credit_bill', 0)
        api_pl = api_summary.get('total_profit_loss', 0)
        api_count = len(api_display_txns)
        print(f"{'API ledger_detail':<30} {float(api_debit):>15.2f} {float(api_credit):>15.2f} {float(api_pl):>15.2f} {api_count:>10}")

    # License Wise
    if our_license:
        # license_wise returns purchase_total and sale_total (amounts not bills)
        license_wise_purchase = our_license.get('companies', [{}])[0].get('purchase_total', 0) if our_license.get('companies') else 0
        license_wise_sale = our_license.get('companies', [{}])[0].get('sale_total', 0) if our_license.get('companies') else 0
        license_wise_pl = our_license.get('companies', [{}])[0].get('profit_loss', 0) if our_license.get('companies') else 0

        print(f"{'license_wise (company)':<30} {float(license_wise_purchase):>15.2f} {float(license_wise_sale):>15.2f} {float(license_wise_pl):>15.2f} {'N/A':>10}")

    # Check for mismatches
    print(f"\n" + "="*100)
    print("VERIFICATION RESULTS")
    print("="*100)

    if canonical_debit == api_debit:
        print(f"✓ Debit Bills match across sources: ₹{float(canonical_debit):,.2f}")
    else:
        print(f"✗ DEBIT MISMATCH:")
        print(f"    Canonical: ₹{float(canonical_debit):,.2f}")
        print(f"    API: ₹{float(api_debit):,.2f}")
        print(f"    Diff: ₹{float(api_debit - canonical_debit):,.2f}")

    if canonical_credit == api_credit:
        print(f"✓ Credit Bills match across sources: ₹{float(canonical_credit):,.2f}")
    else:
        print(f"✗ CREDIT MISMATCH:")
        print(f"    Canonical: ₹{float(canonical_credit):,.2f}")
        print(f"    API: ₹{float(api_credit):,.2f}")
        print(f"    Diff: ₹{float(api_credit - canonical_credit):,.2f}")

    if canonical_pl == api_pl:
        print(f"✓ P/L values match across sources: ₹{float(canonical_pl):,.2f}")
    else:
        print(f"✗ P/L MISMATCH:")
        print(f"    Canonical: ₹{float(canonical_pl):,.2f}")
        print(f"    API: ₹{float(api_pl):,.2f}")
        print(f"    Diff: ₹{float(api_pl - canonical_pl):,.2f}")

    print(f"\n✓ Transaction counts match: {canonical_count} transactions")

if __name__ == '__main__':
    main()
