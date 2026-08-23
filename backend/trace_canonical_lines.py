#!/usr/bin/env python
"""Check what canonical_lines are computed in ALL mode."""
import os, sys, django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')
django.setup()

from apps.license.models import LicenseDetailsModel, LicenseItemPlan
from apps.core.models import SionNormClassModel
from apps.license.services.sion_planning_execution import SionPlanningExecutionService
from django.db import transaction

# Monkey-patch to trace
original_build = SionPlanningExecutionService.plan_sion

@classmethod
def traced_plan_sion(cls, sion, license_ids=None, **kwargs):
    persist = kwargs.get('persist', True)
    mode = kwargs.get('mode', 'NEW')

    print(f"\n>>> plan_sion called: persist={persist}, mode={mode}")

    # Call original but capture the state inside
    if persist:
        result = original_build(sion, license_ids, **kwargs)
        print(f"    write_results count: {len(result.get('write_results', []))}")
        for wr in result.get('write_results', []):
            print(f"      - {wr.get('status')}: lines_created={wr.get('allocation_summary', {}).get('lines_created', 0)}")
        return result
    else:
        return original_build(sion, license_ids, **kwargs)

SionPlanningExecutionService.plan_sion = traced_plan_sion

license_id = 2547
sion_id = 2

license_obj = LicenseDetailsModel.objects.get(pk=license_id)
sion = SionNormClassModel.objects.get(pk=sion_id)

# Clear and setup
LicenseItemPlan.objects.filter(license_id=license_id).delete()
print("="*80)
print("Step 1: NEW Mode")
print("="*80)

with transaction.atomic():
    result = SionPlanningExecutionService.plan_sion(
        sion, [license_id], persist=True, mode="NEW"
    )

print(f"Rows in DB: {LicenseItemPlan.objects.filter(license_id=license_id).count()}")

print("\n" + "="*80)
print("Step 2: ALL Mode")
print("="*80)

with transaction.atomic():
    result = SionPlanningExecutionService.plan_sion(
        sion, [license_id], persist=True, mode="ALL"
    )

print(f"Rows in DB: {LicenseItemPlan.objects.filter(license_id=license_id).count()}")
