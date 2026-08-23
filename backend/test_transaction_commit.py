#!/usr/bin/env python
"""Test if nested transactions are actually committing."""
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

# Clear
LicenseItemPlan.objects.filter(license_id=license_id).delete()

print("="*80)
print("Test: Are nested transactions committing?")
print("="*80)

print("\nStep 1: NEW Mode (should persist 1 row)")
try:
    with transaction.atomic() as outer_txn:
        print(f"  Outer transaction: {connection.in_atomic_block}")
        result = SionPlanningExecutionService.plan_sion(
            sion, [license_id], persist=True, mode="NEW"
        )
        count_inside = LicenseItemPlan.objects.filter(license_id=license_id).count()
        print(f"  Count INSIDE outer transaction: {count_inside}")
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()

count_outside = LicenseItemPlan.objects.filter(license_id=license_id).count()
print(f"  Count OUTSIDE transaction: {count_outside}")

if count_outside != 1:
    print(f"  ✗ ERROR: Expected 1 but got {count_outside}")
    sys.exit(1)

print("\nStep 2: ALL Mode (should DELETE + CREATE 1 row, still 1 total)")
count_before = count_outside
print(f"  Count before ALL: {count_before}")

try:
    with transaction.atomic() as outer_txn:
        print(f"  Outer transaction: {connection.in_atomic_block}")
        result = SionPlanningExecutionService.plan_sion(
            sion, [license_id], persist=True, mode="ALL"
        )
        count_inside = LicenseItemPlan.objects.filter(license_id=license_id).count()
        print(f"  Count INSIDE outer transaction: {count_inside}")

        # Force a flush to ensure all SQL is executed
        from django.db import connection as db_connection
        if hasattr(db_connection, 'queries_log'):
            print(f"  Queries: {len(db_connection.queries_log)}")
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback
    traceback.print_exc()

count_after = LicenseItemPlan.objects.filter(license_id=license_id).count()
print(f"  Count OUTSIDE transaction: {count_after}")

if count_after != count_before:
    print(f"  ✗ ERROR: Count changed from {count_before} to {count_after} (expected no change)")
    print(f"    This indicates the rows were deleted but not recreated")
else:
    print(f"  ✓ Count unchanged (but rows should have been recreated)")

# Check if it's the same row
plans_old = LicenseItemPlan.objects.filter(license_id=license_id).first()
if plans_old:
    print(f"\n  Persisted row: ID={plans_old.pk}, created_on={plans_old.created_on}")
