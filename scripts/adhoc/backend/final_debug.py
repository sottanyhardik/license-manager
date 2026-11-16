#!/usr/bin/env python
"""Final debug: is the transaction actually committing?"""
import os, sys, django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')
django.setup()

from apps.license.models import LicenseDetailsModel, LicenseItemPlan
from apps.core.models import SionNormClassModel
from apps.license.services.sion_planning_execution import SionPlanningExecutionService
from django.db import transaction, connection

license_id = 2547
sion_id = 2

license_obj = LicenseDetailsModel.objects.get(pk=license_id)
sion = SionNormClassModel.objects.get(pk=sion_id)

# Clear and create one row
LicenseItemPlan.objects.filter(license_id=license_id).delete()
with transaction.atomic():
    SionPlanningExecutionService.plan_sion(
        sion, [license_id], persist=True, mode="NEW"
    )

print("="*80)
print("FINAL DEBUG: Transaction commit behavior")
print("="*80 + "\n")

print("Before ALL mode:")
count1 = LicenseItemPlan.objects.filter(license_id=license_id).count()
print(f"  Rows in DB: {count1}")

print("\nDuring ALL mode (inside transaction):")
try:
    txn = transaction.atomic()
    txn.__enter__()
    print(f"  In transaction block: {connection.in_atomic_block}")

    result = SionPlanningExecutionService.plan_sion(
        sion, [license_id], persist=True, mode="ALL"
    )

    count2 = LicenseItemPlan.objects.filter(license_id=license_id).count()
    print(f"  Rows in DB (inside txn): {count2}")

    # Don't exit normally - check transaction state
    print(f"  About to commit transaction...")
    print(f"  Transaction state: {connection.get_autocommit()}")

    txn.__exit__(None, None, None)
    print(f"  Transaction exited normally")

except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()
    txn.__exit__(*sys.exc_info())

print("\nAfter ALL mode:")
count3 = LicenseItemPlan.objects.filter(license_id=license_id).count()
print(f"  Rows in DB: {count3}")

print("\n" + "="*80)
if count3 == count1:
    print("✗ BUG: Rows NOT persisted in ALL mode!")
    if count2 == count1:
        print("  (and count was even different INSIDE transaction)")
else:
    print(f"✓ Rows persisted: {count1} → {count3}")
