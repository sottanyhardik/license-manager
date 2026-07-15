# license/services/norm_plan.py
"""
Norm-based utilization planning (E1 / E5 / E132) reduced to PER-IMPORT-ITEM
planned values, so the manual plan module can pre-fill from it.

Ported from legacy/backend/apps/license/services/norm_plan.py.
New backend field mapping:
  - license_obj.get_balance_cif  → _get_balance_cif(license_obj)
"""
from __future__ import annotations

from decimal import Decimal


def _get_balance_cif(license_obj) -> float:
    """Access balance_cif via the OneToOne LicenseBalance sub-table."""
    try:
        return float(license_obj.balance.balance_cif or 0)
    except Exception:
        return 0.0


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
    Per-import-item effective plan, net of allotments.

    Returns (source, {import_item_id: {planned_quantity, unit_price, planned_cif}})
    where source is 'manual' (any manual line present), 'norm', or '' (neither).
    """
    from apps.license.services.plan_reporting import plan_map_for_license
    from apps.license.models import LicenseImportItemsModel

    manual = plan_map_for_license(license_obj.id)
    norm = norm_plan_for_license(license_obj)

    # Per-item merge: manual line wins for its item; norm fills every other item.
    out = {}
    for iid in set(norm) | set(manual):
        if iid in manual:
            d = manual[iid]
            q = float(d["total_planned_quantity"] or 0)
            c = float(d["total_planned_cif"] or 0)
            out[iid] = {
                "planned_quantity": q,
                "unit_price": round(c / q, 2) if q else 0.0,
                "planned_cif": c,
            }
        else:
            n = norm[iid]
            out[iid] = {
                "planned_quantity": float(n["planned_quantity"]),
                "unit_price": float(n["unit_price"]),
                "planned_cif": float(n["planned_cif"]),
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

    source = "manual" if manual else ("norm" if norm else "")
    return source, out


def norm_plan_for_license(license_obj) -> dict:
    """Per-import-item norm plan: {item_id: {planned_quantity, unit_price, planned_cif}}."""
    from apps.license.models import LicenseImportItemsModel

    norm = detect_norm(license_obj)
    if not norm:
        return {}

    balance_cif = _get_balance_cif(license_obj)
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
        for iid, p in plan_e132_per_item(records, balance_cif).items():
            result[iid] = {
                "planned_quantity": round(float(p["planned_quantity"]), 3),
                "unit_price": round(float(p["unit_price"]), 2) if p["unit_price"] is not None else 0.0,
                "planned_cif": round(float(p["planned_cif"]), 2) if p["planned_cif"] is not None else 0.0,
            }

    return result
