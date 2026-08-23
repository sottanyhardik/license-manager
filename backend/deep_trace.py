#!/usr/bin/env python
"""Deep trace showing the persistence bug in ALL mode."""
import os, sys, django
from decimal import Decimal
from django.db import transaction, connection

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')
django.setup()

from apps.license.models import LicenseDetailsModel, LicenseItemPlan
from apps.core.models import SionNormClassModel
from apps.license.services.sion_planning_execution import SionPlanningExecutionService

license_id = 2547
sion_id = 2

license_obj = LicenseDetailsModel.objects.get(pk=license_id)
sion = SionNormClassModel.objects.get(pk=sion_id)

print("="*80)
print("DEEP TRACE: NEW Mode then ALL Mode")
print("="*80)

# Clear any existing plans
print("\nStep 0: Clear existing plans")
LicenseItemPlan.objects.filter(license_id=license_id).delete()
count_initial = LicenseItemPlan.objects.filter(license_id=license_id).count()
print(f"Plans in DB: {count_initial}")

# NEW Mode
print("\nStep 1: Execute NEW Mode")
with transaction.atomic():
    print("  Inside transaction...")
    result_new = SionPlanningExecutionService.plan_sion(
        sion, [license_id], persist=True, mode="NEW"
    )
    print(f"  write_results: {result_new.get('write_results')}")

    # Check INSIDE the transaction
    count_in_transaction = LicenseItemPlan.objects.filter(license_id=license_id).count()
    print(f"  Plans in DB (inside transaction): {count_in_transaction}")

print("  Transaction committed")

# Check AFTER the transaction
count_after_new = LicenseItemPlan.objects.filter(license_id=license_id).count()
print(f"  Plans in DB (after transaction): {count_after_new}")

# Show what's in the database
plans = LicenseItemPlan.objects.filter(license_id=license_id).order_by('pk')
for plan in plans:
    print(f"    - Import {plan.import_item_id}: {plan.planned_quantity} @ {plan.unit_price}")

# ALL Mode
print("\nStep 2: Execute ALL Mode")
with transaction.atomic():
    print("  Inside transaction...")
    result_all = SionPlanningExecutionService.plan_sion(
        sion, [license_id], persist=True, mode="ALL"
    )
    print(f"  write_results: {result_all.get('write_results')}")

    # Check INSIDE the transaction
    count_in_transaction = LicenseItemPlan.objects.filter(license_id=license_id).count()
    print(f"  Plans in DB (inside transaction): {count_in_transaction}")

print("  Transaction committed")

# Check AFTER the transaction
count_after_all = LicenseItemPlan.objects.filter(license_id=license_id).count()
print(f"  Plans in DB (after transaction): {count_after_all}")

# Show what's in the database
plans = LicenseItemPlan.objects.filter(license_id=license_id).order_by('pk')
for plan in plans:
    print(f"    - Import {plan.import_item_id}: {plan.planned_quantity} @ {plan.unit_price}")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"After NEW: {count_after_new} plans")
print(f"After ALL: {count_after_all} plans")

if count_after_all == count_after_new:
    print("\n✗ BUG CONFIRMED: ALL mode did not persist plans!")
    print(f"  NEW created {count_after_new} plans")
    print(f"  ALL should have recreated them, but count is still {count_after_all}")
else:
    print(f"\n✓ ALL mode persisted {count_after_all - count_after_new} new plans")
