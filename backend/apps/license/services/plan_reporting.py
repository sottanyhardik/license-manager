# license/services/plan_reporting.py
"""
Helpers to surface user-authored utilization plans (LicenseItemPlan) in reports.

A single query per license builds a map keyed by import-item id, holding the
per-item planned totals (summed across split lines) and the split breakdown.
Reused by the item report, item-pivot report and the bulk balance Excel.

Ported verbatim from legacy/backend/apps/license/services/plan_reporting.py.
"""
from __future__ import annotations

from decimal import Decimal


def _build_map(rows) -> dict:
    """Build the {import_item_id: {...}} map from a LicenseItemPlan queryset."""
    out: dict = {}
    for r in rows:
        entry = out.setdefault(r.import_item_id, {
            "total_planned_quantity": Decimal("0"),
            "total_planned_cif": Decimal("0"),
            "splits": [],
        })
        entry["total_planned_quantity"] += r.planned_quantity or Decimal("0")
        entry["total_planned_cif"] += r.planned_cif_fc or Decimal("0")
        entry["splits"].append({
            "item_name": r.item_name.name if r.item_name else None,
            "planned_quantity": float(r.planned_quantity or 0),
            "unit_price": float(r.unit_price or 0),
            "planned_cif_fc": float(r.planned_cif_fc or 0),
        })

    # Normalise Decimal totals to float for JSON/Excel consumers.
    for entry in out.values():
        entry["total_planned_quantity"] = float(entry["total_planned_quantity"])
        entry["total_planned_cif"] = float(entry["total_planned_cif"])
    return out


def plan_map_for_license(license_id) -> dict:
    """Per-import-item plan map for a single license (see _build_map)."""
    from apps.license.models import LicenseItemPlan
    return _build_map(
        LicenseItemPlan.objects.filter(license_id=license_id).select_related("item_name")
    )


def plan_map_for_import_items(item_ids) -> dict:
    """Per-import-item plan map for an explicit set of import-item ids."""
    from apps.license.models import LicenseItemPlan
    ids = list(item_ids)
    if not ids:
        return {}
    return _build_map(
        LicenseItemPlan.objects.filter(import_item_id__in=ids).select_related("item_name")
    )
