#!/usr/bin/env python
"""
Quick verification script to check if License 2509 has persisted plans.
"""
import os
import sys
import django

os.chdir('/Users/drushahardiksottany/Developer/projects/license-manager/backend')
sys.path.insert(0, '/Users/drushahardiksottany/Developer/projects/license-manager/backend')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')
django.setup()

from apps.license.models import LicenseDetailsModel, LicenseItemPlan
from decimal import Decimal

# Check License PK 2509
print("=" * 60)
print("LICENSE VERIFICATION")
print("=" * 60)

try:
    lic = LicenseDetailsModel.objects.get(pk=2509)
    print(f"✓ License PK 2509: {lic.license_number}")
except LicenseDetailsModel.DoesNotExist:
    print("✗ License PK 2509 NOT FOUND")
    exit(1)

# Check for License 3411008090
try:
    lic_check = LicenseDetailsModel.objects.get(license_number='3411008090')
    print(f"✓ License 3411008090 found at PK: {lic_check.pk}")
    if lic_check.pk != 2509:
        print(f"  WARNING: PK mismatch! 3411008090 is PK {lic_check.pk}, not 2509")
except LicenseDetailsModel.DoesNotExist:
    print("✗ License 3411008090 NOT FOUND in database")

# Check import items for this license
print("\n" + "=" * 60)
print("IMPORT ITEMS FOR LICENSE PK 2509")
print("=" * 60)

from apps.license.models import LicenseImportItemsModel

import_items = LicenseImportItemsModel.objects.filter(license_id=2509)
print(f"Total import items: {import_items.count()}")
if import_items.count() > 0:
    for item in import_items[:5]:
        print(f"  - ID: {item.id}, Description: {item.description}")

# Check LicenseItemPlan rows for PK 2509
# Check if there's a planning rule for this license
print("\n" + "=" * 60)
print("PLANNING RULES FOR LICENSE PK 2509")
print("=" * 60)

from apps.license.models import SionPlanningRule

rules = SionPlanningRule.objects.filter(license_id=2509)
print(f"Total planning rules: {rules.count()}")
if rules.count() > 0:
    for rule in rules:
        print(f"  - ID: {rule.id}, Name: {rule.name}, Strategy: {rule.strategy}")
        print(f"    Config: {rule.config}")

print("\n" + "=" * 60)
print("PLANNED ITEMS FOR LICENSE PK 2509")
print("=" * 60)

plans = LicenseItemPlan.objects.filter(import_item__license_id=2509).select_related('import_item', 'import_item__license')
print(f"Total plan rows: {plans.count()}")

if plans.count() == 0:
    print("✗ NO PLANS FOUND - this is the bug!")
else:
    print("✓ Plans exist!")
    total_qty = Decimal('0')
    total_cif = Decimal('0')

    for plan in plans[:20]:
        print(f"\n  ID: {plan.id}")
        print(f"    Import Item: {plan.import_item_id}")
        if plan.import_item:
            print(f"    Item Description: {plan.import_item.description}")
        print(f"    Quantity: {plan.requested_quantity}")
        print(f"    Planned CIF: {plan.planned_cif_fc}")
        total_qty += plan.requested_quantity
        total_cif += plan.planned_cif_fc or Decimal('0')

    print(f"\n  TOTALS:")
    print(f"    Total Quantity: {total_qty}")
    print(f"    Total CIF: {total_cif}")

print("\n" + "=" * 60)
