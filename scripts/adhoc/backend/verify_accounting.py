#!/usr/bin/env python3
"""
Verify INR bill amounts and profit/loss calculations.

TASK: Verify accounting correctness of INR bill amounts.
- Confirm INR bill amounts are actual database values
- Verify profit/loss calculations
- Validate golden license 0310833996

Run with: python manage.py shell < verify_accounting.py
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')
django.setup()

from decimal import Decimal
from django.db.models import Sum, Q
from apps.trade.models import LicenseTrade, LicenseTradeLine
from apps.license.models import LicenseDetailsModel
from apps.license.services.license_profit import profit_for_licenses

def verify_license_accounting(license_number):
    """Verify accounting for one license."""
    print(f"\n{'='*70}")
    print(f"VERIFYING LICENSE: {license_number}")
    print('='*70)

    license = LicenseDetailsModel.objects.filter(license_number=license_number).first()
    if not license:
        print(f"ERROR: License {license_number} not found")
        return None

    print(f"License ID: {license.id}")
    print(f"Importer: {license.importer_name}")
    print(f"Period: {license.period}")

    # Get all purchase trades (external, non-linked)
    purchase_trades = LicenseTrade.objects.filter(
        lines__sr_number__license=license,
        direction=LicenseTrade.DIR_PURCHASE,
        linked_trade__isnull=True
    ).distinct()

    # Get all sale trades (external, non-linked)
    sale_trades = LicenseTrade.objects.filter(
        lines__sr_number__license=license,
        direction=LicenseTrade.DIR_SALE,
        linked_trade__isnull=True
    ).distinct()

    print(f"\n--- PURCHASE TRADES (External, Non-Linked) ---")
    print(f"Count: {purchase_trades.count()}")
    total_purchase_inr = Decimal('0')
    for trade in purchase_trades.order_by('invoice_date'):
        print(f"  {trade.invoice_number:<30} {trade.invoice_date} INR {trade.total_amount:>15.2f}")
        total_purchase_inr += trade.total_amount
    print(f"{'TOTAL PURCHASE (Database):':<51} INR {total_purchase_inr:>15.2f}")

    print(f"\n--- SALE TRADES (External, Non-Linked) ---")
    print(f"Count: {sale_trades.count()}")
    total_sale_inr = Decimal('0')
    for trade in sale_trades.order_by('invoice_date'):
        print(f"  {trade.invoice_number:<30} {trade.invoice_date} INR {trade.total_amount:>15.2f}")
        total_sale_inr += trade.total_amount
    print(f"{'TOTAL SALE (Database):':<51} INR {total_sale_inr:>15.2f}")

    # Calculate profit/loss manually
    manual_profit_loss = total_sale_inr - total_purchase_inr

    print(f"\n--- PROFIT/LOSS CALCULATION (Manual) ---")
    print(f"Sale Amount (INR):      {total_sale_inr:>15.2f}")
    print(f"Purchase Amount (INR):  {total_purchase_inr:>15.2f}")
    print(f"Profit/Loss (Sale-Purch): {manual_profit_loss:>13.2f}")

    # Verify using canonical profit function
    profit_data = profit_for_licenses([license.id]).get(license.id)

    print(f"\n--- CANONICAL PROFIT DATA (from profit_for_licenses) ---")
    print(f"Purchase Amount (INR):  {profit_data['purchase_amount']:>15.2f}")
    print(f"Sale Amount (INR):      {profit_data['sale_amount']:>15.2f}")
    print(f"Profit/Loss (INR):      {profit_data['profit_loss']:>15.2f}")
    print(f"Purchase USD (CIF):     {profit_data['purchase_usd']:>15.2f}")
    print(f"Sale USD (CIF):         {profit_data['sale_usd']:>15.2f}")

    # Verify calculations match
    print(f"\n--- VERIFICATION ---")
    purchase_match = profit_data['purchase_amount'] == total_purchase_inr
    sale_match = profit_data['sale_amount'] == total_sale_inr
    profit_match = profit_data['profit_loss'] == manual_profit_loss

    print(f"Purchase amounts match: {purchase_match}")
    if not purchase_match:
        print(f"  Database total:  {total_purchase_inr}")
        print(f"  Canonical:       {profit_data['purchase_amount']}")

    print(f"Sale amounts match:     {sale_match}")
    if not sale_match:
        print(f"  Database total:  {total_sale_inr}")
        print(f"  Canonical:       {profit_data['sale_amount']}")

    print(f"Profit/Loss calculations match: {profit_match}")
    if not profit_match:
        print(f"  Manual calc (Sale-Purchase):  {manual_profit_loss}")
        print(f"  Canonical (sale_amount-purchase_amount): {profit_data['profit_loss']}")

    return {
        'license_number': license_number,
        'license_id': license.id,
        'purchase_inr': total_purchase_inr,
        'sale_inr': total_sale_inr,
        'profit_loss': manual_profit_loss,
        'verification': {
            'purchase_match': purchase_match,
            'sale_match': sale_match,
            'profit_match': profit_match,
        }
    }

if __name__ == '__main__':
    # Test with golden license
    results = []

    # Golden license
    result = verify_license_accounting('0310833996')
    if result:
        results.append(result)

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print('='*70)

    all_match = all(
        r['verification']['purchase_match'] and
        r['verification']['sale_match'] and
        r['verification']['profit_match']
        for r in results
    )

    if all_match:
        print("✓ All INR bill amounts are actual invoice data: YES")
        print("✓ Profit/Loss calculations correct: YES")
        print("✓ Golden licenses verified: YES")
        print("✓ Any discrepancies found: NONE")
    else:
        print("✗ Discrepancies found - see details above")
        for r in results:
            if not all(r['verification'].values()):
                print(f"  License {r['license_number']}: MISMATCH")
