"""
Norm-based utilization planning (E1 / E5 / E132) reduced to PER-IMPORT-ITEM
planned values, so the manual plan module can pre-fill from it.

Mirrors the exact waterfall calls used by the Item Pivot report
(`apps/license/views/item_pivot_report.py`) so the pre-filled figures match
what the user already sees there:

  * E1 / E5 — classify each import item into a category, run the category
    waterfall, then allocate each item its proportional share of the
    category's planned CIF (unit price = category effective rate).
  * E132 — sequential debit; only "Success" rows carry planned figures.

Returns {import_item_id: {'planned_quantity', 'unit_price', 'planned_cif'}}.
Items with no norm allocation are simply absent from the map.
"""
from __future__ import annotations


def detect_norm(license_obj) -> str:
    """Return 'E1' | 'E5' | 'E132' | '' for the license's primary export norm."""
    if not license_obj.export_license.exists():
        return ""
    first = license_obj.export_license.first()
    code = (first.norm_class.norm_class if first and first.norm_class else "") or ""
    code = code.strip()
    if code == "E132":
        return "E132"
    if code == "E5":
        return "E5"
    # E1 family (but not E126 / E132).
    if "E1" in code and "E126" not in code and "E132" not in code:
        return "E1"
    return ""


def effective_plan_for_license(license_obj):
    """
    The plan a license should show in reports, choosing EXCLUSIVELY:
      * if the license has ANY manual plan line  -> use the manual plan only
      * otherwise                                -> use the norm (E1/E5/E132) plan

    Returns (source, {import_item_id: {planned_quantity, unit_price, planned_cif}})
    where source is 'manual', 'norm', or '' (neither).
    """
    from apps.license.services.plan_reporting import plan_map_for_license

    manual = plan_map_for_license(license_obj.id)
    if manual:  # at least one manual plan line exists for this license
        out = {}
        for iid, d in manual.items():
            q = float(d["total_planned_quantity"] or 0)
            c = float(d["total_planned_cif"] or 0)
            out[iid] = {
                "planned_quantity": q,
                "unit_price": round(c / q, 2) if q else 0.0,
                "planned_cif": c,
            }
        return "manual", out

    norm = norm_plan_for_license(license_obj)
    return ("norm" if norm else ""), norm


def norm_plan_for_license(license_obj) -> dict:
    """Per-import-item norm plan: {item_id: {planned_quantity, unit_price, planned_cif}}."""
    from apps.license.models import LicenseImportItemsModel

    norm = detect_norm(license_obj)
    if not norm:
        return {}

    balance_cif = float(license_obj.get_balance_cif or 0)
    import_items = (
        LicenseImportItemsModel.objects
        .filter(license=license_obj)
        .select_related("hs_code")
        .prefetch_related("items")
    )
    result: dict = {}

    if norm in ("E1", "E5"):
        if norm == "E1":
            from apps.license.services.e1_plan import (
                E1_CATS as CATS, E1_EXCLUDED_CONDITIONS as EXCL,
                classify_e1_item as classify, compute_e1_plan as compute,
            )
        else:
            from apps.license.services.e5_plan import (
                E5_CATS as CATS, classify_e5_item as classify, compute_e5_plan as compute,
            )
            EXCL = None

        display_qty = {c: 0.0 for c in CATS}
        util_qty = {c: 0.0 for c in CATS}
        item_util: dict = {}      # import_item_id -> util qty contributed
        item_cat: dict = {}       # import_item_id -> category

        for ii in import_items:
            names = list(ii.items.values_list("name", flat=True))
            key = ", ".join(sorted(names)) if names else (ii.description or "-")
            hs = ii.hs_code.hs_code if ii.hs_code else ""
            cat = classify(key, hs, ii.description)
            if not cat or cat not in display_qty:
                continue
            avail = float(ii.available_quantity or 0)
            display_qty[cat] += avail
            cond = (ii.condition_type or "").strip()
            if EXCL is not None:
                util_inc = 0.0 if cond in EXCL.get(cat, frozenset()) else avail
            else:
                util_inc = avail
            util_qty[cat] += util_inc
            item_util[ii.id] = util_inc
            item_cat[ii.id] = cat

        # Run the waterfall exactly as the pivot does.
        if norm == "E1":
            planned, rates = compute(display_qty, util_qty, balance_cif)
        else:
            planned, rates = compute(display_qty, None, balance_cif, None)

        for iid, uq in item_util.items():
            cat = item_cat[iid]
            cat_uq = util_qty.get(cat, 0.0)
            cat_plan = planned.get(cat, 0.0)
            item_plan = (uq / cat_uq) * cat_plan if cat_uq else 0.0
            result[iid] = {
                "planned_quantity": round(uq, 3),
                "unit_price": round(item_plan / uq, 2) if uq else 0.0,
                "planned_cif": round(item_plan, 2),
            }

    elif norm == "E132":
        # E132 planning = deterministic classification (services/e132_plan.py):
        # each import item is classified into one planning item and priced at that
        # item's fixed unit price. planned_cif = available_qty × price (0.0 when the
        # price is To-Be-Defined, e.g. Milk). Unclassified items get no plan line.
        from apps.license.services.e132_plan import plan_e132_per_item

        records = [
            {
                "record_id": ii.id,
                "quantity": float(ii.available_quantity or 0),
                "hs_code": ii.hs_code.hs_code if ii.hs_code else "",
                "description": ii.description or "",
            }
            for ii in import_items
        ]
        for iid, p in plan_e132_per_item(records).items():
            result[iid] = {
                "planned_quantity": round(float(p["planned_quantity"]), 3),
                "unit_price": round(float(p["unit_price"]), 2) if p["unit_price"] is not None else 0.0,
                "planned_cif": round(float(p["planned_cif"]), 2) if p["planned_cif"] is not None else 0.0,
            }

    return result
