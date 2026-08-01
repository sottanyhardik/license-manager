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
    if desc:
        return f"{hsn}|{desc}"
    names = _item_names_of(item)
    if names:
        return f"{hsn}|N:" + ", ".join(names).upper()
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
    """Group raw import items into one classification unit per physical
    product (same `plan_group_key`) — feeds the E1/E5 classifier and planner
    as a single merged item instead of once per serial number.

    `classify_e1_item`/`classify_e5_item` partly key off an import item's own
    M2M item-name tags (e.g. "other confectionery", "tartaric", "7607" for
    E1; "dietary fibre", "wheat flour", "olive oil", "pko", "rbd" for E5), so
    two serials of the same physical product can classify into different
    categories if their tags happen to differ. Classifying the whole group at
    once — using the UNION of every member's tags — closes that gap; merging
    the planner's OUTPUT afterwards (`merge_planned_import_items` above)
    cannot, since it only ever sees one category's bucket at a time.

    Returns one dict per group, in first-seen order:
      * `representative_id`: lowest member id (same convention as
        `group_ids_of`/`merge_planned_import_items`)
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
            }
            groups[key] = group
            order.append(key)

        group['member_ids'].append(item.id)
        group['item_names'].update(_item_names_of(item))
        avail = getattr(item, 'available_quantity', None)
        group['available_quantity'] += Decimal(str(avail)) if avail is not None else Decimal('0')

    merged: list[dict] = []
    for key in order:
        group = groups[key]
        group['member_ids'].sort()
        group['representative_id'] = group['member_ids'][0]
        group['item_names'] = sorted(group['item_names'], key=str.casefold)
        merged.append(group)

    return merged


def _raw_hsn_of(item) -> str:
    """Literal (unnormalized) HS code text, for feeding classify_e1_item/
    classify_e5_item — which expect the actual HS code string, not the
    upper-cased form `_hsn_of` produces for grouping-key comparisons."""
    hs = getattr(item, "hs_code", None)
    return (getattr(hs, "hs_code", None) or "") if hs else ""


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
