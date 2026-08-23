#!/usr/bin/env python
"""Debug why plan rows aren't persisting."""
import os, sys, django
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')
django.setup()

from apps.license.models import LicenseDetailsModel, LicenseItemPlan, SionPlanningRule
from apps.core.models import SionNormClassModel
from apps.license.services.sion_rule_engine import SionRulePlanningService
from django.db import transaction

print("="*80)
print("DEBUG: Persistence Issue")
print("="*80)

license_id = 2547
sion_id = 2

license_obj = LicenseDetailsModel.objects.get(pk=license_id)
sion = SionNormClassModel.objects.get(pk=sion_id)
rule = SionPlanningRule.objects.filter(sion_id=sion_id, is_active=True).first()

# Clear
LicenseItemPlan.objects.filter(license_id=license_id).delete()

print(f"\nLicense: {license_obj.license_number} ({license_id})")
print(f"SION: {sion.norm_class} ({sion_id})")
print(f"Rule: {rule.name} ({rule.pk})")

# Test using the OLD service method (not the generic execution service)
print("\n--- Using SionRulePlanningService.plan() ---")

try:
    result = SionRulePlanningService.plan(rule, [license_id])
    print(f"Result: {result}")

    count = LicenseItemPlan.objects.filter(license_id=license_id).count()
    print(f"\nPlans in DB after plan(): {count}")

    if count > 0:
        plans = LicenseItemPlan.objects.filter(license_id=license_id)
        for plan in plans[:3]:
            print(f"  - Import {plan.import_item_id}: Qty {plan.planned_quantity} @ {plan.unit_price}")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

# Now test the generic execution service
print("\n--- Using generic SionPlanningExecutionService ---")
from apps.license.services.sion_planning_execution import SionPlanningExecutionService

LicenseItemPlan.objects.filter(license_id=license_id).delete()

try:
    result = SionPlanningExecutionService.plan_sion(
        sion, [license_id], persist=True, mode="NEW"
    )
    print(f"Result write_results: {result.get('write_results')}")

    count = LicenseItemPlan.objects.filter(license_id=license_id).count()
    print(f"\nPlans in DB after plan_sion(): {count}")

    if count > 0:
        plans = LicenseItemPlan.objects.filter(license_id=license_id)
        for plan in plans[:3]:
            print(f"  - Import {plan.import_item_id}: Qty {plan.planned_quantity} @ {plan.unit_price}")
    else:
        print("NO ROWS PERSISTED!")
        print(f"But write_results says: {result.get('write_results')}")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
