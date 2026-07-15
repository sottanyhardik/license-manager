# license/services/condition_pool.py
"""
Condition-pool calculator — the source of truth for the new restriction model.

Each `LicenseImportItemsModel.condition_type` value of the form "N%" (e.g.
"2%", "3%", "5%", "10%") creates a SHARED POOL on its licence:

    pool      = N% × license total CIF (sum of export-side CIF)
    used      = SUM(BOE debits + un-BOE'd allotments + trade lines)
                for every item in the licence with this condition_type
    remaining = max(pool - used, 0)

All import items that share the same condition_type draw from this single
pool; their `available_value` is therefore `min(remaining, license_balance)`.

Ported from legacy/backend/apps/license/services/condition_pool.py.
New backend field mapping:
  - balance_cif lives on license.balance.balance_cif (OneToOne)
  - No _calculate_license_credit() property — we query export-side CIF directly.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from django.db.models import Sum, Value, DecimalField
from django.db.models.functions import Coalesce

DEC_0 = Decimal("0")


def _parse_pct(condition_type) -> Decimal | None:
    """Return the % as a Decimal for "N%" values, else None."""
    if not condition_type:
        return None
    s = condition_type.strip()
    if s.endswith("%"):
        try:
            return Decimal(s[:-1])
        except Exception:
            return None
    return None


def _get_license_credit(license_obj) -> Decimal:
    """Sum of export-side CIF for this license (replaces _calculate_license_credit)."""
    from apps.license.models import LicenseExportItemModel
    result = LicenseExportItemModel.objects.filter(
        license=license_obj
    ).aggregate(
        t=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
    )["t"]
    return result or DEC_0


def compute_condition_pools(license_obj) -> dict:
    """
    Return a `{condition_type: remaining}` map for every distinct %-condition
    actually used on this licence.
    """
    from apps.license.models import LicenseImportItemsModel
    from apps.bill_of_entry.models import RowDetails
    from apps.allotment.models import AllotmentItems

    distinct_conds: Iterable = (
        LicenseImportItemsModel.objects
        .filter(license=license_obj)
        .exclude(condition_type="")
        .exclude(condition_type__isnull=True)
        .values_list("condition_type", flat=True)
        .distinct()
    )

    pcts: dict = {}
    for c in distinct_conds:
        p = _parse_pct(c)
        if p is not None and p > DEC_0:
            pcts[c] = p
    if not pcts:
        return {}

    license_credit = _get_license_credit(license_obj) or DEC_0

    # Trade lines may not exist as a model in every install; import lazily.
    try:
        from apps.trade.models import LicenseTradeLine
    except Exception:
        LicenseTradeLine = None  # type: ignore

    pools: dict = {}
    for cond, pct in pcts.items():
        pool = license_credit * pct / Decimal("100")

        item_ids = list(
            LicenseImportItemsModel.objects
            .filter(license=license_obj, condition_type=cond)
            .values_list("id", flat=True)
        )
        if not item_ids:
            pools[cond] = pool if pool >= DEC_0 else DEC_0
            continue

        debited = RowDetails.objects.filter(
            sr_number_id__in=item_ids, transaction_type="D"
        ).aggregate(
            t=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
        )["t"] or DEC_0

        allotted = AllotmentItems.objects.filter(
            item_id__in=item_ids, allotment__bill_of_entry__isnull=True
        ).aggregate(
            t=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
        )["t"] or DEC_0

        traded = DEC_0
        if LicenseTradeLine is not None:
            traded = LicenseTradeLine.objects.filter(
                sr_number_id__in=item_ids
            ).aggregate(
                t=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
            )["t"] or DEC_0

        used = Decimal(str(debited)) + Decimal(str(allotted)) + Decimal(str(traded))
        remaining = pool - used
        pools[cond] = remaining if remaining >= DEC_0 else DEC_0

    return pools


def compute_condition_pools_bulk(license_ids) -> dict:
    """Batched equivalent of compute_condition_pools for many licences.

    Returns {license_id: {condition_type: remaining}}.
    """
    from collections import defaultdict

    from apps.license.models import LicenseImportItemsModel, LicenseExportItemModel
    from apps.bill_of_entry.models import RowDetails
    from apps.allotment.models import AllotmentItems

    license_ids = list(license_ids)
    if not license_ids:
        return {}

    # 1. %-condition items grouped by (license, condition_type).
    groups: dict = defaultdict(lambda: defaultdict(list))
    all_item_ids: list = []
    for lid, iid, cond in (
        LicenseImportItemsModel.objects
        .filter(license_id__in=license_ids)
        .exclude(condition_type="")
        .exclude(condition_type__isnull=True)
        .values_list("license_id", "id", "condition_type")
    ):
        p = _parse_pct(cond)
        if p is not None and p > DEC_0:
            groups[lid][cond].append(iid)
            all_item_ids.append(iid)

    # 2. Licence credit (Sum export cif_fc), one grouped query.
    credit_by_license: dict = {}
    for lid, tot in (
        LicenseExportItemModel.objects
        .filter(license_id__in=license_ids)
        .values("license_id")
        .annotate(t=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField()))
        .values_list("license_id", "t")
    ):
        credit_by_license[lid] = tot or DEC_0

    # 3. Per-item component sums (three grouped queries total).
    def _per_item(qs, key) -> dict:
        return {
            iid: (t or DEC_0)
            for iid, t in qs.values(key).annotate(
                t=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
            ).values_list(key, "t")
        }

    if all_item_ids:
        debited_map = _per_item(
            RowDetails.objects.filter(sr_number_id__in=all_item_ids, transaction_type="D"),
            "sr_number_id",
        )
        allotted_map = _per_item(
            AllotmentItems.objects.filter(
                item_id__in=all_item_ids, allotment__bill_of_entry__isnull=True
            ),
            "item_id",
        )
        try:
            from apps.trade.models import LicenseTradeLine
            traded_map = _per_item(
                LicenseTradeLine.objects.filter(sr_number_id__in=all_item_ids),
                "sr_number_id",
            )
        except Exception:
            traded_map = {}
    else:
        debited_map = allotted_map = traded_map = {}

    result: dict = {}
    for lid in license_ids:
        if lid not in groups:
            result[lid] = {}
            continue
        credit = credit_by_license.get(lid, DEC_0) or DEC_0
        pools: dict = {}
        for cond, item_ids in groups[lid].items():
            pct = _parse_pct(cond)
            pool = credit * pct / Decimal("100")
            debited = sum((debited_map.get(i, DEC_0) for i in item_ids), DEC_0)
            allotted = sum((allotted_map.get(i, DEC_0) for i in item_ids), DEC_0)
            traded = sum((traded_map.get(i, DEC_0) for i in item_ids), DEC_0)
            used = Decimal(str(debited)) + Decimal(str(allotted)) + Decimal(str(traded))
            remaining = pool - used
            pools[cond] = remaining if remaining >= DEC_0 else DEC_0
        result[lid] = pools
    return result


def remaining_for_condition(license_obj, condition_type: str) -> Decimal | None:
    """Single-condition variant. Returns None for non-%-conditions / empty."""
    pct = _parse_pct(condition_type)
    if pct is None or pct <= DEC_0:
        return None
    pools = compute_condition_pools(license_obj)
    return pools.get(condition_type, _get_license_credit(license_obj) * pct / Decimal("100"))
