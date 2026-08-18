"""Reconcile fixed theoretical plan lines with actual BOE/open-allotment usage.

This module is presentation-only: it never mutates ``LicenseItemPlan`` and it
does not participate in theoretical plan generation.
"""
from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal, ROUND_DOWN

from apps.allotment.models import AllotmentItems
from apps.bill_of_entry.models import RowDetails, annotate_and_exclude_hidden
from apps.core.constants import DEBIT
from apps.license.models import LicenseDetailsModel, LicenseItemPlan
from apps.license.services.planning_tolerances import (
    apply_remaining_plan_tolerance,
    effective_planning_balance_cif,
)


ZERO = Decimal("0")
CIF_QUANTUM = Decimal("0.01")
QTY_QUANTUM = Decimal("0.001")
FAMILY_ALIASES = {
    "PKO": frozenset({"PKO", "PALM KERNEL OIL", "PALM KERNEL"}),
    "OLIVE_OIL": frozenset({"OLIVE OIL", "OLIVE"}),
    "CHEESE": frozenset({"CHEESE", "CREAM", "BUTTER"}),
    "FOOD_FLAVOUR": frozenset({"FOOD FLAVOUR", "FOOD FLAVOR"}),
}
_SION_SUFFIX = re.compile(r"\s*[-–—]\s*[A-Z]+\s*\d+[A-Z0-9]*\s*$", re.IGNORECASE)


def normalize_product_name(value: str | None) -> str:
    """Uppercase/collapse whitespace and remove a terminal SION code."""
    normalized = " ".join((value or "").strip().split()).upper()
    return _SION_SUFFIX.sub("", normalized).strip()


def normalize_planning_family(value: str | None) -> str | None:
    normalized = normalize_product_name(value)
    for family, aliases in FAMILY_ALIASES.items():
        if normalized in aliases:
            return family
    return None


def _family_from_names(names) -> str | None:
    families = {family for name in names if (family := normalize_planning_family(name))}
    return next(iter(families)) if len(families) == 1 else None


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
    """Return family totals and explicit diagnostics for unmapped usage rows."""
    totals = defaultdict(_usage_bucket)
    unmapped = []

    boe_rows = annotate_and_exclude_hidden(
        RowDetails.objects.filter(sr_number__license_id=license_id, transaction_type=DEBIT),
        boe_field="bill_of_entry",
    ).select_related("bill_of_entry", "sr_number").prefetch_related("sr_number__items")
    for row in boe_rows:
        master_names = [item.name for item in row.sr_number.items.all()]
        transaction_product = row.bill_of_entry.product_name if row.bill_of_entry else ""
        family = normalize_planning_family(transaction_product) or _family_from_names(master_names)
        product = transaction_product or " / ".join(master_names)
        if not family:
            unmapped.append({
                "source": "BOE", "record_id": row.id,
                "record_number": row.bill_of_entry.bill_of_entry_number if row.bill_of_entry else None,
                "product_name": product, "quantity": row.qty or ZERO,
                "cif_fc": row.cif_fc or ZERO,
            })
            continue
        totals[family]["boe_used_quantity"] += row.qty or ZERO
        totals[family]["boe_used_cif"] += row.cif_fc or ZERO

    allotment_rows = (
        AllotmentItems.objects.filter(
            item__license_id=license_id,
            allotment__bill_of_entry__isnull=True,
            allotment__is_boe=False,
            is_boe=False,
        )
        .select_related("allotment", "item")
        .prefetch_related("item__items")
        .distinct()
    )
    for row in allotment_rows:
        master_names = [item.name for item in row.item.items.all()] if row.item_id else []
        transaction_product = row.allotment.item_name if row.allotment else ""
        family = normalize_planning_family(transaction_product) or _family_from_names(master_names)
        product = transaction_product or " / ".join(master_names)
        if not family:
            unmapped.append({
                "source": "ALLOTMENT", "record_id": row.id,
                "record_number": row.allotment.invoice if row.allotment else None,
                "product_name": product, "quantity": row.qty or ZERO,
                "cif_fc": row.cif_fc or ZERO,
            })
            continue
        totals[family]["unlinked_allotment_quantity"] += row.qty or ZERO
        totals[family]["unlinked_allotment_cif"] += row.cif_fc or ZERO

    return {"families": dict(totals), "unmapped_usage": unmapped}


def apply_operational_cif_ceiling(rows, balance_cif):
    """Cap future plan rows to the license's effective financial balance.

    ``rows`` must already have passed usage reconciliation and remaining-qty
    tolerance. The deterministic order is planning-rule priority, then plan
    id. Historical BOE/allotment values are intentionally untouched.
    """
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
        LicenseItemPlan.objects.filter(license_id=license_id)
        .select_related("item_name", "import_item", "planning_rule")
        .order_by("id")
    )
    family_remaining = {family: dict(values) for family, values in usage["families"].items()}
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
            family = normalize_planning_family(plan.item_name.name if plan.item_name_id else None)
            available = family_remaining.get(family, _usage_bucket()) if family else _usage_bucket()
            committed = available["boe_used_quantity"] + available["unlinked_allotment_quantity"]
            row_usage[plan.id] = committed
            usage_details[plan.id] = (family, available)
            theoretical_rows.append({"key": plan.id, "theoretical_qty": plan.planned_quantity or ZERO})
            if family in family_remaining:
                family_remaining[family] = _usage_bucket()

        # A split may be anchored to one representative import item while its
        # planner basis is the matched import *group* quantity. For a complete
        # percentage split, the persisted theoretical total is that canonical
        # source ceiling (and is what Auto Plan's 100% invariant guarantees).
        source_quantity = sum((row["theoretical_qty"] for row in theoretical_rows), ZERO)
        allocation = reconcile_split_allocation(source_quantity, theoretical_rows, row_usage)
        group_results[import_item_id] = allocation
        allocated_by_id = {row["key"]: row for row in allocation["rows"]}
        for plan in group_plans:
            family, available = usage_details[plan.id]
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
                "planning_family": family, **available,
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

    license_obj = LicenseDetailsModel.objects.get(pk=license_id)
    effective_balance_cif = apply_operational_cif_ceiling(
        [(plan, by_plan_id[plan.id]) for plan in plans], license_obj.get_balance_cif,
    )
    return {
        "plans": by_plan_id,
        "groups": group_results,
        "unmapped_usage": usage["unmapped_usage"],
        "raw_balance_cif": license_obj.get_balance_cif,
        "effective_balance_cif": effective_balance_cif,
    }
