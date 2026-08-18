"""Reconcile fixed theoretical plan lines with actual BOE/open-allotment usage.

This module is presentation-only: it never mutates ``LicenseItemPlan`` and it
does not participate in theoretical plan generation.
"""
from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal

from apps.allotment.models import AllotmentItems
from apps.bill_of_entry.models import RowDetails, annotate_and_exclude_hidden
from apps.core.constants import DEBIT
from apps.license.models import LicenseItemPlan


ZERO = Decimal("0")
FAMILY_ALIASES = {
    "PKO": frozenset({"PKO", "PALM KERNEL OIL", "PALM KERNEL"}),
    "OLIVE_OIL": frozenset({"OLIVE OIL"}),
    "CHEESE": frozenset({"CHEESE", "CREAM", "BUTTER"}),
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


def reconcile_license_plans(license_id: int) -> dict:
    """Allocate family usage once across matching theoretical plan lines."""
    usage = aggregate_license_usage(license_id)
    plans = list(
        LicenseItemPlan.objects.filter(license_id=license_id)
        .select_related("item_name")
        .order_by("id")
    )
    family_remaining = {}
    for family, values in usage["families"].items():
        family_remaining[family] = dict(values)

    by_plan_id = {}
    for plan in plans:
        family = normalize_planning_family(plan.item_name.name if plan.item_name_id else None)
        available = family_remaining.get(family, _usage_bucket()) if family else _usage_bucket()
        planned_qty = plan.planned_quantity or ZERO
        planned_cif = plan.planned_cif_fc or ZERO

        # A family should normally have one plan row. Sequential allocation is
        # deterministic and prevents duplicated usage if historical data has
        # multiple rows for the same family.
        effective_qty = available["boe_used_quantity"] + available["unlinked_allotment_quantity"]
        effective_cif = available["boe_used_cif"] + available["unlinked_allotment_cif"]
        remaining_qty = max(planned_qty - effective_qty, ZERO)
        remaining_cif = max(planned_cif - effective_cif, ZERO)
        excess_qty = max(effective_qty - planned_qty, ZERO)
        excess_cif = max(effective_cif - planned_cif, ZERO)
        if effective_qty == ZERO and effective_cif == ZERO:
            status = "NOT_USED"
        elif excess_qty > ZERO or excess_cif > ZERO:
            status = "MANUAL_PLANNING_REQUIRED"
        elif remaining_qty == ZERO and remaining_cif == ZERO:
            status = "FULLY_UTILIZED"
        else:
            status = "PARTIALLY_UTILIZED"

        by_plan_id[plan.id] = {
            "planning_family": family,
            **available,
            "effective_used_quantity": effective_qty,
            "effective_used_cif": effective_cif,
            "remaining_quantity": remaining_qty,
            "remaining_cif": remaining_cif,
            "excess_quantity": excess_qty,
            "excess_cif": excess_cif,
            "reconciliation_status": status,
        }
        if family in family_remaining:
            family_remaining[family] = _usage_bucket()

    return {"plans": by_plan_id, "unmapped_usage": usage["unmapped_usage"]}
