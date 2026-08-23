"""Canonical operational quantities for plan/report consumers.

The persisted plan's ``import_item`` is only a representative anchor. A SION
rule may match several physical license import rows, so report totals must be
built from that complete source group rather than the representative row.
"""
from collections import defaultdict
from decimal import Decimal, ROUND_DOWN

from apps.license.models import LicenseImportItemsModel, LicenseItemPlan
from apps.license.services.planning_usage_reconciliation import reconcile_license_plans


ZERO = Decimal("0")


def _original_group_quantity(items) -> Decimal:
    total = sum((Decimal(item.quantity or 0) for item in items), ZERO)
    # Strategy Auto Plan treats a multi-row matched entitlement as whole kg.
    # A single physical license item retains its exact licensed 3dp quantity.
    return total.quantize(Decimal("1"), rounding=ROUND_DOWN) if len(items) > 1 else total


def planning_operational_snapshots(license_id: int, *, reconciliation=None) -> dict[int, dict]:
    """Return one auditable snapshot per persisted plan line."""
    plans = list(
        LicenseItemPlan.objects.filter(license_id=license_id)
        .select_related("item_name", "import_item")
        .order_by("id")
    )
    reconciliation = reconciliation or reconcile_license_plans(license_id)
    groups = defaultdict(list)
    for plan in plans:
        groups[plan.import_item_id].append(plan)

    result = {}
    for group_plans in groups.values():
        item_name_ids = {plan.item_name_id for plan in group_plans if plan.item_name_id}
        source_items = list(
            LicenseImportItemsModel.objects.filter(
                license_id=license_id, items__id__in=item_name_ids,
            ).distinct().order_by("serial_number", "id")
        ) if item_name_ids else [group_plans[0].import_item]
        original_total = _original_group_quantity(source_items)
        plan_data = [reconciliation["plans"][plan.id] for plan in group_plans]
        boe_qty = sum((row["boe_used_quantity"] for row in plan_data), ZERO)
        allotment_qty = sum((row["unlinked_allotment_quantity"] for row in plan_data), ZERO)
        balance_qty = original_total - boe_qty - allotment_qty
        plan_qty = sum((row["remaining_quantity"] for row in plan_data), ZERO)
        remaining_cif = sum((row["remaining_cif"] for row in plan_data), ZERO)
        snapshot = {
            "source_item_ids": [item.id for item in source_items],
            "original_total_qty": original_total,
            "boe_debited_qty": boe_qty,
            "unlinked_allotment_qty": allotment_qty,
            "balance_qty": balance_qty,
            "plan_qty": plan_qty,
            "remaining_cif": remaining_cif,
        }
        for plan in group_plans:
            result[plan.id] = snapshot
    return result
