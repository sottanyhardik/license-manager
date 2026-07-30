"""
License Overview — summary/header cards (`GET .../overview-summary/`).

Header fields + the 7-card numeric summary shown at the top of the new
"License Overview" dashboard's Overview tab. Deliberately additive and
read-only: reuses `apps.license.services.balance_snapshot.get_snapshot` for
every CIF figure (never re-sums `RowDetails`/`LicenseTradeLine` directly —
see that module's docstring for why a naive raw sum double-counts a SALE
trade's BOE via the legacy `trade.boes` M2M). The snapshot is itself a thin
composition over the exact same bulk `LicenseBalanceCalculator` calls
`calculate_all_components` used, so this produces numerically identical
figures — the point of the redirect is that every Balance-CIF consumer now
goes through the one shared snapshot entry point.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

from django.db.models import Count, DecimalField, Sum, Value
from django.db.models.functions import Coalesce

from apps.allotment.models import AllotmentItems
from apps.bill_of_entry.models import RowDetails, OTH_INVOICE_MARKER
from apps.core.constants import DEC_0
from apps.license.services import balance_snapshot
from apps.license.services.balance_calculator import quantize_2dp


def _synthesize_status(license_obj) -> str:
    """
    Licence status is not a stored enum — synthesized from `LicenseFlags`
    booleans (see `LicenseDetailsModel.is_expired`/`is_active` back-compat
    accessors). Expired takes priority over active/inactive.
    """
    if license_obj.is_expired:
        return "Expired"
    if license_obj.is_active:
        return "Active"
    return "Inactive"


def get_overview_counts(license_obj) -> Dict[str, Any]:
    """
    Returns a dict with license header fields plus a `summary` dict of the
    7 numeric overview cards.

    Query shape: O(1) regardless of item/BOE/allotment/plan count — the
    snapshot (allocation-aware — including the virtual `trade.boes` match
    netting inside the underlying `calculate_boe_debit_total_for_licenses`,
    see that module), 1 distinct-count query each for Total BOEs / Total
    Allotments, 1 `Coalesce(Sum(...))` aggregate for Total Planned CIF.
    """
    snapshot = balance_snapshot.get_snapshot(license_obj.id)
    # `calculate_all_components` used to quantize credit/debit/allotment to
    # 2dp individually for display (its `balance` was already quantized via
    # the shared credit-(debit+allotment) formula) — the snapshot's
    # license-level fields are the same underlying bulk-query totals but
    # left unquantized (matching other bulk consumers, e.g.
    # `license_balance_excel.py`), so quantize here to keep this endpoint's
    # numbers byte-identical to before the redirect.
    components = {
        "credit": quantize_2dp(snapshot["total_licence_cif"]),
        "debit": quantize_2dp(snapshot["debited_cif"]),
        "allotment": quantize_2dp(snapshot["outstanding_allotted_cif"]),
        "balance": snapshot["balance_cif"],  # Financial Ledger figure; already quantized by calculate_financial_balance
    }

    # NOTE: `.values("bill_of_entry").distinct().count()` looks correct but
    # isn't — `RowDetails.Meta.ordering = ["transaction_type",
    # "bill_of_entry__bill_of_entry_date"]` gets pulled into the implicit
    # SELECT DISTINCT by Django's ORM, so a BOE with rows of more than one
    # `transaction_type` (e.g. both DEBIT and CREDIT) was counted once per
    # transaction_type instead of once per BOE. `Count(..., distinct=True)`
    # as an aggregate doesn't have this problem (verified against real
    # licenses: the buggy form over-counted by exactly 1 in every case
    # checked, `Count(distinct=True)` matched the BOEs tab's actual row
    # count exactly).
    # Previous-owner "hidden" BOEs (see `OTH_INVOICE_MARKER`) are excluded
    # — they no longer count toward this licence's utilisation in ANY
    # balance/financial figure, and the overview card is no exception.
    total_boes = RowDetails.objects.filter(sr_number__license=license_obj).exclude(
        bill_of_entry__invoice_no=OTH_INVOICE_MARKER
    ).aggregate(
        n=Count("bill_of_entry", distinct=True)
    )["n"]
    # Only count allotments NOT already linked to a BOE — checked against the
    # REAL `BillOfEntryModel.allotment` M2M relationship, not the hand-
    # maintained `AllotmentModel.is_boe` cache boolean, which has been found
    # stale at real-world scale (allotments linked via the M2M with is_boe
    # still False — see `LicenseBalanceCalculator.get_allotment_rows`'s
    # docstring for the same fix applied to the Balance Engine/Customs
    # Ledger). `.distinct()` on the grouping column already makes this safe
    # against the one-row-per-linked-BOE join fan-out `isnull=True` doesn't
    # multiply rows for (a NULL match is always exactly one row), so no
    # `Exists()` is needed here. `AllotmentModel`/`AllotmentItems` have no
    # soft-delete field to additionally exclude.
    total_allotments = (
        AllotmentItems.objects.filter(item__license=license_obj, allotment__bill_of_entry__isnull=True)
        .values("allotment")
        .distinct()
        .count()
    )

    total_planned_cif = _total_planned_cif(license_obj)

    status = _synthesize_status(license_obj)
    importer = license_obj.exporter.name if license_obj.exporter_id else (license_obj.archived_exporter_name or None)

    return {
        "license_number": license_obj.license_number,
        "authorisation_number": license_obj.registration_number,
        "file_number": license_obj.file_number,
        "license_date": license_obj.license_date,
        "license_expiry_date": license_obj.license_expiry_date,
        "importer": importer,
        "status": status,
        # Purchase Status (`core.PurchaseStatus` FK, e.g. GE/MI/IP/SM/CO) —
        # editable in the UI via the existing generic `PATCH
        # /licenses/{id}/` endpoint (already a writable field on
        # `LicenseDetailsSerializer`, gated by the same `LICENSE_MANAGER`
        # write role as every other license field); this endpoint only
        # surfaces the current value for display, it never writes it.
        "purchase_status_id": license_obj.purchase_status_id,
        "purchase_status_code": license_obj.purchase_status.code if license_obj.purchase_status_id else None,
        "purchase_status_label": license_obj.purchase_status.label if license_obj.purchase_status_id else None,
        "summary": {
            "total_boes": total_boes,
            "total_allotments": total_allotments,
            "total_planned_cif": total_planned_cif,
            "total_cif": components["credit"],
            "total_debited_cif": components["debit"],
            "total_allotted_cif": components["allotment"],
            "total_balance_cif": components["balance"],
        },
    }


def _total_planned_cif(license_obj) -> Decimal:
    """
    Sum of `LicenseItemPlan.planned_cif_fc` across every Utilization
    Planning record on this license — one `Coalesce(Sum(...))` aggregate,
    O(1) regardless of item/plan-group count.

    Deliberately does NOT go through `plan_utilization.plan_utilization_rows`
    (which this module's Planning-tab endpoint uses): that function groups
    items, resolves HS codes/splits, and calls `plan_status_for` once per
    plan-group to diff against live-allotted baselines — all needed for the
    Planning tab's per-group breakdown, but pure overhead for a single
    license-level total, and measured to cost 5-47+ queries depending on
    item/plan-group count (a pre-existing characteristic of that shared
    function, also used by `LicenseDetailsViewSet.retrieve()` and the
    Balance Excel export — out of scope to change here). A direct aggregate
    is mathematically equivalent (`original_cif_fc` per group is itself
    just the sum of that group's `LicenseItemPlan.planned_cif_fc` rows, per
    `plan_enforcement.py`) and keeps this lightweight summary endpoint O(1).
    """
    from apps.license.models import LicenseItemPlan

    result = LicenseItemPlan.objects.filter(license=license_obj).aggregate(
        total=Coalesce(Sum("planned_cif_fc"), Value(DEC_0), output_field=DecimalField())
    )
    return result["total"]
