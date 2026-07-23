"""
Shared "one row per planning item" view over a licence's import items.

Product wants every Plan Utilization screen/report to show ONE row per
planning item (the same `plan_grouping.plan_group_key` product group that
`plan_enforcement.py` already caps allotments against) instead of one row
per raw SION S.No entry — three import-item rows that share a description
(e.g. "Refined Cane Sugar" split across S.No 3/13/23) collapse into one row
whose S.No column lists every merged serial.

This module is the SINGLE place that composes the grouping (`plan_grouping`)
with the group-level plan status (`plan_enforcement.plan_status_for`) and the
split breakdown (`plan_reporting.plan_map_for_license` /
`plan_map_for_import_items`) into report-ready rows. It does not change any
of those modules' semantics — `plan_group_key`/`group_ids_of` remain the
single definition of "group" (correctness-critical for allotment-cap
enforcement), and `plan_status_for` remains the single definition of
Original/Used/Remaining.

Callers:
  - `apps.license.views.license.LicenseDetailsViewSet.retrieve` — adds a
    top-level `plan_utilization` key to the licence-detail response.
  - `apps.license.services.exporters.license_balance_excel` — the
    single-licence and bulk "Plan Utilization" Excel sections.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from apps.core.constants import DEC_0, DEC_000


def _dec(value, default: Decimal = DEC_000) -> Decimal:
    if value is None:
        return default
    return value if isinstance(value, Decimal) else Decimal(str(value))


def plan_utilization_rows(
    license_obj,
    *,
    plan_map: Optional[Dict[int, Dict[str, Any]]] = None,
    items: Optional[List[Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Group `license_obj`'s import items by `plan_grouping.plan_group_key` and
    return one dict per group, in first-seen (= lowest serial number) order.

    Each row:
      group_id            - id of the group's representative import item
                             (lowest serial number) — matches the convention
                             `PlanningEditor.tsx`/`bulk_upsert` already use
                             for where a group's `LicenseItemPlan` rows live.
      description          - representative item's description, falling
                             back to its joined item names / "ID:<id>" (same
                             fallback the frontend's `groupKeyOf` uses).
      hs_code               - first non-empty HS code among the group's members.
      serials               - sorted list of every member's serial_number.
      member_ids            - every member's import-item id, in serial order.
      item_names            - deduped {id, name} dicts for every attached
                             ItemNameModel across all members, name-sorted.
      available_quantity    - Σ available_quantity across members (Decimal).
      total_quantity         - Σ quantity across members (Decimal).
      balance_cif_fc         - Σ available_value across members (Decimal) —
                             the same item-level "available CIF" the licence
                             detail serializer exposes as `balance_cif_fc`
                             (a stored field; NOT the costlier
                             `LicenseImportItemsModel.balance_cif_fc`
                             property, which re-queries per call).
      splits                 - concatenation of every member's plan-map
                             `splits` list (defensive union across the whole
                             group — mirrors `plan_status_for`'s own
                             defensiveness via `group_ids_of`).
      has_plan / original_quantity / used_quantity / remaining_quantity /
      original_cif_fc / used_cif_fc / remaining_cif_fc
                             - group-level plan status from ONE
                             `plan_status_for(representative)` call (it
                             already aggregates across the whole group
                             internally). `has_plan=False` and the six
                             numeric fields omitted when the group has no
                             `LicenseItemPlan` rows at all.

    Args:
      plan_map: pre-built `{import_item_id: {...}}` map (from
        `plan_map_for_license`/`plan_map_for_import_items`) for callers that
        already batched it — e.g. `item_pivot_report.py`'s per-report batch.
        Computed here (one query) when not supplied.
      items: explicit list of import-item model instances to group, for
        callers that need their OWN filtered/prefetched subset (e.g. a
        report that already applied a balance floor) rather than every
        import item on the licence. Defaults to
        `license_obj.import_license.all()`. Sorted by `serial_number` in
        Python (not via `.order_by()`, which would issue a fresh query
        against any prefetch cache the caller already populated).
    """
    from apps.license.services.plan_enforcement import plan_status_for
    from apps.license.services.plan_grouping import plan_group_key
    from apps.license.services.plan_reporting import plan_map_for_license

    if items is None:
        items = list(license_obj.import_license.all())
    items = sorted(items, key=lambda it: it.serial_number or 0)

    if plan_map is None:
        plan_map = plan_map_for_license(license_obj.id)

    groups: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []

    for item in items:
        key = plan_group_key(item)
        group = groups.get(key)
        if group is None:
            group = {
                "group_id": item.id,
                "_representative": item,
                "description": (item.description or "").strip() or None,
                "hs_code": None,
                "serials": [],
                "member_ids": [],
                "_item_name_ids": set(),
                "item_names": [],
                "available_quantity": DEC_000,
                "total_quantity": DEC_000,
                "balance_cif_fc": DEC_0,
                "splits": [],
            }
            groups[key] = group
            order.append(key)

        group["serials"].append(item.serial_number)
        group["member_ids"].append(item.id)
        if not group["hs_code"]:
            hs = getattr(item, "hs_code", None)
            if hs and getattr(hs, "hs_code", None):
                group["hs_code"] = hs.hs_code
        for name_obj in item.items.all():
            name = (getattr(name_obj, "name", "") or "").strip()
            if name_obj.id not in group["_item_name_ids"]:
                group["_item_name_ids"].add(name_obj.id)
                group["item_names"].append({"id": name_obj.id, "name": name})
        group["available_quantity"] += _dec(item.available_quantity)
        group["total_quantity"] += _dec(item.quantity)
        group["balance_cif_fc"] += _dec(item.available_value, DEC_0)
        member_plan = plan_map.get(item.id)
        if member_plan:
            group["splits"].extend(member_plan.get("splits", []))

    rows: List[Dict[str, Any]] = []
    for key in order:
        group = groups[key]
        representative = group.pop("_representative")
        group.pop("_item_name_ids")
        group["serials"] = sorted(group["serials"])
        group["item_names"].sort(key=lambda n: (n["name"] or "").casefold())
        if not group["description"]:
            group["description"] = (
                ", ".join(n["name"] for n in group["item_names"]) or f"ID:{group['group_id']}"
            )

        status = plan_status_for(representative)
        if status is None:
            group["has_plan"] = False
        else:
            group["has_plan"] = True
            group["original_quantity"] = status["original_quantity"]
            group["used_quantity"] = status["used_quantity"]
            group["remaining_quantity"] = status["remaining_quantity"]
            group["original_cif_fc"] = status["original_cif_fc"]
            group["used_cif_fc"] = status["used_cif_fc"]
            group["remaining_cif_fc"] = status["remaining_cif_fc"]

        rows.append(group)

    return rows
