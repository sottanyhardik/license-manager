"""
Plan grouping — import items are grouped by HSN + description so a license is
planned per PHYSICAL PRODUCT (with the product's TOTAL quantity summed across
serial numbers), rather than per individual serial-number row.

The group key (`plan_group_key`) — mirrored by `plan_utilization_rows`, the
Planning Modal (which renders `plan_utilization_rows`' output as-is), and
`group_ids_of`/`plan_status_for` (capacity enforcement) — is:
  * HSN + description (both trimmed, upper-cased, internal whitespace runs
    collapsed to one space, and whitespace immediately next to a "/"
    removed — see `_normalize_text`) when a description is present,
  * else HSN + "N:" + sorted item names,
  * else "ID:<id>" (never merge distinct un-named/undescribed items; HSN
    alone is not a reliable enough signal without a description or names).

Two import items are the SAME planning group only when BOTH their HSN and
their normalized description match — different HSN, or different
description, always means a different group, even if the other field is
identical (e.g. "Cane Sugar" under HSN 17029020 and 17029090 are never
pooled together).

A group's plan is stored on its representative import item (lowest serial
number). The allot cap and bulk-upsert capacity aggregate across the whole
group, so allotting from any serial in the group draws down the shared plan.

`merge_key`/`merge_planned_import_items` below share the same normalization
(`_normalize_text`) for the Item Pivot Report's read-only per-cell
consolidation, where callers already have a plain `(hs_code, description)`
pair rather than a live import-item instance.
"""
from __future__ import annotations

import re
from decimal import Decimal


def _normalize_text(value) -> str:
    """Case-insensitive, trimmed, internal whitespace runs collapsed to one
    space, and whitespace immediately next to a "/" removed entirely (e.g.
    "Packing Material /PP", "Packing Material / PP" and "Packing Material/
    PP" all normalize identically). Real DGFT license data carries exactly
    this kind of inconsistent slash-spacing for the SAME physical product
    (e.g. "Fruit /Juice" / "Fruit / Juice" / "Fruit/ Juice" on one license,
    HSN 20089991) — treating them as distinct products split one item across
    several Planning Modal / Item Pivot Report rows instead of merging them,
    which is worse than the (much rarer) risk of over-merging two genuinely
    different slash-separated descriptions."""
    text = re.sub(r"\s+", " ", (value or "").strip())
    text = re.sub(r"\s*/\s*", "/", text)
    return text.upper()


def _description_of(item) -> str:
    return (getattr(item, "description", "") or "").strip()


def _hsn_of(item) -> str:
    hs = getattr(item, "hs_code", None)
    code = getattr(hs, "hs_code", None) if hs else None
    return _normalize_text(code)


def _item_names_of(item) -> list[str]:
    manager = getattr(item, "items", None)
    if manager is None:
        return []
    return sorted(
        (name for name in ((obj.name or "").strip() for obj in manager.all()) if name),
        key=str.casefold,
    )


def plan_group_key(item) -> str:
    """Grouping key for an import item — HSN + normalized description (see
    module docstring). Mirrors the frontend logic (the Planning Modal
    consumes `plan_utilization_rows`' pre-grouped output; it does not
    re-derive groups client-side)."""
    hsn = _hsn_of(item)
    desc = _normalize_text(_description_of(item))
    # Historical keys implicitly meant KG because that is the model default.
    # Preserve those stable keys, but suffix every non-KG unit so quantities
    # such as MT/PCS can never be pooled with KG (or with each other) without
    # an explicit conversion registry.  There is no such registry in the
    # current schema, therefore separation is the only lossless behavior.
    unit = _normalize_text(getattr(item, "unit", "") or "KG")
    unit_suffix = "" if unit == "KG" else f"|U:{unit}"
    if desc:
        return f"{hsn}|{desc}{unit_suffix}"
    names = _item_names_of(item)
    if names:
        return f"{hsn}|N:" + ", ".join(names).upper() + unit_suffix
    return f"ID:{getattr(item, 'id', None)}"


