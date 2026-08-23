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

from typing import Any, Dict, List

from apps.core.constants import DEC_0, DEC_000
from apps.license.models import LicenseImportItemsModel


def compute_item_ledger_rows(license_obj) -> List[Dict[str, Any]]:
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

        rows.append({
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
        })
    return rows
