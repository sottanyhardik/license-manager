"""
License Overview — BOEs tab (`GET .../overview-boes/`).

Must stay O(1) queries regardless of BOE count (licenses can have 1000+
BOEs) — exactly 2 queries:
  1. A single grouped aggregate over `RowDetails` (per `bill_of_entry_id`:
     summed cif_fc/qty, plus a per-row "remaining allotment-side CIF"
     annotation summed per BOE).
  2. `BillOfEntryModel.objects.filter(id__in=...).select_related(
     'company', 'port')` for header fields.

The "remaining CIF" figure reuses the EXACT allocation formula
`apps.reconciliation.services.allocation_service.remaining_for_row_details_
allotment_side` already applies per-row (row.cif_fc minus its ACTIVE/current
`BOEAllotmentAllocation` sum, floored at 0) — batched into a single
correlated subquery via the same `Subquery(OuterRef(...))` pattern already
used by `LicenseBalanceCalculator.get_allotment_rows`, rather than calling
`LicenseBalanceLedgerBuilder.build_boe_allotment_relationships` (which is
correct but issues one query per BOE debit row internally — fine for a
single-BOE drawer, but O(N) and unacceptable for a 1000+-row Overview tab
load). This is a batched restatement of the same math, not a third,
independent calculation.

No `duty_saved` field exists anywhere in `apps/bill_of_entry/models.py` —
omitted entirely rather than inventing a value.
"""
from __future__ import annotations

from typing import Any, Dict, List

from django.contrib.postgres.aggregates import BoolOr
from django.db.models import DecimalField, F, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce, Greatest

from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.core.constants import DEC_0, DEC_000

_ALLOC_FIELD = DecimalField(max_digits=20, decimal_places=3)


def list_boe_rows(license_obj) -> List[Dict[str, Any]]:
    from apps.reconciliation.models import BOEAllotmentAllocation

    allocated_subquery = (
        BOEAllotmentAllocation.objects.filter(
            row_details_id=OuterRef("pk"),
            status=BOEAllotmentAllocation.STATUS_ACTIVE,
            is_current=True,
        )
        .order_by()
        .values("row_details_id")
        .annotate(total=Sum("allocated_cif_fc"))
        .values("total")
    )

    grouped = (
        RowDetails.objects.filter(sr_number__license=license_obj)
        # Previous-owner "hidden" DEBIT rows (see `RowDetails.is_hidden`)
        # are excluded from this BOEs-tab summary — a hidden row never
        # contributes to this licence's utilisation in any balance/report
        # figure. Never excludes CREDIT rows (hide/restore only ever
        # touches DEBIT rows — see `boe_service.hide_boe_for_license`).
        .exclude(is_hidden=True)
        .annotate(
            allocated=Coalesce(
                Subquery(allocated_subquery, output_field=_ALLOC_FIELD),
                Value(DEC_0),
                output_field=_ALLOC_FIELD,
            )
        )
        .annotate(
            remaining_row=Greatest(
                F("cif_fc") - F("allocated"), Value(DEC_0), output_field=_ALLOC_FIELD
            )
        )
        .values("bill_of_entry_id")
        .annotate(
            cif_fc=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()),
            qty=Coalesce(Sum("qty"), Value(DEC_000), output_field=DecimalField()),
            remaining_cif=Coalesce(Sum("remaining_row"), Value(DEC_0), output_field=DecimalField()),
            any_frozen=BoolOr("is_frozen"),
            any_dispute=BoolOr("is_dispute"),
        )
    )

    by_boe_id: Dict[int, Dict[str, Any]] = {
        row["bill_of_entry_id"]: row for row in grouped if row["bill_of_entry_id"] is not None
    }
    if not by_boe_id:
        return []

    boes = (
        BillOfEntryModel.objects.filter(id__in=by_boe_id.keys())
        .select_related("company", "port")
    )

    rows: List[Dict[str, Any]] = []
    for boe in boes:
        agg = by_boe_id[boe.id]
        rows.append({
            "bill_of_entry_number": boe.bill_of_entry_number,
            "bill_of_entry_date": boe.bill_of_entry_date,
            "port": boe.port.name if boe.port_id else None,
            "supplier": boe.company.name if boe.company_id else None,
            "invoice_no": boe.invoice_no,
            "invoice_date": boe.invoice_date,
            "cif_fc": agg["cif_fc"],
            "status": _boe_status(agg),
        })
    return rows


def _boe_status(agg: Dict[str, Any]) -> str:
    """
    Synthesized status — no stored status field exists on `RowDetails`/
    `BillOfEntryModel`. Priority: Dispute > Frozen > remaining-CIF-driven.
    """
    if agg.get("any_dispute"):
        return "Dispute"
    if agg.get("any_frozen"):
        return "Frozen"
    if (agg.get("remaining_cif") or DEC_0) <= DEC_0:
        return "Reconciled"
    return "Pending"