def merge_key(hs_code, description) -> str:
    """Read-only merge key for the Item Pivot Report: HSN + normalized
    description, given as plain values rather than a live import-item
    instance (used to consolidate `planned_import_items` entries that are
    already-resolved ledger dicts). Same normalization as `plan_group_key`;
    kept as a separate entry point only because its callers don't have (and
    don't need) the item-names/ID fallback chain — pivot ledger entries
    always carry a real `hs_code`/`description` pair."""
    return f"{_normalize_text(hs_code)}|{_normalize_text(description)}"


def merge_planned_import_items(pits: list[dict]) -> list[dict]:
    """Consolidate distinct import items that are the same physical product
    (same `merge_key`) into one display row.

    Single shared implementation for every "list of the actual import items
    behind this cell" the Item Pivot Report builds (persisted-plan path and
    the live E1/E5 waterfall path in `item_pivot_report.py`) — no separate
    merge logic in the JSON serialization, React, or the Excel export; all
    three consume whatever list this function returns.

    Input: one dict per import item, each with `import_item_id`, `hs_code`,
    `description`, `quantity`, `allotted_quantity`, `debited_quantity`,
    `available_quantity`, `planned_quantity`, `planned_cif_fc` (floats).

    Output: one dict per DISTINCT `merge_key`, with every numeric field
    summed across its members, `import_item_id` set to the lowest member id
    (stable "representative"), a new `import_item_ids` list of every member
    (sorted), and a new `unit_price`: the single per-item rate
    (`planned_cif_fc / planned_quantity`) when every member's own rate
    agrees, `None` when no member has a planned quantity, else the literal
    string `"Merged"` — differing rates are never silently averaged.
    """
    groups: dict[str, dict] = {}
    order: list[str] = []

    for pit in pits:
        key = merge_key(pit.get('hs_code'), pit.get('description'))
        group = groups.get(key)
        if group is None:
            group = {
                'import_item_ids': [],
                'hs_code': pit.get('hs_code', ''),
                'description': pit.get('description', ''),
                'quantity': 0.0,
                'allotted_quantity': 0.0,
                'debited_quantity': 0.0,
                'available_quantity': 0.0,
                'planned_quantity': 0.0,
                'planned_cif_fc': 0.0,
                '_rates': set(),
            }
            groups[key] = group
            order.append(key)

        group['import_item_ids'].append(pit['import_item_id'])
        for field in (
            'quantity', 'allotted_quantity', 'debited_quantity',
            'available_quantity', 'planned_quantity', 'planned_cif_fc',
        ):
            group[field] += pit.get(field) or 0.0

        planned_qty = pit.get('planned_quantity') or 0.0
        planned_cif = pit.get('planned_cif_fc') or 0.0
        if planned_qty:
            group['_rates'].add(round(planned_cif / planned_qty, 6))

    merged: list[dict] = []
    for key in order:
        group = groups[key]
        rates = group.pop('_rates')
        group['import_item_ids'] = sorted(group['import_item_ids'])
        group['import_item_id'] = group['import_item_ids'][0]
        if len(rates) == 1:
            group['unit_price'] = next(iter(rates))
        elif not rates:
            group['unit_price'] = None
        else:
            group['unit_price'] = 'Merged'
        merged.append(group)

    return sorted(merged, key=lambda g: g['import_item_id'])


