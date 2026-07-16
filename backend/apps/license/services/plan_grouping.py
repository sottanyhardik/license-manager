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


def _description_of(item) -> str:
    return (getattr(item, "description", "") or "").strip()


def _item_names_of(item) -> list[str]:
    manager = getattr(item, "items", None)
    if manager is None:
        return []
    return sorted(
        (name for name in ((obj.name or "").strip() for obj in manager.all()) if name),
        key=str.casefold,
    )


def plan_group_key(item) -> str:
    """Grouping key for an import item. Mirrors the frontend logic."""
    desc = _description_of(item)
    if desc:
        return desc.upper()
    names = _item_names_of(item)
    if names:
        return "N:" + ", ".join(names).upper()
    return f"ID:{getattr(item, 'id', None)}"


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
        .prefetch_related("items")
    )
    for sib in siblings:
        if plan_group_key(sib) == key:
            ids.append(sib.id)
    return ids
