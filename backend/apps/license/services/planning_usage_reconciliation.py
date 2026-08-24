"""Reconcile fixed theoretical plan lines with actual BOE/open-allotment usage.

This module is presentation-only: it never mutates ``LicenseItemPlan`` and it
does not participate in theoretical plan generation.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_DOWN

from apps.allotment.models import AllotmentItems
from apps.license.models import LicenseDetailsModel, LicenseItemPlan
from apps.license.services.planning_tolerances import (
    apply_remaining_plan_tolerance,
    effective_planning_balance_cif,
)


ZERO = Decimal("0")
CIF_QUANTUM = Decimal("0.01")
QTY_QUANTUM = Decimal("0.001")
def _usage_bucket():
    return {
        "boe_used_quantity": ZERO,
        "boe_used_cif": ZERO,
        "unlinked_allotment_quantity": ZERO,
        "unlinked_allotment_cif": ZERO,
    }


def reconcile_split_allocation(source_qty, theoretical_rows, utilization_by_item):
    """Reallocate one split group without changing its theoretical rows.

    Actual committed usage is a per-child minimum. Deficits are funded from
    unused theoretical allocation on sibling rows. Only committed usage above
    the parent source quantity produces group excess.
    """
    source_qty = Decimal(source_qty or 0)
    rows = [dict(row) for row in theoretical_rows]
    for row in rows:
        row["theoretical_qty"] = Decimal(row.get("theoretical_qty") or 0)
        row["committed_qty"] = Decimal(utilization_by_item.get(row["key"], 0) or 0)
        row["reconciled_qty"] = row["theoretical_qty"]

    for recipient in rows:
        needed = max(recipient["committed_qty"] - recipient["reconciled_qty"], ZERO)
        for donor in rows:
            if needed <= ZERO:
                break
            if donor["key"] == recipient["key"]:
                continue
            reducible = max(donor["reconciled_qty"] - donor["committed_qty"], ZERO)
            moved = min(needed, reducible)
            donor["reconciled_qty"] -= moved
            recipient["reconciled_qty"] += moved
            needed -= moved
        if needed > ZERO:
            spare = max(source_qty - sum((row["reconciled_qty"] for row in rows), ZERO), ZERO)
            added = min(needed, spare)
            recipient["reconciled_qty"] += added
            needed -= added
        if needed > ZERO:
            # Impossible to satisfy every actual commitment inside the parent
            # ceiling. Keep the operational plan capped; the unsatisfied
            # commitment is exposed as child/group excess for manual review.
            pass

    committed_total = sum((row["committed_qty"] for row in rows), ZERO)
    reconciled_total = sum((row["reconciled_qty"] for row in rows), ZERO)
    return {
        "rows": rows,
        "source_quantity": source_qty,
        "theoretical_total": sum((row["theoretical_qty"] for row in rows), ZERO),
        "committed_total": committed_total,
        "reconciled_total": reconciled_total,
        "group_excess_quantity": max(committed_total - source_qty, ZERO),
        "manual_review_required": committed_total > source_qty,
    }


def aggregate_license_usage(license_id: int) -> dict:
    """Return usage keyed by persisted source and canonical target identity.

    Product-name/family inference is deliberately forbidden.  Ambiguous
    history remains source-level and is surfaced, never silently assigned to
    a split target.
    """
    mapped = defaultdict(_usage_bucket)
    unmapped_by_source = defaultdict(_usage_bucket)
    unmapped = []

    # This is the licence-import-item boundary. Planning target mapping below
    # determines only child reconciliation; it cannot exclude a genuine BOE
    # debit from licence-level actual usage.
    from apps.license.models import LicenseDetailsModel
    from apps.license.services.item_usage import eligible_boe_debits_for_license
    license_obj = LicenseDetailsModel.objects.only("pk").get(pk=license_id)
    boe_rows = eligible_boe_debits_for_license(license_obj).select_related(
        "bill_of_entry__planning_target_item"
    )
    for row in boe_rows:
        boe = row.bill_of_entry
        if not boe or not boe.planning_target_item_id or boe.planning_mapping_status in {"INVALID_PERSISTED_TARGET", "UNMAPPED_AMBIGUOUS", "UNMAPPED_NO_TARGET"}:
            bucket = unmapped_by_source[row.sr_number_id]
            bucket["boe_used_quantity"] += row.qty or ZERO
            bucket["boe_used_cif"] += row.cif_fc or ZERO
            unmapped.append({
                "source": "BOE", "record_id": row.id,
                "record_number": row.bill_of_entry.bill_of_entry_number if row.bill_of_entry else None,
                "source_item_id": row.sr_number_id, "planning_target_item_id": None,
                "quantity": row.qty or ZERO, "cif_fc": row.cif_fc or ZERO,
                "mapping_status": boe.planning_mapping_status if boe else "UNMAPPED_AMBIGUOUS",
            })
            continue
        bucket = mapped[(row.sr_number_id, boe.planning_target_item_id)]
        bucket["boe_used_quantity"] += row.qty or ZERO
        bucket["boe_used_cif"] += row.cif_fc or ZERO

    allotment_rows = (
        AllotmentItems.objects.filter(
            item__license_id=license_id,
            allotment__bill_of_entry__isnull=True,
            allotment__is_boe=False,
            is_boe=False,
        )
        .select_related("allotment", "item", "allotment__planning_target_item")
        .distinct()
    )
    for row in allotment_rows:
        allotment = row.allotment
        if not allotment or not allotment.planning_target_item_id or allotment.planning_mapping_status in {"INVALID_PERSISTED_TARGET", "UNMAPPED_AMBIGUOUS", "UNMAPPED_NO_TARGET"}:
            bucket = unmapped_by_source[row.item_id]
            bucket["unlinked_allotment_quantity"] += row.qty or ZERO
            bucket["unlinked_allotment_cif"] += row.cif_fc or ZERO
            unmapped.append({
                "source": "ALLOTMENT", "record_id": row.id,
                "record_number": row.allotment.invoice if row.allotment else None,
                "source_item_id": row.item_id, "planning_target_item_id": None,
                "quantity": row.qty or ZERO, "cif_fc": row.cif_fc or ZERO,
                "mapping_status": allotment.planning_mapping_status if allotment else "UNMAPPED_AMBIGUOUS",
            })
            continue
        bucket = mapped[(row.item_id, allotment.planning_target_item_id)]
        bucket["unlinked_allotment_quantity"] += row.qty or ZERO
        bucket["unlinked_allotment_cif"] += row.cif_fc or ZERO

    return {"mapped": dict(mapped), "unmapped_by_source": dict(unmapped_by_source), "unmapped_usage": unmapped}


def apply_operational_cif_ceiling(rows, balance_cif):
    """Cap future plan rows to the license's effective financial balance.

    ``rows`` must already have passed usage reconciliation and remaining-qty
    tolerance. The deterministic order is planning-rule priority, then plan
    id. Historical BOE/allotment values are intentionally untouched.
    """
    # Strategy Auto Plan already persisted a single canonical operational CIF
    # allocation. Reapplying the unrelated live financial balance here would
    # omit valid capped rows (for example the final WPC waterfall row) from
    # reconciliation and reporting. Use the persisted run snapshot exactly.
    strategy_openings = [
        Decimal(str((plan.allocation_provenance or {}).get("opening_operational_cif")))
        for plan, _row in rows
        if (plan.allocation_provenance or {}).get("opening_operational_cif") is not None
        and (plan.allocation_provenance or {}).get("operational_planned_cif") is not None
    ]
    if strategy_openings:
        # A strategy run normally writes one common opening snapshot to every
        # child.  Some historical rows predate that invariant, however.  This
        # service is used by read-only serializers, so an inconsistent legacy
        # snapshot must not make the entire licence unviewable.  Do not rewrite
        # a persisted plan or substitute a live balance (either would change
        # the historical plan): use the smallest recorded opening as the
        # deterministic, fail-closed reporting ceiling instead.
        #
        # Callers that need to surface the data-quality issue can inspect the
        # reconciliation diagnostic returned by ``reconcile_license_plans``.
        return min(strategy_openings)

    effective_balance = effective_planning_balance_cif(balance_cif)
    # A negative financial balance is an excess/manual-review condition, not
    # negative future planning capacity.  It must never create a negative
    # remaining quantity while this service is limiting future work.
    capacity = max(effective_balance, ZERO)
    for plan, row in sorted(
        rows,
        key=lambda pair: (
            (getattr(pair[0].planning_rule, "priority", None) or Decimal("999999"))
            if pair[0].planning_rule_id else Decimal("999999"),
            pair[0].id,
        ),
    ):
        current_cif = row["remaining_cif"]
        current_qty = row["remaining_quantity"]
        row["pre_balance_remaining_quantity"] = current_qty
        row["pre_balance_remaining_cif"] = current_cif
        allowed_cif = min(current_cif, capacity)
        adjustment = current_cif - allowed_cif
        if adjustment > ZERO:
            if plan.unit_price and plan.unit_price > ZERO:
                adjusted_qty = (allowed_cif / plan.unit_price).quantize(QTY_QUANTUM, rounding=ROUND_DOWN)
                adjusted_cif = (adjusted_qty * plan.unit_price).quantize(CIF_QUANTUM, rounding=ROUND_DOWN)
            elif current_cif > ZERO:
                adjusted_qty = (current_qty * allowed_cif / current_cif).quantize(QTY_QUANTUM, rounding=ROUND_DOWN)
                adjusted_cif = allowed_cif.quantize(CIF_QUANTUM, rounding=ROUND_DOWN)
            else:
                adjusted_qty = current_qty
                adjusted_cif = ZERO
            row["remaining_quantity"], row["remaining_cif"] = apply_remaining_plan_tolerance(
                adjusted_qty, adjusted_cif,
            )
            row["balance_cif_adjustment"] = adjustment
            if row["remaining_quantity"] == ZERO and row["reconciliation_status"] != "MANUAL_PLANNING_REQUIRED":
                row["reconciliation_status"] = "FULLY_UTILIZED"
        else:
            row["balance_cif_adjustment"] = ZERO
        capacity -= row["remaining_cif"]
    return effective_balance


def reconcile_license_plans(license_id: int) -> dict:
    """Allocate family usage once across matching theoretical plan lines."""
    usage = aggregate_license_usage(license_id)
    plans = list(
        LicenseItemPlan.objects.filter(
            license_id=license_id,
            is_active=True,
            is_deleted=False,
            is_cancelled=False,
        )
        .select_related("item_name", "import_item", "planning_rule")
        .order_by("id")
    )
    by_plan_id = {}
    groups = defaultdict(list)
    for plan in plans:
        groups[plan.import_item_id].append(plan)
    group_results = {}
    for import_item_id, group_plans in groups.items():
        row_usage = {}
        usage_details = {}
        theoretical_rows = []
        for plan in group_plans:
            # A generated line may represent several source rows.  New
            # canonical plans retain that immutable source list in provenance;
            # legacy rows conservatively use their persisted anchor.
            source_ids = (plan.allocation_provenance or {}).get("source_item_ids") or [plan.import_item_id]
            available = _usage_bucket()
            for source_id in source_ids:
                values = usage["mapped"].get((int(source_id), plan.item_name_id), _usage_bucket())
                for key in available:
                    available[key] += values[key]
            committed = available["boe_used_quantity"] + available["unlinked_allotment_quantity"]
            row_usage[plan.id] = committed
            usage_details[plan.id] = (source_ids, available)
            theoretical_rows.append({"key": plan.id, "theoretical_qty": plan.planned_quantity or ZERO})

        # A split may be anchored to one representative import item while its
        # planner basis is the matched import *group* quantity. For a complete
        # percentage split, the persisted theoretical total is that canonical
        # source ceiling (and is what Auto Plan's 100% invariant guarantees).
        source_quantity = sum((row["theoretical_qty"] for row in theoretical_rows), ZERO)
        allocation = reconcile_split_allocation(source_quantity, theoretical_rows, row_usage)
        group_results[import_item_id] = allocation
        allocated_by_id = {row["key"]: row for row in allocation["rows"]}
        for plan in group_plans:
            source_ids, available = usage_details[plan.id]
            committed_qty = row_usage[plan.id]
            committed_cif = available["boe_used_cif"] + available["unlinked_allotment_cif"]
            reconciled_qty = allocated_by_id[plan.id]["reconciled_qty"]
            # Preserve the persisted theoretical CIF when quantity did not
            # move (important for STANDARD/manual rows whose CIF is not
            # necessarily expressed as quantity × unit_price). Re-priced CIF
            # is specific to utilization-driven split reallocation.
            residual_qty = max(reconciled_qty - committed_qty, ZERO)
            # Historical commitments keep their authoritative BOE/allotment
            # CIF. Only newly available residual quantity uses the configured
            # planning price.
            reconciled_cif = committed_cif + residual_qty * (plan.unit_price or ZERO)
            # With no utilization-driven reallocation, retain a persisted CIF
            # that may come from STANDARD/manual semantics rather than price.
            if committed_qty == ZERO and reconciled_qty == (plan.planned_quantity or ZERO):
                reconciled_cif = plan.planned_cif_fc or ZERO
            raw_remaining_qty = residual_qty
            raw_remaining_cif = max(reconciled_cif - committed_cif, ZERO)
            remaining_qty, remaining_cif = apply_remaining_plan_tolerance(
                raw_remaining_qty, raw_remaining_cif,
            )
            excess_qty = max(committed_qty - reconciled_qty, ZERO)
            excess_cif = max(committed_cif - reconciled_cif, ZERO)
            if allocation["manual_review_required"] or excess_qty > ZERO or excess_cif > ZERO:
                status = "MANUAL_PLANNING_REQUIRED"
            elif remaining_qty == ZERO:
                status = "FULLY_UTILIZED"
            elif committed_qty == ZERO and committed_cif == ZERO:
                status = "NOT_USED"
            else:
                status = "PARTIALLY_UTILIZED"
            by_plan_id[plan.id] = {
                **available,
                "planning_family": None,
                "planning_target_item_id": plan.item_name_id,
                "mapping_status": "MAPPED_EXPLICIT" if committed_qty else "NO_ACTUAL_USAGE",
                "unmapped_actual_quantity": sum((
                    usage["unmapped_by_source"].get(int(source_id), _usage_bucket())["boe_used_quantity"]
                    + usage["unmapped_by_source"].get(int(source_id), _usage_bucket())["unlinked_allotment_quantity"]
                    for source_id in source_ids
                ), ZERO),
                "unmapped_actual_cif": sum((
                    usage["unmapped_by_source"].get(int(source_id), _usage_bucket())["boe_used_cif"]
                    + usage["unmapped_by_source"].get(int(source_id), _usage_bucket())["unlinked_allotment_cif"]
                    for source_id in source_ids
                ), ZERO),
                "effective_used_quantity": committed_qty,
                "effective_used_cif": committed_cif,
                "percentage_theoretical_quantity": plan.planned_quantity or ZERO,
                "percentage_theoretical_cif": plan.planned_cif_fc or ZERO,
                "theoretical_quantity": reconciled_qty,
                "theoretical_cif": reconciled_cif,
                "reconciled_planned_quantity": reconciled_qty,
                "reconciled_planned_cif": reconciled_cif,
                "remaining_quantity": remaining_qty,
                "remaining_cif": remaining_cif,
                "raw_remaining_quantity": raw_remaining_qty,
                "raw_remaining_cif": raw_remaining_cif,
                "excess_quantity": excess_qty,
                "excess_cif": excess_cif,
                "reconciliation_status": status,
            }

    # Final operational quantity cap. A source import item's available
    # balance is shared by every plan target derived from it, so apply the
    # cap once in deterministic planning priority order rather than letting
    # each report independently clip a displayed grand total.
    quantity_capacity = {
        plan.import_item_id: max(Decimal(str(plan.import_item.available_quantity or 0)), ZERO)
        for plan in plans
    }
    for plan in sorted(
        plans,
        key=lambda value: (value.planning_rule_priority or 999999, value.pk),
    ):
        row = by_plan_id[plan.id]
        raw_qty = max(row["remaining_quantity"], ZERO)
        available_qty = quantity_capacity[plan.import_item_id]
        effective_qty = min(raw_qty, available_qty)
        row["raw_remaining_quantity"] = raw_qty
        row["available_balance_quantity"] = available_qty
        row["effective_remaining_quantity"] = effective_qty
        row["quantity_cap_applied"] = effective_qty < raw_qty
        if effective_qty < raw_qty:
            # Future CIF follows the quantity cap; historical committed CIF
            # is already represented separately above and is never rewritten.
            future_cif = row["remaining_cif"]
            effective_cif = (
                future_cif * effective_qty / raw_qty if raw_qty > ZERO else ZERO
            )
            row["remaining_quantity"] = effective_qty
            row["remaining_cif"] = effective_cif.quantize(CIF_QUANTUM)
        row["effective_remaining_cif"] = row["remaining_cif"]
        quantity_capacity[plan.import_item_id] = max(available_qty - effective_qty, ZERO)

    license_obj = LicenseDetailsModel.objects.get(pk=license_id)
    operational_snapshot_rows = [
        plan for plan in plans
        if (plan.allocation_provenance or {}).get("opening_operational_cif") is not None
        and (plan.allocation_provenance or {}).get("operational_planned_cif") is not None
    ]
    operational_snapshots = {
        Decimal(str(plan.allocation_provenance["opening_operational_cif"]))
        for plan in operational_snapshot_rows
    }
    effective_balance_cif = apply_operational_cif_ceiling(
        [(plan, by_plan_id[plan.id]) for plan in plans], license_obj.get_balance_cif,
    )
    # Presentation and persistence share the same gross-CIF cap.  Apply a
    # plan-specific CIF adjustment to percentage children only; quantities and
    # configured rule prices remain immutable.  This prevents a stale
    # "remaining CIF" from showing a theoretical Olive value after Food/PKO
    # have consumed the actual balance.
    from apps.license.models import LicenseExportItemModel
    from apps.license.services.percentage_group_solver import reduce_high_rate_first
    gross_cif = sum((Decimal(str(value or 0)) for value in LicenseExportItemModel.objects.filter(
        license_id=license_id
    ).values_list("cif_fc", flat=True)), ZERO)
    actual_cif = sum((bucket["boe_used_cif"] + bucket["unlinked_allotment_cif"] for bucket in usage["mapped"].values()), ZERO)
    actual_cif += sum((row["cif_fc"] for row in usage["unmapped_usage"]), ZERO)
    actual_balance_cif = max(gross_cif - actual_cif, ZERO)
    percentage_plans = [plan for plan in plans if (plan.allocation_provenance or {}).get("strategy") == "SPLIT_BY_PERCENT"]
    other_plan_cif = sum((Decimal(str(plan.planned_cif_fc or 0)) for plan in plans if plan not in percentage_plans), ZERO)
    if percentage_plans:
        adjustment = reduce_high_rate_first(
            prior_sequence_cif=other_plan_cif,
            actual_balance_cif=actual_balance_cif,
            members=[{
                "plan_id": plan.id, "unit_rate": plan.unit_price or ZERO,
                "new_planned_qty": plan.planned_quantity or ZERO,
                "new_planned_cif": plan.planned_cif_fc or ZERO,
                "member_sequence": plan.planning_rule_priority or 0,
            } for plan in percentage_plans],
        )
        for member in adjustment["members"]:
            row = by_plan_id[member["plan_id"]]
            row.update({
                "adjusted_planned_cif": member["new_planned_cif"],
                "effective_unit_price": member["effective_unit_price"],
                "cif_cap_adjustment": member["cif_cap_reduction_cif"],
                "adjustment_reason": member["adjustment_reason"],
            })
    return {
        "plans": by_plan_id,
        "groups": group_results,
        "unmapped_usage": usage["unmapped_usage"],
        "raw_balance_cif": license_obj.get_balance_cif,
        "effective_balance_cif": effective_balance_cif,
        "operational_snapshot_inconsistent": len(operational_snapshots) > 1,
    }
