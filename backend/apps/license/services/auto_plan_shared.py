"""
Shared helpers for E1 / E5 / future Auto Plan services.

Keeping the optimization logic here means a single change propagates to all
norms automatically — no duplicated code to drift out of sync.
"""
from __future__ import annotations

import math
from collections import defaultdict


def ensure_plan_item_names(names_with_norm: list[tuple[str, str | None]]) -> dict[str, int]:
    """
    Guarantee that every planned item name exists in ``ItemNameModel``,
    creating any that are missing.  Returns ``{name: ItemNameModel.id}``.

    This is the single point that satisfies requirement §2 — Auto Plan must
    NEVER fail because a planned item name is absent from the database.  Call
    this at the top of every compute_*_auto_plan function instead of a plain
    filter/lookup that returns None for missing rows.

    Args:
        names_with_norm: list of ``(item_name, norm_class_code_or_None)`` pairs.
            The norm class is used only when creating a *new* row — existing
            rows are returned as-is regardless of their current norm assignment.

    Example::

        name_ids = ensure_plan_item_names([
            ('SWP - E1', 'E1'),
            ('DWP - E1', 'E1'),
            ('OTHER CONFECTIONERY - E1 Ingredients', 'E1'),
        ])
        # name_ids['SWP - E1'] → integer pk (created if needed)
    """
    from apps.core.models import ItemNameModel, SionNormClassModel

    # Load norm objects lazily (at most one query per distinct code).
    _norm_cache: dict[str, object] = {}

    def _get_norm(code: str | None):
        if code is None:
            return None
        if code not in _norm_cache:
            _norm_cache[code] = SionNormClassModel.objects.filter(norm_class=code).first()
        return _norm_cache[code]

    result: dict[str, int] = {}
    for name, norm_code in names_with_norm:
        norm_obj = _get_norm(norm_code)
        obj, _ = ItemNameModel.objects.get_or_create(
            name=name,
            defaults={
                'sion_norm_class': norm_obj,
                'is_active': True,
                'display_order': 999,  # end of list; admin can reorder later
            },
        )
        result[name] = obj.id
    return result


def group_by_desc(items):
    """
    Group import items by description so every rule creates one plan line
    PER DESCRIPTION GROUP rather than one per raw import-item row.

    This matches the Plan Tab's ``groupKeyOf`` grouping: items with the same
    description (e.g. "Dietary Fibre S.No 12 and 26") appear as a single
    group in the UI. The auto plan must save on the SAME representative item
    (lowest serial number) that the Plan Tab displays as the group anchor —
    otherwise the Plan Tab shows the group as "Not Planned" even though a
    plan line exists for another member of the same description group.

    Rules:
      * Representative = import item with the LOWEST serial_number in the group.
        (This may have available_quantity = 0 — the bulk_upsert capacity check
        uses group_ids_of() which sums all members, so the plan still validates.)
      * group_avail = sum of available_quantity across ALL members. Used as
        the planned qty input for the rule — items with avail=0 contribute 0.

    Returns:
        List of (representative_import_item, group_total_avail) tuples,
        one per distinct description group, in the order first seen.
    """
    buckets: dict = defaultdict(list)
    for ii in items:
        key = (ii.description or '').strip().upper()
        buckets[key].append(ii)

    result = []
    for group in buckets.values():
        rep = min(group, key=lambda x: x.serial_number)
        total_avail = sum(float(ii.available_quantity or 0) for ii in group)
        result.append((rep, total_avail))
    return result


def optimal_milk_split(
    total_qty: float,
    remaining_cif: float,
) -> tuple[float, float, float]:
    """
    Exact-residual optimization for Milk & Milk planning.

    Finds the combination of SWP / DWP / WPC that:
      1. Maximises quantity utilised  (subject to total_qty constraint)
      2. Leaves Remaining CIF = $0.00 (the "residual" product absorbs the exact
         leftover CIF with 3 dp fractional precision)
      3. Prefers cheaper base + expensive residual (maximises qty first)

    Algorithm
    ---------
    Divide the available qty/CIF space into avg-price bands and solve
    analytically — no iteration needed.

      avg = remaining_cif / total_qty

      avg < 1.50        SWP only;  qty = C / 1.50  (fractional)
      1.50 ≤ avg < 5    SWP (int, maximised) + DWP (fractional residual)
      5    ≤ avg < 20   DWP (int, maximised) + WPC (fractional residual)
      avg ≥ 20          WPC at full qty; surplus CIF flows to the caller

    Maximisation formula for a two-product band (SWP+DWP example):
        q_base     = FLOOR((p_high × Q − C) / (p_high − p_low))
        q_residual = (C − q_base × p_low) / p_high   ← exact, 3 dp

    Returns
    -------
    (q_swp, q_dwp, q_wpc) — non-negative floats, each rounded to 3 dp.
    The caller is responsible for mapping these to the norm-specific item
    names (e.g. "SWP - E1" vs "SWP - E5").
    """
    if total_qty <= 0 or remaining_cif <= 0:
        return 0.0, 0.0, 0.0

    Q = total_qty
    C = remaining_cif
    avg = C / Q

    if avg < 1.50:
        # Only SWP is affordable; fractional qty absorbs the exact CIF.
        return round(C / 1.50, 3), 0.0, 0.0

    if avg < 5.00:
        # SWP (integer, maximised) + DWP (fractional residual → CIF = 0)
        q_swp = float(math.floor((5.0 * Q - C) / 3.50))
        q_dwp = round((C - q_swp * 1.50) / 5.00, 3)
        return q_swp, q_dwp, 0.0

    if avg < 20.00:
        # DWP (integer, maximised) + WPC (fractional residual → CIF = 0)
        q_dwp = float(math.floor((20.0 * Q - C) / 15.00))
        q_wpc = round((C - q_dwp * 5.00) / 20.00, 3)
        return 0.0, q_dwp, q_wpc

    # avg ≥ 20: use all qty at WPC; surplus CIF (C − Q×20) flows to the
    # next planning rule (e.g. wheat flour mop-up in E5).
    return 0.0, 0.0, float(Q)