def merge_items_for_classification(import_items) -> list[dict]:
    """Group raw import items into one unit per physical product (same
    `plan_group_key`) — the single canonical grouping mechanism every
    Auto-Plan engine (E1, E5, E126, E132) and every plan-consuming layer
    (`plan_enforcement.py`, `plan_utilization.py`, exports) uses. No engine
    may invent its own grouping logic; this is the one.

    Works on ANY list of import items, not just a license's full set — two
    usage patterns exist depending on whether classification depends on an
    item's own M2M item-name tags:
      * E126/E132: call this on the license's FULL item list, then classify
        each resulting group ONCE (their classification is pure HSN/
        description, independent of item-name tags, so grouping before or
        after classifying is equivalent).
      * E1/E5: `classify_e1_item`/`classify_e5_item` partly key off an
        import item's own M2M item-name tags (e.g. "other confectionery",
        "tartaric", "7607" for E1; "dietary fibre", "wheat flour", "olive
        oil", "pko", "rbd" for E5), so two serials of the same physical
        product COULD classify into different categories if their tags
        happen to differ. E1/E5's auto-plan modules therefore classify each
        RAW item first (unchanged, existing behavior), then call this on
        each already-classified bucket — grouping only for representative-
        anchoring and quantity-summing, never touching classification order.

    Returns one dict per group, in first-seen order:
      * `representative_id`: the LOWEST-SERIAL-NUMBER member (this module's
        own top-of-file docstring: "a group's plan is stored on its
        representative import item, lowest serial number"). Falls back to
        the member's own id if `serial_number` is unavailable (defensive
        only — every real `LicenseImportItemsModel` has one).
      * `member_ids`: every member id, sorted
      * `hs_code` / `description`: raw (unnormalized) text from one member —
        equal-after-normalization across the group by construction
      * `item_names`: sorted union of every member's item-name tags
      * `available_quantity`: Decimal sum of `available_quantity` across members
    """
    from decimal import Decimal

    groups: dict[str, dict] = {}
    order: list[str] = []

    for item in import_items:
        key = plan_group_key(item)
        group = groups.get(key)
        if group is None:
            group = {
                'member_ids': [],
                'hs_code': _raw_hsn_of(item),
                'description': _description_of(item),
                'item_names': set(),
                'available_quantity': Decimal('0'),
                '_serial_by_id': {},
            }
            groups[key] = group
            order.append(key)

        group['member_ids'].append(item.id)
        group['_serial_by_id'][item.id] = getattr(item, 'serial_number', item.id)
        group['item_names'].update(_item_names_of(item))
        avail = getattr(item, 'available_quantity', None)
        group['available_quantity'] += Decimal(str(avail)) if avail is not None else Decimal('0')

    merged: list[dict] = []
    for key in order:
        group = groups[key]
        serial_by_id = group.pop('_serial_by_id')
        group['member_ids'].sort()
        group['representative_id'] = min(group['member_ids'], key=lambda mid: serial_by_id.get(mid, mid))
        group['item_names'] = sorted(group['item_names'], key=str.casefold)
        merged.append(group)

    return merged


def _raw_hsn_of(item) -> str:
    """Literal (unnormalized) HS code text, for feeding classify_e1_item/
    classify_e5_item — which expect the actual HS code string, not the
    upper-cased form `_hsn_of` produces for grouping-key comparisons."""
    hs = getattr(item, "hs_code", None)
    return (getattr(hs, "hs_code", None) or "") if hs else ""


