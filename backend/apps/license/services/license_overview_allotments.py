"""
License Overview — Allotments tab (`GET .../overview-allotments/`).

3 queries total, regardless of allotment count:
  1. `AllotmentItems` grouped by `allotment_id`, summing `cif_fc`/`qty` —
     restricted to THIS license's items only (an `AllotmentModel` row could
     in principle carry items from more than one license; the totals shown
     here are this license's share of that allotment, consistent with the
     filter used to find the allotment in the first place).
  2. `AllotmentModel.objects.filter(id__in=...).select_related('company')`
     for header fields.
  3. Which of those allotment ids have >=1 real linked BOE (the
     `BillOfEntryModel.allotment` M2M) — for the "Linked to BOE" status,
     see `_allotment_status`.

(Deliberately avoids `AllotmentModel.objects.filter(...).annotate(Sum(...))`
directly on the reverse `allotment_details` relation — combined with the
`distinct()` a filter-then-annotate on the same reverse FK would need, that
pattern is a well-known Django JOIN-fan-out trap that silently inflates
sums. Two separate grouped queries side-step it entirely.)

Allotment Number is synthesized as `f"ALT-{allotment.id}"`, matching the
exact convention already used in
`license_balance_ledger_builder.py::build_boe_allotment_relationships`.
"""
from __future__ import annotations

from typing import Any, Dict, List

from django.db.models import DecimalField, Sum, Value

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.core.constants import DEC_0, DEC_000


def list_allotment_rows(license_obj) -> List[Dict[str, Any]]:
    grouped = (
        AllotmentItems.objects.filter(item__license=license_obj)
        .values("allotment_id")
        .annotate(
            cif_fc=Sum("cif_fc", output_field=DecimalField()),
            qty=Sum("qty", output_field=DecimalField()),
        )
    )
    by_allotment_id: Dict[int, Dict[str, Any]] = {
        row["allotment_id"]: row for row in grouped if row["allotment_id"] is not None
    }
    if not by_allotment_id:
        return []

    allotments = (
        AllotmentModel.objects.filter(id__in=by_allotment_id.keys())
        .select_related("company")
    )

    # Real linked-BOE check (the `BillOfEntryModel.allotment` M2M) rather
    # than `AllotmentModel.is_boe` — that hand-maintained cache boolean has
    # been found stale at real-world scale (allotments linked via the M2M
    # with `is_boe` still False), which would show a BOE-linked allotment
    # as "Pending" here while the Customs Ledger correctly no longer treats
    # it as an outstanding commitment — see `LicenseBalanceCalculator.
    # get_allotment_rows`'s docstring for the identical fix there. One extra
    # batched query, not one per allotment.
    linked_allotment_ids = set(
        AllotmentModel.objects.filter(id__in=by_allotment_id.keys(), bill_of_entry__isnull=False)
        .values_list("id", flat=True)
        .distinct()
    )

    rows: List[Dict[str, Any]] = []
    for allotment in allotments:
        agg = by_allotment_id[allotment.id]
        rows.append({
            "allotment_number": f"ALT-{allotment.id}",
            "date": allotment.estimated_arrival_date,
            "customer": allotment.company.name if allotment.company_id else None,
            "product": allotment.item_name,
            "quantity": agg["qty"] or DEC_000,
            "cif_fc": agg["cif_fc"] or DEC_0,
            "status": _allotment_status(allotment, is_linked_to_boe=allotment.id in linked_allotment_ids),
        })
    return rows


def _allotment_status(allotment: AllotmentModel, is_linked_to_boe: bool) -> str:
    """
    Synthesized status — no stored status field exists on `AllotmentModel`.
    Priority: BOE-linked > Approved > Allotted > Pending.

    Note: `is_allotted` is set to True automatically by a signal
    (`apps.allotment.signals.update_is_allotted_on_save`) the moment an
    `AllotmentModel` gets its first `AllotmentItems` row — which is also
    the precondition for that allotment appearing in this list at all.
    So `is_allotted` is checked AFTER `is_approved` (not before), or
    "Approved" would be unreachable for every row this endpoint ever
    returns.
    """
    if is_linked_to_boe:
        return "Linked to BOE"
    if allotment.is_approved:
        return "Approved"
    if allotment.is_allotted:
        return "Allotted"
    return "Pending"
