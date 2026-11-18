"""Item Pivot — Licence Utilization & Planning Intelligence (read-only).

Builds four views over the same filtered licence population as the classic
Item Pivot (``item_pivot_selection.select_pivot_licenses``):

* overview  — totals + the actual → planned waterfall;
* licences  — canonical figures per licence (``LicenseBalanceCalculator`` bulk
  components; signed balance, ``is_over_utilised``);
* products  — one row per master item (``ItemNameModel``) × SION (owner
  decision 2026-11-18). Import items with no master-item link are "Unmapped",
  with more than one link "Ambiguous" — kept separate, never merged;
* eligibility — every licence × product cell with quantities, plans, max unit
  price and a compliance status.

Nothing is written. Money is Decimal end-to-end and serialised as strings.
Recommendations are a separate call (``recommend_for_licenses``) that runs the
existing Auto Plan engine in preview inside a rolled-back transaction, so every
SION / split / cap / CIF-budget rule comes from the single planning engine.
"""
from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.core.constants import DEC_0, DEC_000
from apps.license.models import LicenseItemPlan, SionPlanningRule
from apps.license.services.balance_calculator import LicenseBalanceCalculator as LBC
from apps.license.services.item_usage import billed_no_boe_qty_bulk_map, get_item_usage_for_items
from apps.license.services.planning_tolerances import apply_remaining_plan_tolerance, effective_planning_balance_cif

QTY_TOL = Decimal("0.001")
CIF_TOL = Decimal("0.01")

CORRECT, UNDERUTILIZED, WARNING, BLOCKED, OVERPLANNED = "CORRECT", "UNDERUTILIZED", "WARNING", "BLOCKED", "OVERPLANNED"


def _d(value, default=DEC_0) -> Decimal:
    if value is None or value == "":
        return default
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _s(value) -> str:
    return str(value)


def _norm_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^0-9A-Za-z]+", " ", str(value or ""))).strip().upper()


def _licence_sion(licence) -> str | None:
    norms = sorted({e.norm_class.norm_class for e in licence.export_license.all() if e.norm_class_id})
    return ", ".join(norms) or None


def _product_identity(item, sion: str | None) -> tuple[str, dict]:
    """Master-item identity of one import item (never guessed)."""
    names = list(item.items.all())
    hsn = getattr(item.hs_code, "hs_code", None) if item.hs_code_id else None
    if len(names) == 1:
        name = names[0]
        item_sion = name.sion_norm_class.norm_class if name.sion_norm_class_id else sion
        return f"ITEM:{name.pk}:{item_sion or '-'}", {
            "kind": "MAPPED", "item_name_id": name.pk, "product": name.name, "sion": item_sion,
            "mapping_basis": "Master item link (LicenseImportItemsModel.items)",
        }
    if len(names) > 1:
        ids = sorted(n.pk for n in names)
        return f"AMBIGUOUS:{'-'.join(map(str, ids))}:{sion or '-'}", {
            "kind": "AMBIGUOUS", "item_name_id": None, "product": " / ".join(sorted(n.name for n in names)), "sion": sion,
            "mapping_basis": f"Import item linked to {len(names)} master items — not merged",
        }
    desc = _norm_text(item.description)
    return f"UNMAPPED:{hsn or '-'}:{desc}:{sion or '-'}", {
        "kind": "UNMAPPED", "item_name_id": None, "product": (item.description or "").strip() or "(no description)", "sion": sion,
        "mapping_basis": "No master item link — kept separate",
    }


def _max_unit_prices() -> dict[tuple[int, str], Decimal]:
    """Highest configured unit price per (master item, SION) from active planning rules."""
    prices: dict[tuple[int, str], Decimal] = {}
    rules = SionPlanningRule.objects.filter(is_active=True).select_related("sion").prefetch_related("percentage_rows", "unit_value_rows")
    for rule in rules:
        sion = rule.sion.norm_class
        pairs = []
        if rule.import_item_id:
            pairs.append((rule.import_item_id, _d(rule.max_unit_price)))
        pairs.extend((row.import_item_id, _d(row.unit_price)) for row in rule.percentage_rows.all())
        pairs.extend((row.import_item_id, _d(row.max_unit_price)) for row in rule.unit_value_rows.all())
        for item_name_id, price in pairs:
            key = (item_name_id, sion)
            if price > prices.get(key, DEC_0):
                prices[key] = price
    return prices


