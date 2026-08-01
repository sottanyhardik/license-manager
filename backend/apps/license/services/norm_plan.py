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


def effective_plan_for_license(license_obj, *, balance_cif=None):
    """
    Per-import-item effective plan, net of allotments.

    Composition (per item, not per license):
      * MANUAL FIRST — if an import item has a manual plan line, that line is used
        and is FIXED: the automated norm logic never overrides it.
      * NORM FILLS THE REST — items without a manual line use the norm (E1/E5/E132)
        plan.
      * REMAINING = plan − allotted — the planned quantity and CIF are then reduced
        by what has already been ALLOTTED for that item (floored at 0). Because the
        item's allotted_quantity / allotted_value are maintained by the allotment
        signals, this figure shrinks when an allotment is made and grows back when
        one is removed, with no stored-plan mutation.

    Args:
      balance_cif: optional pre-computed `license_obj.get_balance_cif` value
        (int/float/Decimal), for bulk callers that already batched every
        license's balance and want to avoid `norm_plan_for_license`
        re-triggering the model property's own DB round-trips. Defaults to
        `None`, in which case `norm_plan_for_license` computes it itself
        exactly as before — existing callers are unaffected.

    Returns (source, {import_item_id: {planned_quantity, unit_price, planned_cif}})
    where source is 'manual' (any manual line present), 'norm', or '' (neither).
    """
    from apps.license.services.plan_reporting import plan_map_for_license
    from apps.license.models import LicenseImportItemsModel

    manual = plan_map_for_license(license_obj.id)
    norm = norm_plan_for_license(license_obj, balance_cif=balance_cif)

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


def norm_plan_for_license(license_obj, *, balance_cif=None) -> dict:
    """Per-import-item norm plan: {item_id: {planned_quantity, unit_price, planned_cif}}.

    Args:
      balance_cif: optional pre-computed `license_obj.get_balance_cif` value.
        When omitted (the default, used by every caller except the bulk
        exporter), computed here exactly as before via the model property.
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

    return result
