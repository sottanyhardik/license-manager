"""
Norm-based utilization planning (E1 / E5 / E126 / E132) reduced to
PER-IMPORT-ITEM planned values, so the manual plan module can pre-fill from
it.

Mirrors the exact waterfall calls used by the Item Pivot report
(`apps/license/views/item_pivot_report.py`) so the pre-filled figures match
what the user already sees there:

  * E1 / E5 — classify each import item into a category, run the category
    waterfall, then allocate each item its proportional share of the
    category's planned CIF (unit price = category effective rate).
  * E132 / E126 — deterministic per-item classification (Nuts/Yeast/PKO/RBD/
    Cheese/Aluminium for E132; Nuts/PKO/Olive-Oil for E126), priced at each
    planning item's fixed unit price.

Returns {import_item_id: {'planned_quantity', 'unit_price', 'planned_cif'}}.
Items with no norm allocation are simply absent from the map.
"""
from __future__ import annotations


def detect_norm(license_obj) -> str:
    """Return 'E1' | 'E5' | 'E126' | 'E132' | 'A3627' | '' for the license's
    primary export norm."""
    if not license_obj.export_license.exists():
        return ""
    first = license_obj.export_license.first()
    code = (first.norm_class.norm_class if first and first.norm_class else "") or ""
    code = code.strip()
    if code == "E132":
        return "E132"
    if code == "E126":
        return "E126"
    if code == "E5":
        return "E5"
    if code == "A3627":
        return "A3627"
    # E1 family (but not E126 / E132).
    if "E1" in code and "E126" not in code and "E132" not in code:
        return "E1"
    return ""


def effective_plan_for_license(license_obj, *, balance_cif=None):
    """
    DEPRECATED: Read-only paths must use LicenseItemPlan directly.

    Legacy function that merged manual and norm-derived plans. This is now
    DEPRECATED for read paths — reports, exports, and other GET endpoints must
    read ONLY from persisted LicenseItemPlan, never from on-the-fly planning.

    This function is kept for backward compatibility with legacy code, but
    SHOULD NOT be called from new read paths. Use plan_map_for_license() to
    read manual plans from LicenseItemPlan instead.

    WRITE paths (planning operations) should use the canonical planning engine
    directly, not this function.

    Returns (source, {import_item_id: {planned_quantity, unit_price, planned_cif}})
    where source is 'manual' (manual plan present), or '' (no plan).
    """
    from apps.license.services.plan_reporting import plan_map_for_license
    from apps.license.models import LicenseImportItemsModel

    manual = plan_map_for_license(license_obj.id)

    # Per-item mapping: ONLY manual plans, no norm fallback
    out = {}
    for iid, d in manual.items():
        q = float(d["total_planned_quantity"] or 0)
        c = float(d["total_planned_cif"] or 0)
        out[iid] = {
            "planned_quantity": q,
            "unit_price": round(c / q, 2) if q else 0.0,
            "planned_cif": c,
        }

    # Remaining = plan − allotted (per item), floored at 0.
    if out:
        allot = {
            row["id"]: (float(row["allotted_quantity"] or 0), float(row["allotted_value"] or 0))
            for row in LicenseImportItemsModel.objects
            .filter(license=license_obj, id__in=list(out.keys()))
            .values("id", "allotted_quantity", "allotted_value")
        }
        for iid, p in out.items():
            aq, av = allot.get(iid, (0.0, 0.0))
            rq = max(p["planned_quantity"] - aq, 0.0)
            rc = max(p["planned_cif"] - av, 0.0)
            p["planned_quantity"] = rq
            p["planned_cif"] = rc
            p["unit_price"] = round(rc / rq, 2) if rq else 0.0

    source = "manual" if manual else ""
    return source, out