def existing_split_balances_for_groups(license_obj, groups, split_target_names) -> dict:
    """
    Consolidate existing `LicenseItemPlan` split rows (e.g. E126's PKO/Olive
    Oil, E132's PKO/Cheese) across EVERY member of each group — not just its
    representative — onto that group's representative id.

    Returns ``{representative_id: {planning_item_name: {'remaining_quantity',
    'remaining_cif_fc', 'unit_price'}}}``.

    Why this has to look at every member, not just the representative: a
    licence's import items can be re-serialized (e.g. by a DGFT resync) into
    new sibling rows sharing the same `plan_group_key` — same physical
    product, smaller quantities summing to the original. A split generated
    BEFORE that resync lives on whatever row was the representative back
    then, which may no longer be this group's representative (or may no
    longer even look like a fresh candidate on its own tiny remaining
    quantity). Querying only the CURRENT representative would silently lose
    track of that split — or worse, let a NEW, independent split be
    generated for the other siblings while the old one is never revisited,
    which is exactly how a group's displayed/enforced total can end up
    double-counted (some engines used to plan per raw import item instead of
    per group; see `merge_items_for_classification`'s docstring).

    Consolidation: SUM `remaining_quantity`/`remaining_cif_fc` per
    `(representative_id, item_name)` across every contributing member.
    `unit_price` for the consolidated entry is the value-weighted rate
    (`remaining_cif_fc / remaining_quantity`, same style as
    `_effective_rate` elsewhere in the planning engines) when quantity > 0 —
    this stays a single honest number even if two stale rows happened to
    carry different prices, and the caller's own fixed-price-ceiling
    validation still catches an out-of-range result. Falls back to 0 when a
    target has no contributing member at all.
    """
    from apps.license.models import LicenseItemPlan

    member_to_rep: dict[int, int] = {}
    for group in groups:
        rep_id = group['representative_id']
        for member_id in group['member_ids']:
            member_to_rep[member_id] = rep_id

    if not member_to_rep:
        return {}

    rows = (
        LicenseItemPlan.objects
        .filter(license=license_obj, import_item_id__in=list(member_to_rep),
                 item_name__name__in=split_target_names)
        .values("import_item_id", "item_name__name", "remaining_quantity", "remaining_cif_fc")
    )

    from decimal import Decimal

    totals: dict[tuple, dict] = {}
    for row in rows:
        rep_id = member_to_rep.get(row["import_item_id"])
        if rep_id is None:
            continue
        key = (rep_id, row["item_name__name"])
        bucket = totals.setdefault(key, {"remaining_quantity": Decimal("0"), "remaining_cif_fc": Decimal("0")})
        bucket["remaining_quantity"] += row["remaining_quantity"] or Decimal("0")
        bucket["remaining_cif_fc"] += row["remaining_cif_fc"] or Decimal("0")

    out: dict[int, dict[str, dict]] = {}
    for (rep_id, item_name), bucket in totals.items():
        qty = bucket["remaining_quantity"]
        cif = bucket["remaining_cif_fc"]
        unit_price = (cif / qty) if qty > 0 else Decimal("0")
        out.setdefault(rep_id, {})[item_name] = {
            "remaining_quantity": qty,
            "remaining_cif_fc": cif,
            "unit_price": unit_price,
        }
    return out


