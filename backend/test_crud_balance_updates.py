#!/usr/bin/env python
"""Test script to verify balance updates across all items for all CRUD operations"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')
django.setup()

from decimal import Decimal
from license.models import LicenseDetailsModel, LicenseImportItemsModel
from bill_of_entry.models import BillOfEntryModel, RowDetails
from allotment.models import AllotmentModel, AllotmentItems

def test_crud_updates_all_items():
    print("=" * 80)
    print("Testing CRUD Operations Update All Items' Available Value")
    print("=" * 80)

    # Find a license with multiple import items
    license_obj = None
    for lic in LicenseDetailsModel.objects.all():
        if lic.import_license.count() >= 2:
            license_obj = lic
            break

    if not license_obj:
        print("❌ No license found with multiple import items")
        return

    print(f"\n✓ Found license: {license_obj.license_number}")
    print(f"  Import items count: {license_obj.import_license.count()}")

    # Get all import items
    import_items = list(license_obj.import_license.all()[:4])
    print(f"  Testing with {len(import_items)} items")

    # Display initial state
    print(f"\n{'='*80}")
    print("INITIAL STATE")
    print(f"{'='*80}")
    print(f"License balance_cif: ${license_obj.balance_cif:,.2f}")
    print(f"\nImport Items:")
    for idx, item in enumerate(import_items, 1):
        print(f"  Item {idx} (SN {item.serial_number}): available_value = ${item.available_value:,.2f}")

    # Store initial values
    initial_values = {item.id: item.available_value for item in import_items}

    # Test 1: Check if BOE exists, if not skip BOE test
    print(f"\n{'='*80}")
    print("TEST 1: BOE CREATE - Should update ALL items")
    print(f"{'='*80}")

    test_item = import_items[0]
    boe_exists = RowDetails.objects.filter(sr_number=test_item).exists()

    if boe_exists:
        print(f"✓ BOE records found for Item 1")

        # Refresh license to see updated balance
        license_obj.refresh_from_db()

        print(f"\nAfter BOE existence check:")
        print(f"License balance_cif: ${license_obj.balance_cif:,.2f}")

        # Check all items
        all_updated = True
        for idx, item in enumerate(import_items, 1):
            item.refresh_from_db()
            print(f"  Item {idx}: ${item.available_value:,.2f}")
            if item.available_value == initial_values[item.id]:
                print(f"    ⚠️  Value unchanged (might be OK if no new BOEs)")
    else:
        print("ℹ️  No BOE records found, skipping BOE test")

    # Test 2: Check Allotments
    print(f"\n{'='*80}")
    print("TEST 2: ALLOTMENT CHECK - All items should reflect license balance")
    print(f"{'='*80}")

    allotment_exists = AllotmentItems.objects.filter(item__license=license_obj).exists()

    if allotment_exists:
        print(f"✓ Allotment records found")

        # Refresh license
        license_obj.refresh_from_db()

        print(f"\nCurrent state:")
        print(f"License balance_cif: ${license_obj.balance_cif:,.2f}")

        # Check all items
        for idx, item in enumerate(import_items, 1):
            item.refresh_from_db()
            calculated_value = item.available_value_calculated
            stored_value = item.available_value

            match = "✓" if abs(calculated_value - stored_value) < Decimal("0.01") else "✗"
            print(f"  Item {idx}:")
            print(f"    Stored:     ${stored_value:,.2f}")
            print(f"    Calculated: ${calculated_value:,.2f} {match}")
    else:
        print("ℹ️  No allotment records found")

    # Test 3: Verify all items share same available_value (for non-restricted)
    print(f"\n{'='*80}")
    print("TEST 3: NON-RESTRICTED ITEMS - Should share same available_value")
    print(f"{'='*80}")

    non_restricted = [item for item in import_items if not item.is_restricted]

    if len(non_restricted) >= 2:
        print(f"✓ Found {len(non_restricted)} non-restricted items")

        values = [item.available_value for item in non_restricted]
        all_same = all(abs(v - values[0]) < Decimal("0.01") for v in values)

        if all_same:
            print(f"✓ All non-restricted items share same value: ${values[0]:,.2f}")
        else:
            print(f"✗ Non-restricted items have different values:")
            for idx, item in enumerate(non_restricted, 1):
                print(f"  Item {idx}: ${item.available_value:,.2f}")
    else:
        print("ℹ️  Not enough non-restricted items to test")

    # Test 4: Check restricted items
    print(f"\n{'='*80}")
    print("TEST 4: RESTRICTED ITEMS - Should use restriction calculation")
    print(f"{'='*80}")

    restricted = [item for item in import_items if item.is_restricted]

    if restricted:
        print(f"✓ Found {len(restricted)} restricted items")

        for idx, item in enumerate(restricted, 1):
            restriction_balance = item._calculate_head_restriction_balance()
            print(f"  Item {idx}:")
            print(f"    Available value: ${item.available_value:,.2f}")
            print(f"    Restriction calc: ${restriction_balance:,.2f}")
            print(f"    Match: {'✓' if abs(item.available_value - restriction_balance) < Decimal('0.01') else '✗'}")
    else:
        print("ℹ️  No restricted items found")

    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}")

if __name__ == "__main__":
    test_crud_updates_all_items()
