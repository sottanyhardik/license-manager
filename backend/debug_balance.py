#!/usr/bin/env python
"""
Debug script to check balance calculation for license 0311045597
Run: python debug_balance.py
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')
django.setup()

from decimal import Decimal
from license.models import LicenseDetailsModel
from license.services.balance_calculator import LicenseBalanceCalculator
from allotment.models import AllotmentItems
from bill_of_entry.models import RowDetails
from trade.models import LicenseTradeLine

def debug_license_balance(license_number):
    try:
        license_obj = LicenseDetailsModel.objects.get(license_number=license_number)
        print(f"\n{'='*80}")
        print(f"License: {license_number}")
        print(f"{'='*80}")

        # Get components
        credit = LicenseBalanceCalculator.calculate_credit(license_obj)
        debit = LicenseBalanceCalculator.calculate_debit(license_obj)
        allotment = LicenseBalanceCalculator.calculate_allotment(license_obj)
        trade = LicenseBalanceCalculator.calculate_trade(license_obj)
        balance = LicenseBalanceCalculator.calculate_balance(license_obj)

        print(f"\n📊 Balance Components:")
        print(f"  Credit (Export CIF):     ${credit:,.2f}")
        print(f"  Debit (BOE):            -${debit:,.2f}")
        print(f"  Allotment (no BOE):     -${allotment:,.2f}")
        print(f"  Trade (no invoice):     -${trade:,.2f}")
        print(f"  {'─'*50}")
        print(f"  Calculated Balance:      ${balance:,.2f}")
        print(f"  Stored balance_cif:      ${license_obj.balance_cif:,.2f}")

        # Check allotments in detail
        print(f"\n🔍 Allotment Details:")
        allotment_items = AllotmentItems.objects.filter(
            item__license=license_obj
        ).select_related('allotment')

        print(f"  Total allotment items: {allotment_items.count()}")

        # Count with BOE
        allotments_with_boe = allotment_items.filter(
            allotment__bill_of_entry__isnull=False
        )
        print(f"  Allotments WITH BOE: {allotments_with_boe.count()}")
        for item in allotments_with_boe[:5]:
            boe_count = item.allotment.bill_of_entry.count()
            print(f"    - Allotment {item.allotment.id}: CIF ${item.cif_fc:,.2f} (linked to {boe_count} BOE)")

        # Count without BOE
        allotments_no_boe = allotment_items.filter(
            allotment__bill_of_entry__isnull=True
        )
        print(f"  Allotments WITHOUT BOE: {allotments_no_boe.count()}")
        total_no_boe = sum(item.cif_fc for item in allotments_no_boe)
        print(f"    Total CIF (no BOE): ${total_no_boe:,.2f}")
        for item in allotments_no_boe[:5]:
            print(f"    - Allotment {item.allotment.id}: CIF ${item.cif_fc:,.2f}")

        # Check BOE items
        print(f"\n🔍 BOE Details:")
        boe_items = RowDetails.objects.filter(
            sr_number__license=license_obj,
            transaction_type='DEBIT'
        )
        print(f"  Total BOE debit items: {boe_items.count()}")
        total_boe = sum(item.cif_fc for item in boe_items)
        print(f"    Total CIF: ${total_boe:,.2f}")

        # Check Trade items
        print(f"\n🔍 Trade Details:")
        from django.db.models import Q
        trade_items = LicenseTradeLine.objects.filter(
            sr_number__license=license_obj
        ).filter(
            Q(trade__boe__isnull=True) |
            Q(trade__boe__invoice_no__isnull=True) |
            Q(trade__boe__invoice_no='')
        )
        print(f"  Trade lines (no invoice): {trade_items.count()}")
        total_trade = sum(item.cif_fc for item in trade_items)
        print(f"    Total CIF: ${total_trade:,.2f}")

        # Final calculation
        print(f"\n✅ Manual Calculation:")
        print(f"  ${credit:,.2f} - (${debit:,.2f} + ${allotment:,.2f} + ${trade:,.2f})")
        manual_balance = credit - (debit + allotment + trade)
        print(f"  = ${manual_balance:,.2f}")

        if manual_balance != balance:
            print(f"\n⚠️  WARNING: Manual calculation doesn't match service!")

        if license_obj.balance_cif != balance:
            print(f"\n⚠️  WARNING: Stored balance_cif is outdated!")
            print(f"     Run: python manage.py update_balance_cif --license-number {license_number}")

    except LicenseDetailsModel.DoesNotExist:
        print(f"❌ License {license_number} not found!")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_license_balance("0311045597")
