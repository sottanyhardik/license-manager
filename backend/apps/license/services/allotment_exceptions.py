"""
Allotment reconciliation exceptions (read-only).

Owner DEC-03 C (2026-11-20, `docs/qa/SAT_USER_DECISION_REGISTER.md`): an
allotment linked (``BillOfEntryModel.allotment`` M2M) to a BOE that carries no
DEBIT row — a rowless or placeholder BOE such as ``1234567`` — does NOT release
its reservation (see ``LicenseBalanceCalculator._allotment_release_condition``),
and every such link is listed here so users can link the real BOE or enter its
rows. No data is changed by this module.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable

from django.db.models import Exists, OuterRef

from apps.bill_of_entry.models import BillOfEntryModel, RowDetails
from apps.core.constants import DEBIT, DEC_0
from apps.core.utils.decimal_utils import to_decimal


def rowless_boe_link_exceptions(license_ids: Iterable[int]) -> list[dict[str, Any]]:
    """One row per (allotment item on the given licences, linked BOE without
    DEBIT rows). ``outstanding_cif_fc`` is the Balance Engine's live
    contribution of that allotment item (0 when another, real BOE link or a
    formal allocation already consumes it)."""
    from apps.license.services.balance_calculator import LicenseBalanceCalculator as LBC

    ids = list(license_ids)
    if not ids:
        return []
    rowless_boes = (
        BillOfEntryModel.objects
        .annotate(has_rows=Exists(RowDetails.objects.filter(bill_of_entry=OuterRef("pk"), transaction_type=DEBIT)))
        .filter(has_rows=False, allotment__allotment_details__item__license_id__in=ids)
        .values_list("id", "bill_of_entry_number", "allotment")
        .distinct()
    )
    boes_by_allotment: dict[int, list[tuple[int, str]]] = {}
    for boe_id, number, allotment_id in rowless_boes:
        boes_by_allotment.setdefault(allotment_id, []).append((boe_id, number))
    if not boes_by_allotment:
        return []

    rows: list[dict[str, Any]] = []
    items = (
        LBC.get_allotment_rows_bulk(ids)
        .filter(allotment_id__in=boes_by_allotment.keys())
        .values("id", "allotment_id", "item_id", "item__license_id", "cif_fc", "qty", "contributed")
        .order_by("allotment_id", "id")
    )
    for item in items:
        for boe_id, number in sorted(boes_by_allotment[item["allotment_id"]]):
            rows.append({
                "license_id": item["item__license_id"],
                "allotment_id": item["allotment_id"],
                "allotment_item_id": item["id"],
                "import_item_id": item["item_id"],
                "bill_of_entry_id": boe_id,
                "bill_of_entry_number": number,
                "cif_fc": to_decimal(item["cif_fc"], DEC_0),
                "qty": to_decimal(item["qty"], Decimal("0.000")),
                "outstanding_cif_fc": to_decimal(item["contributed"], DEC_0),
            })
    return rows
