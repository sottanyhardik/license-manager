#!/usr/bin/env python3
"""Find license with ID 2616 and verify"""
import os
import sys
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')
sys.path.insert(0, '/Users/drushahardiksottany/Developer/projects/license-manager/backend')

django.setup()

from django.db import connection, reset_queries
from django.test.utils import override_settings
from apps.license.models import LicenseDetailsModel, IncentiveLicense
from apps.trade.models import LicenseTrade
from apps.license.services.canonical_ledger_service import CanonicalLedgerService

print("Looking for license ID 2616...")

# Try DFIA
try:
    lic = LicenseDetailsModel.objects.get(id=2616)
    print(f"Found DFIA: {lic.license_number} (ID={lic.id})")
except LicenseDetailsModel.DoesNotExist:
    print("Not a DFIA license")
    lic = None

# Try Incentive
if not lic:
    try:
        lic = IncentiveLicense.objects.get(id=2616)
        print(f"Found IncentiveLicense: {lic.license_number} (ID={lic.id})")
    except IncentiveLicense.DoesNotExist:
        print("Not an IncentiveLicense")
        lic = None

if not lic:
    print("License ID 2616 not found in any table!")
else:
    # We already processed 0310833996 which is ID=2616
    # So let's find another interesting license to test
    print("\n" + "="*80)
    print("Finding another test license...")
    print("="*80)

    # Find a license with trades
    licenses = LicenseDetailsModel.objects.filter(
        lines__sr_number__trade_lines__trade__isnull=False
    ).distinct()[:5]

    print(f"\nFound {licenses.count()} licenses with trades:")

    for lic in licenses:
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

        trade_count = trades.count()

        if trade_count > 0:
            print(f"\n  License {lic.license_number} (ID={lic.id})")
            print(f"    Trades: {trade_count}")
            print(f"    PURCHASE bill: ₹{purchase_bill:,.2f}")
            print(f"    SALE bill: ₹{sale_bill:,.2f}")

            # Build canonical dataset to verify
            reset_queries()
            with override_settings(DEBUG=True):
                dataset = CanonicalLedgerService.build_canonical_ledger_dataset(lic.id, 'DFIA')

            query_count = len(connection.queries)
            print(f"    Query count: {query_count}")
            print(f"    Service PURCHASE bill: ₹{dataset['summary']['total_purchase_bill_inr']:,.2f}")
            print(f"    Service SALE bill: ₹{dataset['summary']['total_sale_bill_inr']:,.2f}")

            matches = (
                dataset['summary']['total_purchase_bill_inr'] == purchase_bill and
                dataset['summary']['total_sale_bill_inr'] == sale_bill
            )
            print(f"    Service matches DB: {matches} {'✓' if matches else '✗'}")