def _status(cell: dict, licence: dict) -> tuple[str, list[str]]:
    reasons: list[str] = []
    balance_qty, planned_qty = _d(cell["balance_qty"]), _d(cell["planned_qty"])
    licence_available = _d(licence["available_cif"])
    if cell["kind"] != "MAPPED":
        reasons.append(cell["mapping_basis"])
        return WARNING, reasons
    if not licence["components_reconcile"]:
        reasons.append("Licence CIF components do not reproduce the canonical balance — reconciliation required")
        return WARNING, reasons
    if licence["is_over_utilised"]:
        reasons.append(f"Licence is over-utilised: canonical balance {licence['available_cif']}")
        return WARNING, reasons
    if planned_qty > balance_qty + QTY_TOL:
        reasons.append(f"Planned qty {planned_qty} exceeds remaining entitlement {balance_qty}")
        return OVERPLANNED, reasons
    if _d(licence["final_balance_cif"]) < -CIF_TOL:
        reasons.append(f"Licence plans exceed available CIF by {abs(_d(licence['final_balance_cif']))}")
        return OVERPLANNED, reasons
    if balance_qty <= QTY_TOL:
        reasons.append("Entitlement quantity exhausted")
        return BLOCKED, reasons
    if cell.get("max_unit_price") is None:
        reasons.append(f"No active planning rule covers this product under {cell.get('sion') or 'its SION'} — not plannable by Auto Plan")
        return WARNING, reasons
    if effective_planning_balance_cif(licence_available) <= DEC_0:
        reasons.append(f"Licence available CIF {licence['available_cif']} is below the planning threshold")
        return BLOCKED, reasons
    # Existing planner tolerances: residuals below 100 qty / 500 CIF are treated as nil.
    unplanned_qty, _ = apply_remaining_plan_tolerance(balance_qty - planned_qty, DEC_0)
    if unplanned_qty > QTY_TOL and effective_planning_balance_cif(licence["final_balance_cif"]) > DEC_0:
        reasons.append(f"{balance_qty - planned_qty} qty and {licence['final_balance_cif']} CIF still unplanned")
        return UNDERUTILIZED, reasons
    return CORRECT, reasons


