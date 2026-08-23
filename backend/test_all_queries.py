#!/usr/bin/env python
"""Show ALL SQL queries in ALL mode."""
import os, sys, django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')
django.setup()

from apps.license.models import LicenseDetailsModel, LicenseItemPlan
from apps.core.models import SionNormClassModel
from apps.license.services.sion_planning_execution import SionPlanningExecutionService
from django.db import transaction, connection
from django.test.utils import CaptureQueriesContext

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
print("ALL MODE: Capturing ALL SQL queries")
print("="*80 + "\n")

with CaptureQueriesContext(connection) as context:
    with transaction.atomic():
        result = SionPlanningExecutionService.plan_sion(
            sion, [license_id], persist=True, mode="ALL"
        )

# Show only LicenseItemPlan queries
print("Queries related to LicenseItemPlan:")
for i, q in enumerate(context.captured_queries):
    sql = q['sql']
    if 'LicenseItemPlan' in sql or 'license_licenseitemplan' in sql:
        print(f"\n{i}. {sql[:150]}...")

print("\n" + "="*80)
print("Looking for DELETE + INSERT pattern:")
print("="*80)

delete_queries = [q for q in context.captured_queries if 'DELETE' in q['sql'] and 'license_licenseitemplan' in q['sql']]
insert_queries = [q for q in context.captured_queries if 'INSERT' in q['sql'] and 'license_licenseitemplan' in q['sql']]

print(f"DELETE queries: {len(delete_queries)}")
for q in delete_queries:
    print(f"  {q['sql']}")

print(f"\nINSERT queries: {len(insert_queries)}")
for q in insert_queries:
    print(f"  {q['sql'][:120]}...")

if len(delete_queries) > len(insert_queries):
    print(f"\n✗ BUG: {len(delete_queries)} DELETEs but only {len(insert_queries)} INSERTs!")
    print("The rows are being deleted but not restored!")
