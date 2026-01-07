#!/usr/bin/env python
"""Test script to verify corrected balance calculation logic"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')
django.setup()

from license.services.balance_calculator import LicenseBalanceCalculator
from license.models import LicenseDetailsModel

def test_balance_calculation():
    print("Testing LicenseBalanceCalculator with corrected logic")
    print("=" * 70)

    # Test with first 5 licenses
    licenses = LicenseDetailsModel.objects.all()[:5]

    if not licenses:
        print("No licenses found in database")
        return

    for license_obj in licenses:
        print(f"\nLicense: {license_obj.license_number}")
        print("-" * 70)

        # Calculate all components
        components = LicenseBalanceCalculator.calculate_all_components(license_obj)

        print(f"  Export CIF (Credit):      ${components['credit']:>12,.2f}")
        print(f"  BOE Debits (no trade):    ${components['debit']:>12,.2f}")
        print(f"  Trade Debits (all SALE):  ${components['trade']:>12,.2f}")
        print(f"  Allotments (no BOE):      ${components['allotment']:>12,.2f}")
        print(f"  {'-' * 68}")
        print(f"  Available Balance:        ${components['balance']:>12,.2f}")

        # Verify formula
        calculated = components['credit'] - (components['debit'] + components['trade'] + components['allotment'])
        match = "✓" if abs(calculated - components['balance']) < 0.01 else "✗"
        print(f"  Formula verification:     {match}")

        # Check current stored value
        if license_obj.balance_cif != components['balance']:
            print(f"  WARNING: Stored value ${license_obj.balance_cif:,.2f} differs from calculated ${components['balance']:,.2f}")

    print("\n" + "=" * 70)
    print("Test complete!")

if __name__ == "__main__":
    test_balance_calculation()