def build_intelligence(licences: list) -> dict[str, Any]:
    ids = [lic.pk for lic in licences]
    credit = LBC.calculate_credit_for_licenses(ids)
    boe = LBC.calculate_debit_for_licenses(ids)
    allotment = LBC.calculate_allotment_for_licenses(ids)
    billed = LBC.calculate_trade_for_licenses(ids)
    available = LBC.calculate_financial_balance_for_licenses(ids)
    purchase_credit = LBC.calculate_purchase_credit_for_licenses(ids)
    opening = LBC.calculate_opening_balance_for_licenses(ids, purchase_credit_map=purchase_credit)

    import_items = [item for lic in licences for item in lic.import_license.all()]
    item_ids = [item.pk for item in import_items]
    usage = get_item_usage_for_items(item_ids)
    billed_qty = billed_no_boe_qty_bulk_map(item_ids)
    plans_by_item: dict[int, list] = defaultdict(list)
    plans_by_licence: dict[int, Decimal] = defaultdict(lambda: DEC_0)
    for plan in LicenseItemPlan.objects.filter(
        license_id__in=ids, is_active=True, is_deleted=False, is_cancelled=False,
    ).select_related("item_name"):
        plans_by_item[plan.import_item_id].append(plan)
        plans_by_licence[plan.license_id] += _d(plan.planned_cif_fc)
    prices = _max_unit_prices()

    licence_rows: dict[int, dict] = {}
    for lic in licences:
        original, boe_cif, allot_cif, billed_cif = (_d(m.get(lic.pk)) for m in (credit, boe, allotment, billed))
        avail = _d(available.get(lic.pk))
        planned = plans_by_licence[lic.pk]
        # Financial engine: opening + purchase credit − billed − BOE − allotment. Its opening /
        # purchase-credit terms are reported against the original CIF explicitly (not as a plug),
        # and any licence whose components do not reproduce the engine balance is flagged.
        other = _d(opening.get(lic.pk)) + _d(purchase_credit.get(lic.pk)) - original
        reconciles = abs((original + other - boe_cif - allot_cif - billed_cif) - avail) <= CIF_TOL
        licence_rows[lic.pk] = {
            "license_id": lic.pk, "license_number": lic.license_number, "sion": _licence_sion(lic),
            "company": getattr(lic.exporter, "name", None), "expiry_date": lic.license_expiry_date.isoformat() if lic.license_expiry_date else None,
            "purchase_status": getattr(lic.purchase_status, "code", None),
            "original_cif": _s(original), "boe_cif": _s(boe_cif), "allotment_cif": _s(allot_cif), "billed_cif": _s(billed_cif),
            # Opening-balance / purchase-credit components of the financial engine, shown explicitly (never hidden in a total).
            "other_adjustments_cif": _s(other), "components_reconcile": reconciles,
            "available_cif": _s(avail), "is_over_utilised": avail < DEC_0,
            "planned_cif": _s(planned), "final_balance_cif": _s(avail - planned),
            "utilisation_percent": _s(((original - avail) * 100 / original).quantize(Decimal("0.1"))) if original > 0 else None,
            "products": [],
        }

    products: dict[str, dict] = {}
    cells: dict[tuple[int, str], dict] = {}
    for lic in licences:
        sion = _licence_sion(lic)
        for item in lic.import_license.all():
            key, ident = _product_identity(item, sion)
            hsn = getattr(item.hs_code, "hs_code", None) if item.hs_code_id else None
            debited = sum((_d(r.qty) for r in usage.get(item.pk, {}).get("boes", [])), DEC_000)
            allotted = sum((_d(r.qty) for r in usage.get(item.pk, {}).get("allotments", [])), DEC_000)
            billed_q = _d(billed_qty.get(item.pk), DEC_000)
            qty = _d(item.quantity, DEC_000)
            item_plans = plans_by_item.get(item.pk, [])
            planned_qty = sum((_d(p.planned_quantity) for p in item_plans), DEC_000)
            planned_cif = sum((_d(p.planned_cif_fc) for p in item_plans), DEC_0)
            product = products.setdefault(key, {
                "key": key, **ident, "hsn_codes": set(), "aliases": set(), "source_records": [], "licence_ids": set(),
                "entitlement_qty": DEC_000, "allotted_qty": DEC_000, "debited_qty": DEC_000, "billed_qty": DEC_000,
                "balance_qty": DEC_000, "planned_qty": DEC_000, "planned_cif": DEC_0,
                "max_unit_price": prices.get((ident["item_name_id"], ident["sion"])) if ident["item_name_id"] else None,
            })
            if hsn:
                product["hsn_codes"].add(hsn)
            if item.description:
                product["aliases"].add(item.description.strip())
            product["licence_ids"].add(lic.pk)
            balance = qty - debited - allotted - billed_q
            for field, value in (("entitlement_qty", qty), ("allotted_qty", allotted), ("debited_qty", debited), ("billed_qty", billed_q),
                                 ("balance_qty", balance), ("planned_qty", planned_qty), ("planned_cif", planned_cif)):
                product[field] += value
            product["source_records"].append({
                "license_id": lic.pk, "license_number": lic.license_number, "import_item_id": item.pk,
                "serial_number": item.serial_number, "description": item.description, "hsn_code": hsn,
            })
            cell = cells.setdefault((lic.pk, key), {
                "license_id": lic.pk, "license_number": lic.license_number, "product_key": key, "product": ident["product"],
                "kind": ident["kind"], "mapping_basis": ident["mapping_basis"], "sion": ident["sion"],
                "entitlement_qty": DEC_000, "debited_qty": DEC_000, "allotted_qty": DEC_000, "billed_qty": DEC_000,
                "balance_qty": DEC_000, "planned_qty": DEC_000, "planned_cif": DEC_0, "import_item_ids": [],
                "max_unit_price": product["max_unit_price"],
                "references": {"boes": [], "allotments": []},
            })
            for field, value in (("entitlement_qty", qty), ("debited_qty", debited), ("allotted_qty", allotted), ("billed_qty", billed_q),
                                 ("balance_qty", balance), ("planned_qty", planned_qty), ("planned_cif", planned_cif)):
                cell[field] += value
            cell["import_item_ids"].append(item.pk)
            cell["references"]["boes"].extend(sorted({r.bill_of_entry.bill_of_entry_number for r in usage.get(item.pk, {}).get("boes", []) if r.bill_of_entry_id}))
            cell["references"]["allotments"].extend(sorted({f"ALT-{r.allotment_id}" for r in usage.get(item.pk, {}).get("allotments", [])}))

    status_counts: dict[str, int] = defaultdict(int)
    eligibility = []
    for (lid, key), cell in cells.items():
        licence = licence_rows[lid]
        status, reasons = _status({**cell, "balance_qty": cell["balance_qty"], "planned_qty": cell["planned_qty"]}, licence)
        status_counts[status] += 1
        out = {k: (_s(v) if isinstance(v, Decimal) else v) for k, v in cell.items()}
        out.update({"status": status, "reasons": reasons, "licence_available_cif": licence["available_cif"],
                    "licence_final_balance_cif": licence["final_balance_cif"],
                    "planning_eligible": status == UNDERUTILIZED})
        eligibility.append(out)
        licence["products"].append(key)
        prod = products[key]
        prod.setdefault("status_counts", defaultdict(int))[status] += 1

    product_rows = []
    for prod in products.values():
        prod_status = prod.pop("status_counts", {})
        product_rows.append({
            **{k: (_s(v) if isinstance(v, Decimal) else v) for k, v in prod.items() if k not in {"hsn_codes", "aliases", "licence_ids"}},
            "hsn_codes": sorted(prod["hsn_codes"]), "aliases": sorted(prod["aliases"]), "eligible_licences": len(prod["licence_ids"]),
            "source_record_count": len(prod["source_records"]), "status_counts": dict(prod_status),
            # Master-item grouping is authoritative (owner decision), but HSN codes from different
            # chapters under one master item are surfaced for review — never silently accepted.
            "hsn_chapters": sorted({h[:2] for h in prod["hsn_codes"] if h}),
            "mapping_review": (
                f"HSN codes span chapters {', '.join(sorted({h[:2] for h in prod['hsn_codes'] if h}))} — review the master-item links"
                if len({h[:2] for h in prod["hsn_codes"] if h}) > 1 else None
            ),
            "utilisation_percent": _s(((prod["entitlement_qty"] - prod["balance_qty"]) * 100 / prod["entitlement_qty"]).quantize(Decimal("0.1")))
            if prod["entitlement_qty"] > 0 else None,
        })
    product_rows.sort(key=lambda r: (r["kind"] != "MAPPED", r["sion"] or "", r["product"]))

    total = lambda field: sum((_d(r[field]) for r in licence_rows.values()), DEC_0)  # noqa: E731
    overview = {
        "licence_count": len(licence_rows),
        "original_cif": _s(total("original_cif")), "boe_cif": _s(total("boe_cif")), "allotment_cif": _s(total("allotment_cif")),
        "billed_cif": _s(total("billed_cif")), "other_adjustments_cif": _s(total("other_adjustments_cif")),
        "available_cif": _s(total("available_cif")), "planned_cif": _s(total("planned_cif")), "final_balance_cif": _s(total("final_balance_cif")),
        "utilisation_percent": _s(((total("original_cif") - total("available_cif")) * 100 / total("original_cif")).quantize(Decimal("0.1")))
        if total("original_cif") > 0 else None,
        "eligible_product_count": sum(1 for r in product_rows if r["kind"] == "MAPPED" and _d(r["balance_qty"]) > QTY_TOL),
        "underutilised_licence_count": len({c["license_id"] for c in eligibility if c["status"] == UNDERUTILIZED}),
        "warning_count": status_counts[WARNING] + status_counts[OVERPLANNED],
        "attention_product_count": sum(1 for r in product_rows if r["status_counts"].get(WARNING) or r["status_counts"].get(OVERPLANNED) or r["mapping_review"]),
        "status_counts": dict(status_counts),
        "consolidation": {
            "mapped": sum(1 for r in product_rows if r["kind"] == "MAPPED"),
            "ambiguous": sum(1 for r in product_rows if r["kind"] == "AMBIGUOUS"),
            "unmapped": sum(1 for r in product_rows if r["kind"] == "UNMAPPED"),
            "merged_source_records": sum(r["source_record_count"] for r in product_rows if r["kind"] == "MAPPED" and r["source_record_count"] > 1),
            "mapping_review": sum(1 for r in product_rows if r["mapping_review"]),
        },
    }
    overview["unreconciled_licence_count"] = sum(1 for r in licence_rows.values() if not r["components_reconcile"])
    overview["bases"] = {
        "licence": "Canonical LicenseBalanceCalculator (financial engine): allocation-aware BOE debit, BOE-netted outstanding allotments, billed without BOE, signed balance.",
        "item": "Item-level raw records: visible BOE debit rows, allotments not linked to a BOE, billed-without-BOE trade lines. Invoice representation and allocation netting are applied only at licence level.",
    }
    return {"report_version": "item-pivot-intelligence-v1", "overview": overview,
            "licences": list(licence_rows.values()), "products": product_rows, "eligibility": eligibility}


