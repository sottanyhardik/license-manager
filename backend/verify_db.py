#!/usr/bin/env python3
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')
sys.path.insert(0, '/Users/drushahardiksottany/Developer/projects/license-manager/backend')

django.setup()

from decimal import Decimal
from apps.license.models import LicenseDetailsModel
from apps.trade.models import LicenseTrade

# Test license 0310833996
try:
    lic = LicenseDetailsModel.objects.get(license_number='0310833996')
    print(f"✓ Found license 0310833996: ID={lic.id}")

    # Get trades
    trades = LicenseTrade.objects.filter(
        lines__sr_number__license=lic
    ).distinct()

    print(f"\n  Total trades: {trades.count()}")

    # PURCHASE
    purchase_bill = Decimal('0')
    purchase_trades = trades.filter(direction='PURCHASE')
    for t in purchase_trades:
        bill = sum(
            (line.amount_inr or Decimal('0'))
            for line in t.lines.filter(sr_number__license=lic)
        )
        purchase_bill += bill

    print(f"  PURCHASE bill total: ₹{purchase_bill:,.2f}")
    print(f"  Expected: ₹45,83,719.00")
    print(f"  Match: {purchase_bill == Decimal('4583719.00')}")

    # SALE
    sale_bill = Decimal('0')
    sale_trades = trades.filter(direction='SALE')
    for t in sale_trades:
        bill = sum(
            (line.amount_inr or Decimal('0'))
            for line in t.lines.filter(sr_number__license=lic)
        )
        sale_bill += bill

    print(f"\n  SALE bill total: ₹{sale_bill:,.2f}")
    print(f"  Expected: ₹65,24,056.00")
    print(f"  Match: {sale_bill == Decimal('6524056.00')}")

except LicenseDetailsModel.DoesNotExist:
    print(f"✗ License 0310833996 not found")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("\nDone.")
