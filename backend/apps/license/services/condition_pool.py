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

For other condition_type values:
    ""   (empty / open)   → available_value = license_balance
    "AU" (actual user)    → available_value = license_balance (item is
                            non-transferable, but still usable up to the
                            licence balance — the restriction is on transfer,
                            not on use)
"""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from django.db.models import Sum, Value, DecimalField
from django.db.models.functions import Coalesce

DEC_0 = Decimal("0")


def _parse_pct(condition_type: str | None) -> Decimal | None:
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


def compute_condition_pools(license_obj) -> dict[str, Decimal]:
    """
    Return a `{condition_type: remaining}` map for every distinct %-condition
    actually used on this licence.

    Cost: 1 query to find distinct condition_types + 3 SUM queries per group
    (BOE / Allotment / Trade) + 1 SUM for licence credit. For a licence with
    4 condition groups this is ~13 queries total — vs the old O(N²) which
    could be 2000+ for 38 items.
    """
    from apps.license.models import LicenseImportItemsModel
    from apps.bill_of_entry.models import RowDetails
    from apps.allotment.models import AllotmentItems

    distinct_conds: Iterable[str] = (
        LicenseImportItemsModel.objects
        .filter(license=license_obj)
        .exclude(condition_type="")
        .exclude(condition_type__isnull=True)
        .values_list("condition_type", flat=True)
        .distinct()
    )

    pcts: dict[str, Decimal] = {}
    for c in distinct_conds:
        p = _parse_pct(c)
        if p is not None and p > DEC_0:
            pcts[c] = p
    if not pcts:
        return {}

    license_credit = license_obj._calculate_license_credit() or DEC_0

    # Trade lines may not exist as a model in every install; import lazily.
    try:
        from apps.trade.models import LicenseTradeLine
    except Exception:
        LicenseTradeLine = None  # type: ignore

    pools: dict[str, Decimal] = {}
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
        ).exclude(is_hidden=True).aggregate(
            t=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
        )["t"] or DEC_0

        allotted = AllotmentItems.objects.filter(
            item_id__in=item_ids, allotment__bill_of_entry__isnull=True
        ).aggregate(
            t=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
        )["t"] or DEC_0

        traded = DEC_0
        if LicenseTradeLine is not None:
            # Only SALE trade lines debit the pool, matching
            # LicenseBalanceCalculator.calculate_trade()'s own direction
            # filter -- Purchase trade adds to the license (already
            # accounted for elsewhere) and must not reduce the pool.
            traded = LicenseTradeLine.objects.filter(
                sr_number_id__in=item_ids,
                trade__direction='SALE',
            ).aggregate(
                t=Coalesce(Sum("cif_fc"), Value(DEC_0), output_field=DecimalField())
            )["t"] or DEC_0

        used = Decimal(str(debited)) + Decimal(str(allotted)) + Decimal(str(traded))
        remaining = pool - used
        pools[cond] = remaining if remaining >= DEC_0 else DEC_0

    return pools


def compute_condition_pools_bulk(license_ids) -> dict[int, dict[str, Decimal]]:
    """Batched equivalent of :func:`compute_condition_pools` for many licences.

    Returns ``{license_id: {condition_type: remaining}}``, byte-identical to
    calling ``compute_condition_pools`` per licence but in a handful of queries
    instead of ~13 per licence. Used by the Item Pivot Report, which iterates
    hundreds of licences.

    Correctness: a per-group ``SUM(cif_fc)`` equals the Decimal sum of the
    per-item ``SUM(cif_fc)`` (Decimal addition is exact), and licence credit is
    the same ``Coalesce(Sum('cif_fc'), 0)`` over export items — so the arithmetic
    matches the per-licence path exactly.
    """
    from collections import defaultdict

    from apps.license.models import LicenseImportItemsModel, LicenseExportItemModel
    from apps.bill_of_entry.models import RowDetails
    from apps.allotment.models import AllotmentItems

    license_ids = list(license_ids)
    if not license_ids:
        return {}

    # 1. %-condition items grouped by (license, condition_type).
    groups: dict[int, dict[str, list]] = defaultdict(lambda: defaultdict(list))
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
    credit_by_license: dict[int, Decimal] = {}
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
            RowDetails.objects.filter(
                sr_number_id__in=all_item_ids, transaction_type="D"
            ).exclude(is_hidden=True),
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
            # Only SALE trade lines debit the pool, matching
            # LicenseBalanceCalculator.calculate_trade()'s own direction
            # filter -- Purchase trade adds to the license and must not
            # reduce the pool.
            traded_map = _per_item(
                LicenseTradeLine.objects.filter(
                    sr_number_id__in=all_item_ids,
                    trade__direction='SALE',
                ),
                "sr_number_id",
            )
        except Exception:
            traded_map = {}
    else:
        debited_map = allotted_map = traded_map = {}

    result: dict[int, dict[str, Decimal]] = {}
    for lid in license_ids:
        if lid not in groups:
            result[lid] = {}
            continue
        credit = credit_by_license.get(lid, DEC_0) or DEC_0
        pools: dict[str, Decimal] = {}
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
    return pools.get(condition_type, license_obj._calculate_license_credit() * pct / Decimal("100"))


def _resolve_available_value(item, balance_map: dict, pools_map: dict) -> Decimal:
    """
    Per-item resolver shared by `available_value_bulk_map` — mirrors
    `LicenseImportItemsModel.available_value_calculated`'s branches EXACTLY
    (see that property's docstring in `apps/license/models/core.py`), just
    reading from pre-computed batch maps instead of running per-item
    queries. Keep these two in lock-step; if one branches, the other must.
    """
    # Special marker value — identical check to `available_value_calculated`.
    if item.cif_inr == Decimal("0.01") or item.cif_fc == Decimal("0.01"):
        return Decimal("0.01")

    if not item.license_id:
        return DEC_0

    license_balance = balance_map.get(item.license_id, DEC_0)
    cond = (item.condition_type or "").strip()

    if cond.endswith("%"):
        pct = _parse_pct(cond)
        if pct is None or pct <= DEC_0:
            return license_balance
        pools = pools_map.get(item.license_id) or {}
        if cond in pools:
            remaining = pools[cond]
        else:
            # Defensive fallback — should be unreachable in practice, since
            # `compute_condition_pools_bulk` derives its groups from a fresh
            # query over the same licence/condition_type, so an item with a
            # valid "%" condition always lands in its licence's pool map.
            # Mirrors `remaining_for_condition`'s own miss-path (full pool,
            # no usage subtracted) for a licence this defensive branch has
            # no batched credit for.
            remaining = item.license._calculate_license_credit() * pct / Decimal("100")
        return min(remaining, license_balance)

    # "AU" or open: track licence balance directly.
    return license_balance


def available_value_bulk_map(items) -> dict[int, Decimal]:
    """
    Batched equivalent of `LicenseImportItemsModel.available_value_calculated`
    for MANY items, possibly spanning MANY different licences — byte-
    identical to calling `.available_value_calculated` per item, but in a
    small fixed number of queries regardless of batch size instead of
    O(items) balance-aggregate + condition-pool queries.

    Used by list-style reads of `LicenseImportItemSerializer` (e.g. the
    Allotment "available-items" action) to avoid re-running a licence's
    full Balance CIF aggregate once per import item on that licence.

    Composes:
      - `LicenseBalanceCalculator.calculate_financial_balance_for_licenses`
        for the `license_balance` component (same formula `available_value_
        calculated` reaches via the licence's `get_balance_cif` — see that
        property's docstring).
      - `compute_condition_pools_bulk` for the "%"-condition shared-pool
        component.

    Returns `{item_id: Decimal}`. Keep in lock-step with
    `available_value_calculated` / `_resolve_available_value` — never
    duplicate the branching logic elsewhere.
    """
    items = list(items)
    if not items:
        return {}

    from apps.license.services.balance_calculator import LicenseBalanceCalculator

    license_ids = list({item.license_id for item in items if item.license_id})
    # Financial Ledger formula — must match `available_value_calculated`'s
    # own `get_balance_cif` exactly (see this function's docstring: "keep
    # in lock-step... never duplicate the branching logic elsewhere").
    balance_map = LicenseBalanceCalculator.calculate_financial_balance_for_licenses(license_ids) if license_ids else {}
    pools_map = compute_condition_pools_bulk(license_ids) if license_ids else {}

    return {item.id: _resolve_available_value(item, balance_map, pools_map) for item in items}