def validate_group_plan_lines(
    item_lines, item_planning_items, avail_qty, unit_price_map, *, is_preserved,
    qty_tolerance=Decimal("0.01"), price_tolerance=Decimal("0.01"),
) -> bool:
    """
    Mandatory validation gate every Auto-Plan engine runs before accepting a
    group's plan lines — the single shared implementation (no engine keeps
    its own copy). Checks span the WHOLE group's lines together, never one
    line at a time, so a single bad line rejects its siblings too — the
    caller must never save a partial group.

    Args:
      item_lines: the group's candidate plan-line dicts (each with at least
        `unit_price`/`planned_quantity`).
      item_planning_items: parallel list of each line's planning-item name
        (same order/length as `item_lines`), used to look up its ceiling in
        `unit_price_map`.
      avail_qty: the group's current summed available quantity (Decimal).
      unit_price_map: `{planning_item_name: Decimal max_price}` for this
        norm (e.g. E126/E132's `UNIT_PRICE`, or an E1/E5 caller's own
        per-step price table).
      is_preserved: True when these lines re-emit an existing, already-
        generated balance rather than a fresh computation — see the
        quantity check below for why this changes what's enforced.

    Checks:
      * PRICE CEILING — every line's `unit_price` must not exceed its
        planning item's max price (`unit_price_map`) by more than
        `price_tolerance`. Checked ALWAYS, preserved or fresh — fixed
        prices are hard business constants, and a price above the ceiling
        is never legitimate whether just computed or re-emitted from a
        preserved balance. This is the safety net against stale/legacy
        `LicenseItemPlan` rows (e.g. a hand-edited `bulk_upsert` row, or
        data orphaned by a DGFT re-serialization) carrying an out-of-range
        price being blindly re-emitted forever by a "preserve once
        generated" rule.
      * QUANTITY vs AVAILABLE — total planned quantity must not exceed
        `avail_qty` by more than `qty_tolerance`. Checked ONLY when
        `is_preserved` is False: a FRESH computation must satisfy this by
        construction (a pure safety-net assertion — it should never
        actually fire for a correctly-implemented engine), but a PRESERVED
        split's remaining balance is intentionally decoupled from the
        group's current available_quantity once generated — real debits
        drain it independently via `plan_line_id`, and available_quantity
        can move for unrelated reasons without invalidating an
        already-committed split (see e.g. `test_e126_auto_plan.py::
        TestPkoOliveSplitPreservedOnceGenerated`).

    Returns True when the group's lines pass and may be saved; False when
    the caller must reject the WHOLE group's lines (skip and log a warning)
    rather than save anything for it this run.
    """
    price_ok = all(
        Decimal(str(ln['unit_price'])) <= unit_price_map.get(name, Decimal('0')) + price_tolerance
        for ln, name in zip(item_lines, item_planning_items)
    )
    if is_preserved:
        return price_ok
    total_qty = sum((Decimal(str(ln['planned_quantity'])) for ln in item_lines), Decimal('0'))
    qty_ok = total_qty <= avail_qty + qty_tolerance
    return price_ok and qty_ok


def validate_fresh_plan_lines(item_lines, avail_qty, *, qty_tolerance=Decimal("0.01")) -> bool:
    """
    Generic safety-net validation for a norm with NO "preserve once
    generated" split concept (E1, E5 — as opposed to E126/E132's fixed-ratio
    PKO/Olive-Oil / PKO/Cheese splits). Every E1/E5 line is a fresh
    recompute from the current balance on every run, so there is no stale/
    legacy preserved price to guard against — unlike `validate_group_plan_lines`,
    this deliberately does NOT check a price ceiling: E1/E5 include
    genuinely dynamic, balance-driven rates (milk DWP/SWP/WPC, E5's Wheat
    Flour mop-up) with no fixed business-rule maximum, so a price-ceiling
    check here would either need a per-step ceiling map that doesn't
    meaningfully exist for those steps, or silently reject correct engine
    output — see `plan_grouping.py`'s module docstring and
    `validate_group_plan_lines`'s docstring for why the ceiling check exists
    at all for E126/E132.

    Checks (both must hold):
      * every line's `planned_quantity`/`planned_cif_fc` is non-negative;
      * the group's total planned quantity does not exceed `avail_qty` by
        more than `qty_tolerance` — a pure safety net that should never
        actually fire for a correctly-implemented, structurally-bounded
        waterfall engine.

    Returns True when the group's lines pass and may be saved; False when
    the caller must reject the WHOLE group's lines (skip and log a warning).
    """
    for ln in item_lines:
        if Decimal(str(ln['planned_quantity'])) < 0 or Decimal(str(ln['planned_cif_fc'])) < 0:
            return False
    total_qty = sum((Decimal(str(ln['planned_quantity'])) for ln in item_lines), Decimal('0'))
    return total_qty <= avail_qty + qty_tolerance


def group_ids_of(item) -> list:
    """Return the import-item ids sharing this item's group within its license."""
    from apps.license.models import LicenseImportItemsModel

    license_id = getattr(item, "license_id", None)
    if not license_id:
        return []

    key = plan_group_key(item)
    ids = []
    siblings = (
        LicenseImportItemsModel.objects
        .filter(license_id=license_id)
        .select_related("hs_code")
        .prefetch_related("items")
    )
    for sib in siblings:
        if plan_group_key(sib) == key:
            ids.append(sib.id)
    return ids
