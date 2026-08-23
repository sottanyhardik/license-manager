"""
Shared "how is this import item being used" query — the single source of
truth for BOE debits + open (non-BOE) allotments against one
`LicenseImportItemsModel` row.

Before this module existed, this exact query pair (`RowDetails` DEBIT rows +
`AllotmentItems` with no linked BOE) was hand-rolled independently in:
  - `apps/license/views/license.py::LicenseDetailsViewSet.item_usage`
  - `apps/license/services/exporters/license_balance_pdf.py` (Customs Ledger
    per-item loop, and again in the end-of-PDF "Summary" loop)
  - `apps/license/services/exporters/license_balance_excel.py` (three
    functions, each with its own copy)

All of those now call `get_item_usage()` below instead, so there is exactly
one query to get right/optimize.
"""
from collections import defaultdict
from decimal import Decimal

from apps.core.constants import DEBIT


ZERO_CIF = Decimal("0.00")
ZERO_QTY = Decimal("0.000")


def eligible_boe_debits_for_license(license_obj):
    """Canonical actual BOE debit allocations for one licence.

    ``RowDetails.pk`` is the debit-allocation identity.  The query starts at
    licence import items and deliberately has no optional planning, alias,
    HSN, allotment, or header-value joins that could widen or multiply the
    eligible financial population.
    """
    from apps.bill_of_entry.models import RowDetails, annotate_and_exclude_hidden

    return (
        annotate_and_exclude_hidden(
            RowDetails.objects.filter(
                sr_number__license_id=license_obj.pk,
                transaction_type=DEBIT,
                bill_of_entry__isnull=False,
            ),
            boe_field="bill_of_entry",
        )
        .select_related("sr_number", "bill_of_entry")
        .order_by("pk")
    )


def rollup_actual_boe_debits_for_license(license_obj):
    """Aggregate canonical debit allocations once, before optional joins."""
    rows = list(eligible_boe_debits_for_license(license_obj))
    per_item = defaultdict(lambda: {
        "boe_used_quantity": ZERO_QTY,
        "boe_used_cif": ZERO_CIF,
        "row_ids": [],
    })
    for row in rows:
        bucket = per_item[row.sr_number_id]
        bucket["boe_used_quantity"] += row.qty or ZERO_QTY
        bucket["boe_used_cif"] += row.cif_fc or ZERO_CIF
        bucket["row_ids"].append(row.pk)
    return {
        "rows": rows,
        "row_count_before_aggregation": len(rows),
        "row_count_after_deduplication": len({row.pk for row in rows}),
        "actual_boe_quantity": sum((row.qty or ZERO_QTY for row in rows), ZERO_QTY),
        "actual_boe_cif": sum((row.cif_fc or ZERO_CIF for row in rows), ZERO_CIF),
        "per_import_item": dict(per_item),
    }


def get_item_usage(import_item):
    """
    Args:
        import_item: LicenseImportItemsModel instance.

    Returns:
        dict with 'boes' (RowDetails queryset, DEBIT rows for this item,
        select_related for company/port) and 'allotments' (AllotmentItems
        queryset, open/no-BOE rows for this item, select_related for
        company) — both lazy querysets, not yet evaluated.
    """
    from apps.bill_of_entry.models import RowDetails, annotate_and_exclude_hidden
    from apps.allotment.models import AllotmentItems

    boes = (
        annotate_and_exclude_hidden(
            RowDetails.objects.filter(
                sr_number=import_item, transaction_type=DEBIT,
                bill_of_entry__isnull=False,
            ),
            # Previous-owner "hidden" BOEs (genuinely hidden per audit
            # trail) are excluded — this usage query feeds live
            # balance/report figures (Item Summary drawer, Excel
            # exporters), never the Customs History audit view.
            boe_field="bill_of_entry",
        )
        .select_related('bill_of_entry__company', 'bill_of_entry__port', 'bill_of_entry__planning_target_item')
    )
    allotments = (
        AllotmentItems.objects.filter(item=import_item, allotment__bill_of_entry__isnull=True)
        .select_related('allotment__company', 'allotment__planning_target_item')
    )
    return {'boes': boes, 'allotments': allotments}


def get_item_usage_for_items(item_ids):
    """
    Batched sibling of `get_item_usage` for many items at once (e.g. every
    import item on a licence) — avoids one query pair per item.

    Args:
        item_ids: iterable of LicenseImportItemsModel pks.

    Returns:
        {item_id: {'boes': [...], 'allotments': [...]}} — values are lists
        (already evaluated), grouped by `sr_number_id` / `item_id`.
    """
    from collections import defaultdict

    from apps.bill_of_entry.models import RowDetails, annotate_and_exclude_hidden
    from apps.allotment.models import AllotmentItems

    ids = list(item_ids)
    result = {i: {'boes': [], 'allotments': []} for i in ids}
    if not ids:
        return result

    boes_by_item = defaultdict(list)
    for row in (
        annotate_and_exclude_hidden(
            RowDetails.objects.filter(
                sr_number_id__in=ids, transaction_type=DEBIT,
                bill_of_entry__isnull=False,
            ),
            boe_field="bill_of_entry",
        )
        .select_related('bill_of_entry__company', 'bill_of_entry__port', 'bill_of_entry__planning_target_item')
    ):
        boes_by_item[row.sr_number_id].append(row)

    allotments_by_item = defaultdict(list)
    for row in (
        AllotmentItems.objects.filter(item_id__in=ids, allotment__bill_of_entry__isnull=True)
        .select_related('allotment__company', 'allotment__planning_target_item')
    ):
        allotments_by_item[row.item_id].append(row)

    for i in ids:
        result[i]['boes'] = boes_by_item.get(i, [])
        result[i]['allotments'] = allotments_by_item.get(i, [])
    return result


def billed_no_boe_bulk_map(item_ids) -> dict:
    """
    Batched sibling of `LicenseImportItemSerializer.get_billed_no_boe` —
    total CIF from SALE trade lines with no BOE attached to the parent
    trade, for MANY import items in one query instead of one per item.

    Byte-identical to calling the per-item aggregate
    (`LicenseTradeLine.objects.filter(sr_number=item, trade__direction=
    'SALE', trade__boes__isnull=True).aggregate(Sum('cif_fc'))`) for each
    id — same filter, just grouped. An id with no matching trade lines is
    simply absent from the result (callers should use `.get(id, DEC_0)`,
    matching the per-item method's own zero-default via `Coalesce`).

    Args:
        item_ids: iterable of LicenseImportItemsModel pks.

    Returns:
        `{item_id: Decimal}` billed-no-BOE total per item.
    """
    from decimal import Decimal

    from django.db.models import DecimalField, Sum, Value
    from django.db.models.functions import Coalesce

    from apps.trade.models import LicenseTradeLine

    ids = list(item_ids)
    if not ids:
        return {}

    rows = (
        LicenseTradeLine.objects.filter(
            sr_number_id__in=ids,
            trade__direction='SALE',
            trade__boes__isnull=True,
        )
        .values('sr_number_id')
        .annotate(t=Coalesce(Sum('cif_fc'), Value(Decimal('0')), output_field=DecimalField()))
    )
    return {row['sr_number_id']: row['t'] for row in rows}
