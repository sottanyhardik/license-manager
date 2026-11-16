#!/usr/bin/env python
"""Comprehensive trace of persistence bug for Plan New / Force Re-plan."""
import os, sys, django
from decimal import Decimal
from django.db import transaction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')
django.setup()

from apps.license.models import LicenseDetailsModel, LicenseItemPlan
from apps.core.models import SionNormClassModel
from apps.license.services.sion_planning_execution import SionPlanningExecutionService

def trace_execution(license_id, sion_id, mode):
    """Trace one execution from preview through persistence."""

    print(f"\n{'='*80}")
    print(f"TRACE: License {license_id} | SION {sion_id} | Mode {mode}")
    print(f"{'='*80}")

    # Setup
    license_obj = LicenseDetailsModel.objects.filter(pk=license_id).first()
    if not license_obj:
        print(f"ERROR: License {license_id} not found")
        return

    try:
        sion = SionNormClassModel.objects.get(pk=sion_id)
    except SionNormClassModel.DoesNotExist:
        print(f"ERROR: SION {sion_id} not found")
        return

    print(f"\n1. REQUEST VALIDATION")
    print(f"   License: {license_obj.license_number} (pk={license_id})")
    print(f"   SION: {sion.norm_class} (pk={sion_id})")
    print(f"   Mode: {mode}")
    print(f"   Exporter: {license_obj.exporter.iec if license_obj.exporter else 'None'}")

    balance_cif = Decimal(str(license_obj.get_balance_cif or 0))
    print(f"   Balance CIF: {balance_cif}")

    # Count existing plans
    existing_count_before = LicenseItemPlan.objects.filter(license_id=license_id).count()
    print(f"   Existing plans before: {existing_count_before}")

    # Test PREVIEW
    print(f"\n2. PREVIEW (persist=False, mode={mode})")
    try:
        preview_result = SionPlanningExecutionService.plan_sion(
            sion, [license_id], persist=False, mode=mode
        )
        print(f"   Status: SUCCESS")
        print(f"   Rules executed: {len(preview_result.get('rules_executed', preview_result.get('rules_processed', [])))}")

        matched_count = 0
        proposed_count = 0
        for lic in preview_result.get('licenses', []):
            if lic['license_id'] == license_id:
                matched_count = lic.get('matched_item_count', 0)
                proposed_count = lic.get('proposed_plan', {}).get('item_count', 0)
                print(f"   Matched items: {matched_count}")
                print(f"   Proposed plan items: {proposed_count}")

                # Show proposed items
                if lic.get('items'):
                    print(f"   Proposed details:")
                    for item in lic.get('items', [])[:3]:
                        print(f"     - Import {item['import_item_id']}: {item.get('execution_output', 'N/A')}")
                        print(f"       Qty: {item.get('proposed_planned_quantity')}, Price: {item.get('proposed_unit_price')}")
                break

    except Exception as e:
        print(f"   Status: ERROR - {e}")
        import traceback
        traceback.print_exc()
        return

    # Test EXECUTION (persist=True)
    print(f"\n3. EXECUTION (persist=True, mode={mode})")
    try:
        print(f"   Calling SionPlanningExecutionService.plan_sion() with persist=True...")

        with transaction.atomic():
            exec_result = SionPlanningExecutionService.plan_sion(
                sion, [license_id], persist=True, mode=mode
            )
        print(f"   Status: SUCCESS (transaction committed)")
        print(f"   Rules executed: {len(exec_result.get('rules_executed', []))}")

        # Check write results
        write_results = exec_result.get('write_results', [])
        print(f"   Write results count: {len(write_results)}")
        for wr in write_results:
            print(f"     - License {wr.get('license_id')}: {wr.get('status', 'UNKNOWN')}")
            if wr.get('status') == 'PLANNED':
                print(f"       Plan ID: {wr.get('plan_id')}")
                allocated = wr.get('allocated_items', [])
                print(f"       Allocated items: {len(allocated)}")
                summary = wr.get('allocation_summary', {})
                print(f"       Lines created: {summary.get('lines_created', 0)}")
                print(f"       Consumed CIF: {summary.get('consumed_cif', 0)}")

    except Exception as e:
        print(f"   Status: ERROR - {e}")
        import traceback
        traceback.print_exc()
        return

    # Verify database state
    print(f"\n4. DATABASE VERIFICATION")
    existing_count_after = LicenseItemPlan.objects.filter(license_id=license_id).count()
    print(f"   Plans before execution: {existing_count_before}")
    print(f"   Plans after execution:  {existing_count_after}")
    print(f"   Plans created: {existing_count_after - existing_count_before}")

    if existing_count_after > existing_count_before:
        print(f"   ✓ ROWS PERSISTED")
        # Show the persisted rows
        plans = LicenseItemPlan.objects.filter(license_id=license_id).order_by('-created_on')[:5]
        for plan in plans:
            item_name = plan.item_name.name if plan.item_name else "None"
            print(f"     - Import {plan.import_item_id}: Qty {plan.planned_quantity}, Price {plan.unit_price}")
            print(f"       Item name: {item_name}, Rule: {plan.planning_rule_id}")
    else:
        print(f"   ✗ NO ROWS PERSISTED - BUG CONFIRMED!")

        # Check if the preview had items
        if matched_count > 0 and proposed_count > 0:
            print(f"   BUT: Preview showed {proposed_count} proposed items!")
            print(f"   PROBLEM: Execution computed {proposed_count} rows but didn't persist them!")

    print(f"\n{'='*80}")

# Main
if __name__ == "__main__":
    # Use the specific test license we found
    license_id = 2547
    sion_id = 2

    # Test both NEW and ALL modes
    for mode in ['NEW', 'ALL']:
        trace_execution(license_id, sion_id, mode)