def recommend_for_licenses(license_ids: list[int], *, limit: int = 25) -> dict[str, Any]:
    """Read-only Auto Plan preview per licence (rolled back) vs. the existing plan.

    The planning engine decides every quantity / rate / split / CIF cap; this only
    reports what it would plan and how that differs from what is saved.
    """
    from apps.license.api.views.sion_planning_rule import SionPlanningRuleViewSet
    from apps.license.models import LicenseDetailsModel
    from apps.license.services.sion_planning_execution import SionPlanningExecutionService

    ids = list(dict.fromkeys(int(i) for i in license_ids))[:limit]
    available = LBC.calculate_financial_balance_for_licenses(ids)
    existing: dict[tuple[int, int | None], dict] = defaultdict(lambda: {"qty": DEC_000, "cif": DEC_0})
    for plan in LicenseItemPlan.objects.filter(license_id__in=ids, is_active=True, is_deleted=False, is_cancelled=False):
        bucket = existing[(plan.license_id, plan.item_name_id)]
        bucket["qty"] += _d(plan.planned_quantity)
        bucket["cif"] += _d(plan.planned_cif_fc)
    names = {}
    licences = {lic.pk: lic for lic in LicenseDetailsModel.objects.filter(pk__in=ids)}
    rows, errors = [], []
    for lid in ids:
        lic = licences.get(lid)
        if lic is None:
            continue
        from apps.core.models import ItemNameModel, SionNormClassModel
        _, sion_ids = SionPlanningRuleViewSet._resolve_sions_for_license(lid)
        for sion in SionNormClassModel.objects.filter(pk__in=sion_ids).order_by("norm_class"):
            sion_id = sion.pk
            try:
                with transaction.atomic():
                    result = SionPlanningExecutionService.plan_sion(sion, license_ids=[lid], persist=False, mode="ALL", force_plan=True)
                    transaction.set_rollback(True)
            except Exception as exc:  # noqa: BLE001 — surfaced per licence, never hidden
                errors.append({"license_id": lid, "sion_id": sion_id, "error": str(exc)[:300]})
                continue
            for licence_result in result.get("results", result.get("licenses", [])) if isinstance(result, dict) else []:
                for line in licence_result.get("lines", []):
                    item_name_id = line.get("item_name_id")
                    if item_name_id and item_name_id not in names:
                        names.update(dict(ItemNameModel.objects.filter(pk=item_name_id).values_list("pk", "name")))
                    qty, price = _d(line.get("requested_quantity")), _d(line.get("unit_price"))
                    provenance = line.get("allocation_provenance") or {}
                    cif = _d(provenance.get("operational_planned_cif"), qty * price)
                    prior = existing[(lid, item_name_id)]
                    rows.append({
                        "license_id": lid, "license_number": lic.license_number,
                        "expiry_date": lic.license_expiry_date.isoformat() if lic.license_expiry_date else None,
                        "sion_id": sion_id, "sion": sion.norm_class, "item_name_id": item_name_id, "product": names.get(item_name_id) or provenance.get("canonical_item_name"),
                        "rule_priority": line.get("planning_rule_priority"), "unit_price": _s(price),
                        "recommended_qty": _s(qty), "recommended_cif": _s(cif),
                        "existing_qty": _s(prior["qty"]), "existing_cif": _s(prior["cif"]),
                        "additional_qty": _s(qty - prior["qty"]), "additional_cif": _s(cif - prior["cif"]),
                        "licence_available_cif": _s(_d(available.get(lid))),
                        "cif_status": provenance.get("cif_status"),
                    })
    # Deterministic priority: licences expiring first (use entitlement before it lapses), then rule priority.
    rows.sort(key=lambda r: (r["expiry_date"] or "9999-12-31", r["license_number"], r["rule_priority"] if r["rule_priority"] is not None else 10**6))
    by_licence: dict[int, Decimal] = defaultdict(lambda: DEC_0)
    for rank, row in enumerate(rows, start=1):
        by_licence[row["license_id"]] += _d(row["recommended_cif"])
        row["rank"] = rank
        row["remaining_licence_cif_after"] = _s(_d(row["licence_available_cif"]) - by_licence[row["license_id"]])
        row["reason"] = (
            f"Auto Plan engine (rule priority {row['rule_priority']}) within licence available CIF {row['licence_available_cif']}; "
            f"licence expires {row['expiry_date'] or 'n/a'}"
        )
    alternatives: dict[Any, list] = defaultdict(list)
    for row in rows:
        alternatives[row["item_name_id"]].append(row["license_number"])
    for row in rows:
        row["alternatives"] = [n for n in alternatives[row["item_name_id"]] if n != row["license_number"]][:5]
    return {"read_only": True, "licence_count": len(ids), "recommendations": rows, "errors": errors}
