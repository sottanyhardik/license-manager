#!/usr/bin/env python
"""Show query sequence around DELETE/INSERT."""
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
print("Query sequence around DELETE/INSERT")
print("="*80 + "\n")

with CaptureQueriesContext(connection) as context:
    with transaction.atomic():
        result = SionPlanningExecutionService.plan_sion(
            sion, [license_id], persist=True, mode="ALL"
        )

# Find DELETE and INSERT indices
delete_idx = None
insert_idx = None

for i, q in enumerate(context.captured_queries):
    sql = q['sql']
    if 'DELETE' in sql and 'license_licenseitemplan' in sql:
        delete_idx = i
    if 'INSERT' in sql and 'license_licenseitemplan' in sql:
        insert_idx = i

if delete_idx is not None and insert_idx is not None:
    print(f"DELETE at query {delete_idx}")
    print(f"INSERT at query {insert_idx}")
    print(f"Queries between: {insert_idx - delete_idx - 1}\n")

    print("Showing queries from DELETE to INSERT (queries 47-57):\n")
    for i in range(max(0, delete_idx - 2), min(len(context.captured_queries), insert_idx + 3)):
        q = context.captured_queries[i]
        sql = q['sql']
        is_delete = 'DELETE' in sql and 'license_licenseitemplan' in sql
        is_insert = 'INSERT' in sql and 'license_licenseitemplan' in sql

        marker = ""
        if is_delete:
            marker = "  ← DELETE"
        elif is_insert:
            marker = "  ← INSERT"

        print(f"{i:2}. {sql[:100]:<100} {marker}")

else:
    print("DELETE or INSERT not found!")

# Final check
count = LicenseItemPlan.objects.filter(license_id=license_id).count()
print(f"\nFinal count in DB: {count}")
