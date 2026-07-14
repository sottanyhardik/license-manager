"""
Plan grouping — import items are grouped by description so a license is planned
per product (with the product's TOTAL quantity summed across serial numbers),
rather than per individual serial-number row.

The group key must match the frontend planner exactly:
  * description (trimmed, upper-cased) when present,
  * else "N:" + sorted item names,
  * else "ID:<id>" (never merge distinct un-named/undescribed items).

A group's plan is stored on its representative import item (lowest serial
number). The allot cap and bulk-upsert capacity aggregate across the whole
group, so allotting from any serial in the group draws down the shared plan.
"""
from __future__ import annotations


def plan_group_key(item) -> str:
    """Grouping key for an import item. Mirrors the frontend logic."""
    desc = (item.description or "").strip()
    if desc:
        return desc.upper()
    names = sorted(n.name for n in item.items.all())
    if names:
        return "N:" + ", ".join(names).upper()
    return f"ID:{item.id}"


def group_ids_of(item) -> list:
    """Return the import-item ids sharing this item's group within its license."""
    from apps.license.models import LicenseImportItemsModel

    key = plan_group_key(item)
    ids = []
    siblings = (
        LicenseImportItemsModel.objects
        .filter(license_id=item.license_id)
        .prefetch_related("items")
    )
    for sib in siblings:
        if plan_group_key(sib) == key:
            ids.append(sib.id)
    return ids
