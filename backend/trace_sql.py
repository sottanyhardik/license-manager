#!/usr/bin/env python
"""Trace SQL operations during ALL mode execution."""
import os, sys, django
from decimal import Decimal
from django.db import transaction, connection
from django.test.utils import CaptureQueriesContext

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

# Clear and create one plan
print("Setup: Clear and create initial plan")
LicenseItemPlan.objects.filter(license_id=license_id).delete()
with transaction.atomic():
    SionPlanningExecutionService.plan_sion(
        sion, [license_id], persist=True, mode="NEW"
    )

count_before = LicenseItemPlan.objects.filter(license_id=license_id).count()
print(f"Plans after NEW: {count_before}")

# Now capture SQL during ALL mode
print("\n" + "="*80)
print("ALL Mode - Capturing SQL")
print("="*80 + "\n")

with CaptureQueriesContext(connection) as context:
    with transaction.atomic():
        result = SionPlanningExecutionService.plan_sion(
            sion, [license_id], persist=True, mode="ALL"
        )

# Show relevant queries
delete_queries = [q for q in context.captured_queries if 'DELETE' in q['sql']]
insert_queries = [q for q in context.captured_queries if 'INSERT' in q['sql'] and 'LicenseItemPlan' in q['sql']]
select_queries = [q for q in context.captured_queries if 'SELECT' in q['sql'] and 'LicenseItemPlan' in q['sql']]

print(f"Total queries: {len(context.captured_queries)}")
print(f"DELETE queries: {len(delete_queries)}")
print(f"INSERT LicenseItemPlan: {len(insert_queries)}")
print(f"SELECT LicenseItemPlan: {len(select_queries)}")

if delete_queries:
    print("\nDELETE queries:")
    for q in delete_queries:
        print(f"  {q['sql'][:100]}...")

if insert_queries:
    print("\nINSERT queries:")
    for q in insert_queries:
        print(f"  {q['sql'][:150]}...")

# Check database state
count_after = LicenseItemPlan.objects.filter(license_id=license_id).count()
print(f"\nPlans before ALL: {count_before}")
print(f"Plans after ALL: {count_after}")

if count_after == count_before:
    print("\n✗ BUG: No change despite successful response!")
    print(f"  write_results says: {result.get('write_results')}")
