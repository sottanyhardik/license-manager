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


def norm_plan_for_license(license_obj, *, balance_cif=None) -> dict:
    """
    INTERNAL / WRITE-ONLY: Legacy norm-based planning logic.

    This function computes planned quantities using legacy norm-specific
    planning engines (E1/E5/E126/E132 waterfalls). It is kept for backward
    compatibility with write paths that may still need it.

    MUST NOT be called from read paths (reports, exports, GET endpoints).
    Read paths must use LicenseItemPlan directly.

    Returns: {item_id: {planned_quantity, unit_price, planned_cif}}

    Args:
      balance_cif: optional pre-computed `license_obj.get_balance_cif` value.
        When omitted (the default), computed here via the model property.
    """
    from apps.license.models import LicenseImportItemsModel

    norm = detect_norm(license_obj)
    if not norm:
        return {}

    balance_cif = float(balance_cif) if balance_cif is not None else float(license_obj.get_balance_cif or 0)
    import_items = (
        LicenseImportItemsModel.objects
        .filter(license=license_obj)
        .select_related("hs_code")
        .prefetch_related("items")
    )
    result: dict = {}

    if norm == "E1":
        from decimal import Decimal

        from apps.license.services.e1_plan import E1Item, classify_e1_item, plan_e1_items

        item_qty: dict = {}       # import_item_id -> its own available qty
        items: list[E1Item] = []
        for ii in import_items:
            names = list(ii.items.values_list("name", flat=True))
            key = ", ".join(sorted(names)) if names else (ii.description or "-")
            hs = ii.hs_code.hs_code if ii.hs_code else ""
            cat = classify_e1_item(key, hs, ii.description)
            if not cat:
                continue
            avail = Decimal(str(ii.available_quantity or 0))
            item_qty[ii.id] = avail
            items.append(E1Item(key=ii.id, category=cat, qty=avail))

        # Run the shared per-item engine — every consumer (Auto-Plan, this
        # function, Item Pivot Report) delegates to the same rules, so the
        # figures pre-filled here always match what those show.
        plan_result = plan_e1_items(items, Decimal(str(balance_cif)))
        cif_by_item: dict = {}
        for line in plan_result.lines:
            cif_by_item[line.key] = cif_by_item.get(line.key, Decimal("0")) + line.planned_cif

        for iid, avail in item_qty.items():
            item_cif = cif_by_item.get(iid, Decimal("0"))
            result[iid] = {
                "planned_quantity": round(float(avail), 3),
                "unit_price": round(float(item_cif / avail), 2) if avail else 0.0,
                "planned_cif": round(float(item_cif), 2),
            }

    elif norm == "E5":
        from decimal import Decimal

        from apps.license.services.e5_plan import E5Item, classify_e5_item, plan_e5_items

        item_qty: dict = {}       # import_item_id -> its own available qty
        items: list[E5Item] = []
        for ii in import_items:
            names = list(ii.items.values_list("name", flat=True))
            key = ", ".join(sorted(names)) if names else (ii.description or "-")
            hs = ii.hs_code.hs_code if ii.hs_code else ""
            cat = classify_e5_item(key, hs, ii.description)
            if not cat:
                continue
            avail = Decimal(str(ii.available_quantity or 0))
            item_qty[ii.id] = avail
            items.append(E5Item(key=ii.id, category=cat, qty=avail))

        # Run the shared per-item engine — every consumer (Auto-Plan, this
        # function, Item Pivot Report) delegates to the same rules, so the
        # figures pre-filled here always match what those show.
        plan_result = plan_e5_items(items, Decimal(str(balance_cif)))
        cif_by_item: dict = {}
        for line in plan_result.lines:
            cif_by_item[line.key] = cif_by_item.get(line.key, Decimal("0")) + line.planned_cif

        for iid, avail in item_qty.items():
            item_cif = cif_by_item.get(iid, Decimal("0"))
            result[iid] = {
                "planned_quantity": round(float(avail), 3),
                "unit_price": round(float(item_cif / avail), 2) if avail else 0.0,
                "planned_cif": round(float(item_cif), 2),
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
        for iid, p in plan_e132_per_item(records, balance_cif).items():
            result[iid] = {
                "planned_quantity": round(float(p["planned_quantity"]), 3),
                "unit_price": round(float(p["unit_price"]), 2) if p["unit_price"] is not None else 0.0,
                "planned_cif": round(float(p["planned_cif"]), 2) if p["planned_cif"] is not None else 0.0,
            }

    elif norm == "E126":
        # E126 planning = deterministic classification (services/e126_plan.py):
        # each import item is classified into one planning item (Nuts / PKO /
        # Olive Oil) and priced at that item's fixed unit price. Unclassified
        # items get no plan line.
        from apps.license.services.e126_plan import plan_e126_per_item

        records = [
            {
                "record_id": ii.id,
                "quantity": float(ii.available_quantity or 0),
                "hs_code": ii.hs_code.hs_code if ii.hs_code else "",
                "description": ii.description or "",
            }
            for ii in import_items
        ]
        for iid, p in plan_e126_per_item(records, balance_cif).items():
            result[iid] = {
                "planned_quantity": round(float(p["planned_quantity"]), 3),
                "unit_price": round(float(p["unit_price"]), 2) if p["unit_price"] is not None else 0.0,
                "planned_cif": round(float(p["planned_cif"]), 2) if p["planned_cif"] is not None else 0.0,
            }

    return result
