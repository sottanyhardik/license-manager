"""
License Overview — per-item ledger rows (`GET .../overview-items/`).

IMPORTANT — this module computes a NEW, display-only balance formula:

    balance_qty = total_qty - debited_qty - allotted_qty
    balance_cif = total_cif - debited_cif - allotted_cif

using each `LicenseImportItemsModel` row's own stored
`debited_quantity`/`debited_value`/`allotted_quantity`/`allotted_value`
fields directly (single query, no per-row lookups). This is deliberately
DISTINCT from the existing, license-level-shared `available_value`/
`available_quantity` computed by `apps/core/scripts/calculate_balance.py`
(which has its own serial_number==1 special case and pool-sharing rules —
see that module). The two numbers are allowed to differ for the same item;
this is intentional, not a bug to reconcile. This module must NOT call or
modify anything in `calculate_balance.py`.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List

from apps.core.constants import DEC_0, DEC_000
from apps.license.models import LicenseImportItemsModel


def compute_item_ledger_rows(license_obj, *, include_canonical: bool = False):
    """One dict per `LicenseImportItemsModel` row on this license. Single
    query (`select_related('hs_code')`); all arithmetic is pure Python over
    already-stored fields."""
    items = LicenseImportItemsModel.objects.filter(license=license_obj).select_related("hs_code")

    rows: List[Dict[str, Any]] = []
    for item in items:
        total_qty = item.quantity or DEC_000
        total_cif = item.cif_fc or DEC_0
        debited_qty = item.debited_quantity or DEC_000
        debited_cif = item.debited_value or DEC_0
        allotted_qty = item.allotted_quantity or DEC_000
        allotted_cif = item.allotted_value or DEC_0

        balance_qty = total_qty - debited_qty - allotted_qty
        balance_cif = total_cif - debited_cif - allotted_cif

        row = {
            "id": item.id,
            "description": item.description,
            "hs_code": item.hs_code.hs_code if item.hs_code_id else None,
            "unit": item.unit,
            "total_qty": total_qty,
            "total_cif": total_cif,
            "debited_qty": debited_qty,
            "debited_cif": debited_cif,
            "allotted_qty": allotted_qty,
            "allotted_cif": allotted_cif,
            "balance_qty": balance_qty,
            "balance_cif": balance_cif,
        }
        if include_canonical:
            # Do not replace the deployed fields above.  The selector's
            # legacy input is the exact existing overview calculation; only
            # a literal True can substitute the import-item balance.
            from apps.license.services.effective_cif_mode import project_effective_item_cif
            projection = project_effective_item_cif(
                licence=license_obj,
                item=item,
                legacy_row_balance=balance_cif,
            )
            row.update({
                "individual_item_cif_override": projection.raw_override,
                "individual_item_cif": projection.raw_override is True,
                "effective_cif_mode": projection.effective_mode,
                "legacy_balance_cif": projection.legacy_row_balance,
                "license_balance_cif": projection.license_balance_cif,
                "individual_item_balance_cif": projection.individual_item_balance,
                "effective_balance_cif": projection.effective_row_balance,
                "balance_cif_source": projection.balance_source,
                "cif_diagnostics": projection.diagnostics,
            })
        rows.append(row)

    if not include_canonical:
        return rows

    def total(name: str) -> Decimal:
        return sum((Decimal(str(row.get(name) or 0)) for row in rows), Decimal("0"))

    return {
        "rows": rows,
        "individual_item_cif_override": getattr(license_obj, "individual_item_cif_override", None),
        "effective_cif_mode": (
            "INDIVIDUAL_ITEM" if getattr(license_obj, "individual_item_cif_override", None) is True else "LEGACY"
        ),
        "footer_totals": {
            "total_cif": total("total_cif"),
            "debited_cif": total("debited_cif"),
            "allotted_cif": total("allotted_cif"),
            # Both names are explicit API affordances for existing/new table
            # consumers; their values are backend Decimal totals.
            "balance_cif": total("balance_cif"),
            # A licence-level balance is displayed on every row in shared
            # mode, but is one ceiling and must never be multiplied in a
            # table total.
            "actual_effective_balance_cif": (
                Decimal(str(license_obj.get_balance_cif))
                if getattr(license_obj, "individual_item_cif_override", None) is not True
                else total("effective_balance_cif")
            ),
        },
    }
