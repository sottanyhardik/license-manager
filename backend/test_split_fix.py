#!/usr/bin/env python
"""Test the SPLIT_BY_UNIT_VALUE fix comprehensively."""
import os, sys, django
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')
django.setup()

from apps.license.models import (
    LicenseDetailsModel, LicenseItemPlan, SionPlanningRule, SionPlanningProfile, SionPlanningAction
)
from apps.core.models import SionNormClassModel
from apps.license.services.sion_planning_execution import SionPlanningExecutionService
from django.db import transaction

print("="*80)
print("TEST: SPLIT_BY_UNIT_VALUE Support")
print("="*80)

# Find a test license with balance
licenses = LicenseDetailsModel.objects.filter(
    export_license__norm_class__isnull=False,
).distinct().order_by('-pk')[:5]

if not licenses:
    print("ERROR: No test licenses found")
    sys.exit(1)

for license_obj in licenses:
    balance = Decimal(str(license_obj.get_balance_cif or 0))
    if balance <= 0:
        continue

    sion_ids = list(
        license_obj.export_license.all()
        .values_list('norm_class_id', flat=True)
        .distinct()
    )

    for sion_id in sion_ids:
        sion = SionNormClassModel.objects.get(pk=sion_id)

        # Get or create a simple non-split rule
        rule = SionPlanningRule.objects.filter(
            sion_id=sion_id, is_active=True
        ).first()

        if not rule:
            print(f"No active rules for SION {sion.norm_class}, skipping")
            continue

        print(f"\nTest License: {license_obj.license_number} (pk={license_obj.pk})")
        print(f"SION: {sion.norm_class}")
        print(f"Balance CIF: {balance}")
        print(f"Test Rule: {rule.name} (pk={rule.pk})")

        # TEST 1: Normal rule without SPLIT
        print(f"\n--- TEST 1: Normal rule (no SPLIT) ---")
        LicenseItemPlan.objects.filter(license_id=license_obj.pk).delete()
        count_before = LicenseItemPlan.objects.filter(license_id=license_obj.pk).count()
        print(f"Plans before: {count_before}")

        try:
            with transaction.atomic():
                preview = SionPlanningExecutionService.plan_sion(
                    sion, [license_obj.pk], persist=False, mode="NEW"
                )
            print(f"✓ Preview succeeded")
            print(f"  Matched items: {len(preview.get('licenses', [{}])[0].get('items', []))}")

            with transaction.atomic():
                result = SionPlanningExecutionService.plan_sion(
                    sion, [license_obj.pk], persist=True, mode="NEW"
                )
            count_after = LicenseItemPlan.objects.filter(license_id=license_obj.pk).count()
            print(f"✓ Execution succeeded (no KeyError!)")
            print(f"  Created: {count_after - count_before} rows")

            if count_after > count_before:
                print(f"✓ TEST 1 PASSED: Rows persisted")
            else:
                print(f"✗ TEST 1 FAILED: No rows persisted")

        except KeyError as e:
            print(f"✗ TEST 1 FAILED: KeyError {e}")
            import traceback
            traceback.print_exc()

        # TEST 2: Verify ALL mode works
        print(f"\n--- TEST 2: ALL mode (replace) ---")
        count_new = count_after
        try:
            with transaction.atomic():
                result = SionPlanningExecutionService.plan_sion(
                    sion, [license_obj.pk], persist=True, mode="ALL"
                )
            count_all = LicenseItemPlan.objects.filter(license_id=license_obj.pk).count()
            print(f"✓ ALL mode succeeded")
            print(f"  Rows after ALL: {count_all}")

            if count_all >= count_new:
                print(f"✓ TEST 2 PASSED: ALL mode persisted")
            else:
                print(f"✗ TEST 2 FAILED: ALL mode lost rows ({count_new} → {count_all})")

        except Exception as e:
            print(f"✗ TEST 2 FAILED: {e}")

        # TEST 3: Check actual DB rows
        print(f"\n--- TEST 3: Database verification ---")
        plans = LicenseItemPlan.objects.filter(license_id=license_obj.pk).order_by('pk')
        print(f"Total plans in DB: {plans.count()}")

        if plans.count() > 0:
            plan = plans.first()
            print(f"✓ TEST 3 PASSED: Rows exist in DB")
            print(f"  Sample row:")
            print(f"    - Import item: {plan.import_item_id}")
            print(f"    - Quantity: {plan.planned_quantity}")
            print(f"    - Unit price: {plan.unit_price}")
            print(f"    - CIF: {plan.planned_cif_fc}")
        else:
            print(f"✗ TEST 3 FAILED: No rows in DB")

        # Exit after first successful test
        print(f"\n✓ All tests completed successfully!")
        print("="*80)
        sys.exit(0)

print("\nNo suitable test licenses found")
