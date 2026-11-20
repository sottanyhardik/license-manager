"""Canonical data set for the item pivot report.

This deliberately consumes persisted effective plans and the item-linked usage
queries.  It is a report projection, not another planning engine.
"""
from collections import Counter, defaultdict
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from apps.license.models import LicenseItemPlan
from apps.license.services.item_usage import (
    get_item_usage_for_items,
    billed_no_boe_bulk_map,
    billed_no_boe_lines_bulk,
    billed_no_boe_qty_bulk_map,
)
from apps.license.services.c969_product_classifier import (
    C969_CATEGORY_ORDER,
    C969_CLASSIFIER_ORDER,
    C969_GENERIC_CATEGORIES,
    C969_NORM,
    UNRECOGNISED,
)
from apps.license.services.product_classification import E5_PRODUCT_CONDITIONS, classify_product, pivot_category_sort_key

ZERO_QTY = Decimal("0.000")
ZERO_CIF = Decimal("0.00")


def _decimal(value, default=Decimal("0")):
    return Decimal(str(value if value is not None else default))


def _add_balance_fields(row):
    """Per-item balance CIF and unit price: balance CIF / balance QTY, two decimals.

    Balance CIF is the item's CIF capacity less BOE-used, allotted and billed CIF,
    the same components that reduce balance QTY. The unit price is shown in the
    RUTILE block; it is None when no quantity is left.
    """
    used_cif = _decimal(row.get("boe_used_cif")) + _decimal(row.get("allotted_cif")) + _decimal(row.get("billed_cif"))
    balance_cif = max(_decimal(row.get("canonical_item_cif_capacity")) - used_cif, ZERO_CIF)
    balance_qty = _decimal(row.get("balance_qty"))
    row["balance_cif"] = _text(balance_cif)
    row["unit_price"] = _unit_price(balance_cif, balance_qty)


def _unit_price(balance_cif, balance_qty):
    """Balance CIF / balance QTY to two decimals (half up); None when no quantity is left."""
    qty = _decimal(balance_qty)
    if qty <= ZERO_QTY:
        return None
    return _text((_decimal(balance_cif) / qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _text(value):
    """JSON has no Decimal; retain exact values instead of converting to float."""
    return str(value)


QTY_PLACES = Decimal("0.001")
CIF_PLACES = Decimal("0.01")


def apportion(total, weights, places):
    """Split ``total`` between keys in proportion to ``weights`` (Decimal only) so the parts sum EXACTLY to ``total``.

    Rule (owner decisions D1/D3, 2026-11-20; largest-remainder rounding): every share is the proportional amount rounded
    DOWN to ``places``; the leftover units (each one ``places``) go one at a time to the keys with the largest discarded
    fraction, ties to the larger weight, then the lowest key (plan pk). Shares are never negative and never differ from
    the exact proportion by a unit or more. If every weight is 0 the split is equal. ``weights`` is a list of
    ``(key, weight)``; returns ``{key: share}``. 100.00 split 1:2 -> 33.33 + 66.67; 0.02 split 4 ways -> 0.01, 0.01, 0, 0."""
    total = _decimal(total)
    weights = [(key, max(_decimal(weight), Decimal("0"))) for key, weight in weights]
    if not weights:
        return {}
    weight_sum = sum((weight for _, weight in weights), Decimal("0"))
    if weight_sum <= 0:
        weights = [(key, Decimal("1")) for key, _ in weights]
        weight_sum = Decimal(len(weights))
    sign = Decimal("-1") if total < 0 else Decimal("1")
    magnitude = abs(total)
    exact = {key: magnitude * weight / weight_sum for key, weight in weights}
    shares = {key: value.quantize(places, rounding=ROUND_DOWN) for key, value in exact.items()}
    leftover = int(((magnitude - sum(shares.values(), Decimal("0"))) / places).to_integral_value(rounding=ROUND_DOWN))
    weight_of = dict(weights)
    order = sorted(shares, key=lambda key: (-(exact[key] - shares[key]), -weight_of[key], key))
    for key in order[:leftover]:
        shares[key] += places
    # An amount with more decimals than ``places`` (cif_fc 3 dp, qty_kg 4 dp) leaves a sub-unit residual the rounded
    # leftover cannot carry: it goes, exactly, to the first key so the parts always sum to the input (never negative).
    residual = magnitude - sum(shares.values(), Decimal("0"))
    if residual:
        shares[order[0]] += residual
    return {key: sign * share for key, share in shares.items()}


def _share_fraction(weight, weights):
    """Display fraction (6 dp string) of one key's weight in the split; equal when all weights are 0."""
    weights = [max(_decimal(w), Decimal("0")) for w in weights]
    total = sum(weights, Decimal("0"))
    weight = max(_decimal(weight), Decimal("0"))
    fraction = weight / total if total > 0 else Decimal("1") / Decimal(len(weights) or 1)
    return str(fraction.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _positive_issue(issue):
    """An exception is valid only when a canonical positive excess exists."""
    return (
        _decimal(issue.get("actual_excess_qty")) > ZERO_QTY
        or _decimal(issue.get("planned_excess_qty")) > ZERO_QTY
        or _decimal(issue.get("actual_excess_cif")) > ZERO_CIF
        or _decimal(issue.get("planned_excess_cif")) > ZERO_CIF
    )


def _merge_plan_cell(existing, candidate):
    """Coalesce plan lines targeting one canonical pivot identity.

    A split plan can legitimately contain several persisted rows for the
    same target/source item.  The report must not let the last row overwrite
    the earlier one.  Source rows are unique by import-item id; quantitative
    plan fields sum, while source usage/entitlement is counted once for a
    repeated source and once per distinct source.
    """
    existing_sources = {row["import_item_id"]: row for row in existing.get("source_items", [])}
    candidate_sources = {row["import_item_id"]: row for row in candidate.get("source_items", [])}
    new_source_ids = set(candidate_sources) - set(existing_sources)
    # N4: two apportioned (shared-entitlement) plans each add their own share of the same source.
    adds_entitlement = bool(new_source_ids) or bool(existing.get("entitlement_apportioned") and candidate.get("entitlement_apportioned"))
    # Identity parts mirror exactly what this merge adds: entitlement only for new sources, usage and plan always.
    parts = [dict(part) for part in candidate.get("identity_parts", [])]
    if not adds_entitlement:
        for part in parts:
            part.update({field: "0" for field in _PART_ENTITLEMENT_FIELDS if field in part})
    existing["identity_parts"] = [*existing.get("identity_parts", []), *parts]
    for trace_field in ("apportioned_rows", "usage_rows"):
        if existing.get(trace_field) is not None or candidate.get(trace_field) is not None:
            existing[trace_field] = [*(existing.get(trace_field) or []), *(candidate.get(trace_field) or [])]
    existing_sources.update(candidate_sources)
    existing["source_items"] = [existing_sources[key] for key in sorted(existing_sources)]

    for field in ("plan_qty", "planned_cif", "effective_planned_qty", "effective_planned_cif"):
        existing[field] = _text(_decimal(existing.get(field)) + _decimal(candidate.get(field)))

    # Usage is transaction-deduplicated by the caller (each BOE / allotment row and billed item is carried by exactly
    # one cell of the licence), so a candidate's usage is always new to this cell and is always added.
    for field in _USAGE_FIELDS:
        existing[field] = _text(_decimal(existing.get(field)) + _decimal(candidate.get(field)))

    # Repeated split rows have the same source entitlement/usage, so retain
    # it once.  Distinct source rows contribute their own independently
    # reconciled quantities and CIFs.
    if adds_entitlement:
        for field in (
            "total_qty", "percentage_target_qty", "own_excess_qty",
            "excess_other_item_qty", "adjusted_total_qty", "balance_qty",
            "canonical_item_cif_capacity", "item_total_cif",
        ):
            existing[field] = _text(_decimal(existing.get(field)) + _decimal(candidate.get(field)))
        if existing.get("available_cif") is not None and candidate.get("available_cif") is not None:
            existing["available_cif"] = _text(_decimal(existing["available_cif"]) + _decimal(candidate["available_cif"]))
    else:
        # Same sources (entitlement held once): the candidate's own new usage still consumes the shared balance.
        used_qty = sum((_decimal(candidate.get(f)) for f in ("debited_qty", "allotted_qty", "billed_qty")), ZERO_QTY)
        existing["balance_qty"] = _text(max(_decimal(existing.get("balance_qty")) - used_qty, ZERO_QTY))

    hsn_codes = [row.get("hsn_code") for row in existing["source_items"] if row.get("hsn_code")]
    descriptions = [row.get("description") for row in existing["source_items"] if row.get("description")]
    # Normalize descriptions: strip whitespace and ignore case for deduplication.
    # If all descriptions are the same after normalization, show one; otherwise join with comma.
    if hsn_codes:
        unique_hsns = list(dict.fromkeys(hs.strip() for hs in hsn_codes if hs.strip()))
        existing["hsn_code"] = unique_hsns[0] if len(unique_hsns) == 1 else ", ".join(unique_hsns)
    else:
        existing["hsn_code"] = ""
    if descriptions:
        # Normalize by stripping whitespace and lowercasing for comparison
        normalized = [desc.strip() for desc in descriptions if desc.strip()]
        # Deduplicate while preserving order; ignore case for comparison
        seen = set()
        unique_descs = []
        for desc in normalized:
            key = desc.lower()
            if key not in seen:
                seen.add(key)
                unique_descs.append(desc)
        existing["description"] = unique_descs[0] if len(unique_descs) == 1 else ", ".join(unique_descs)
    else:
        existing["description"] = ""
    return existing


_CATEGORY_NAMES = frozenset(condition["name"] for condition in E5_PRODUCT_CONDITIONS)


def _plan_source_ids(plan) -> tuple[int, ...]:
    provenance = plan.allocation_provenance or {}
    return tuple(sorted({int(s) for s in provenance.get("source_item_ids", []) if str(s).isdigit()} or {plan.import_item_id}))


_PERCENT_STRATEGIES = {"SPLIT_BY_PERCENT", "SPLIT_BY_PERCENTAGE"}


def _is_percentage(plan) -> bool:
    return (plan.allocation_provenance or {}).get("strategy") in _PERCENT_STRATEGIES


def _split_source_targets(plans) -> dict:
    """source item id → canonical targets, for percentage splits only: several targets planned from the same source rows
    (each target owns a percentage share). STANDARD / unit-value plans keep the existing one-cell merge."""
    targets_by_sources = defaultdict(set)
    for plan in plans:
        if plan.item_name_id and _is_percentage(plan):
            targets_by_sources[_plan_source_ids(plan)].add(plan.item_name_id)
    out = defaultdict(set)
    for sources, targets in targets_by_sources.items():
        if len(targets) > 1:
            for source_id in sources:
                out[source_id] |= targets
    return out


def _canonical_categories(licenses, plans_by_license) -> dict:
    """(Item Name id, SION) → the product category its single-target plans get in this report (most common; ties by
    name). A split target (one percentage share of a source shared with other targets) is keyed by it, so one canonical
    Item Name never appears under a category derived from another target's source description."""

    counts = defaultdict(Counter)
    for license_obj in licenses:
        plans = plans_by_license.get(license_obj.id, [])
        if not plans:
            continue
        split = _split_source_targets(plans)
        default_sion = next((e.norm_class.norm_class for e in license_obj.export_license.all() if e.norm_class_id), "")
        if default_sion == "C969":
            continue
        items = {item.id: item for item in license_obj.import_license.all()}
        for plan in plans:
            sources = _plan_source_ids(plan)
            if not plan.item_name_id or any(len(split.get(source_id, ())) > 1 for source_id in sources):
                continue
            source_items = [items[i] for i in sources if i in items]
            description = next((i.description for i in source_items if i.description), plan.item_name.name)
            hsn = next((i.hs_code.hs_code for i in source_items if i.hs_code_id), "")
            category = classify_product(hsn, description, default_sion)
            if category:
                sion = (plan.allocation_provenance or {}).get("sion") or default_sion
                counts[(plan.item_name_id, sion)][category] += 1
    return {key: sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] for key, counter in counts.items()}


def _split_target_category(target_name: str):
    """Fallback category of ONE canonical target of a split source (several targets planned from the same import rows)
    when the report has no single-target plan of that Item Name: the Item Name itself (it is a category label, or its
    own column). The shared source's HSN is NOT used — it describes the mixed source, not this target (an HSN-1511
    source split to PALM KERNEL OIL would otherwise be labelled RBD PAL)."""
    name = (target_name or "").strip().upper()
    return name or None


UNATTRIBUTED_CATEGORY = "NOT ATTRIBUTED (TARGET MISSING)"


_USAGE_FIELDS = ("debited_qty", "boe_used_cif", "allotted_qty", "allotted_cif", "billed_qty", "billed_cif")


_PART_ENTITLEMENT_FIELDS = ("total_qty", "adjusted_total_qty", "canonical_item_cif_capacity", "item_total_cif")
_PART_SUM_FIELDS = _PART_ENTITLEMENT_FIELDS + _USAGE_FIELDS + ("plan_qty", "planned_cif", "effective_planned_qty", "effective_planned_cif")
_PART_META_FIELDS = ("product_category", "sion", "planning_priority", "priority_item_order", "planning_rule_id", "planning_rule_name",
                     "planning_strategy", "priority_source")


def _identity_part(cell, *, canonical_item_id, item_name, reason=None):
    """One canonical identity's own contribution to a matrix cell (Item Name × SION, or an explicit unmapped identity).

    Matrix cells are keyed by product category and may merge several Item Names; the Item Summary aggregates these
    parts instead, so an item is never credited with another item's rows. ``reason`` marks a source that has no single
    Item Name (``no_item_name`` / ``ambiguous_item_name`` / ``plan_without_item_name``)."""
    return {"canonical_item_id": canonical_item_id, "item_name": item_name, "reason": reason,
            "hsn_codes": sorted({hs.strip() for row in cell.get("source_items", []) for hs in str(row.get("hsn_code") or "").split(",") if hs.strip()}),
            "source_items": [{k: row.get(k) for k in ("import_item_id", "serial_number", "hsn_code", "description", "unit", "quantity", "cif_fc")} for row in cell.get("source_items", [])],
            **{field: cell.get(field) for field in _PART_META_FIELDS},
            **{field: cell[field] for field in _PART_SUM_FIELDS if cell.get(field) is not None},
            **{field: list(cell[field]) for field in ("apportioned_rows", "usage_rows") if cell.get(field) is not None}}


def _row_index(usage) -> dict:
    """("BOE" | "ALLOTMENT", row pk) → (row, header planning target id): the transaction identity used for attribution."""
    index = {}
    for values in usage.values():
        for row in values.get("boes", []):
            index[("BOE", row.pk)] = (row, getattr(getattr(row, "bill_of_entry", None), "planning_target_item_id", None))
        for row in values.get("allotments", []):
            index[("ALLOTMENT", row.pk)] = (row, getattr(getattr(row, "allotment", None), "planning_target_item_id", None))
    return index


def _sum_rows(keys, index):
    """(boe qty, boe cif, allotment qty, allotment cif) of exactly these transaction rows."""
    totals = [ZERO_QTY, ZERO_CIF, ZERO_QTY, ZERO_CIF]
    for kind, pk in keys:
        row = index[(kind, pk)][0]
        offset = 0 if kind == "BOE" else 2
        totals[offset] += _decimal(row.qty)
        totals[offset + 1] += _decimal(row.cif_fc)
    return tuple(totals)


def _sum_entries(entries):
    """(boe qty, boe cif, allotment qty, allotment cif) of apportioned/whole transaction entries ``(kind, pk, qty, cif, share)``."""
    totals = [ZERO_QTY, ZERO_CIF, ZERO_QTY, ZERO_CIF]
    for kind, _pk, qty, cif, _share in entries:
        offset = 0 if kind == "BOE" else 2
        totals[offset] += qty
        totals[offset + 1] += cif
    return tuple(totals)


def _resolve_source_ids(plan, item_by_id):
    """The plan's source import items, restricted to this licence's own items (a provenance id of another licence's item
    never reads that licence's transactions into this licence's cells)."""
    provenance = plan.allocation_provenance or {}
    source_ids = [int(source_id) for source_id in provenance.get("source_item_ids", []) if str(source_id).isdigit()] or [plan.import_item_id]
    return ([source_id for source_id in dict.fromkeys(source_ids) if source_id in item_by_id]
            or [source_id for source_id in (plan.import_item_id,) if source_id in item_by_id])


def _trace_row(kind, row, header, import_item_id, qty, cif, share):
    """One transaction row carried by a cell (drill-down trace; only built when the report is generated with trace_rows)."""
    parent = getattr(row, header, None)
    if kind == "BOE":
        ref = {"number": getattr(parent, "bill_of_entry_number", "") or "", "date": getattr(parent, "bill_of_entry_date", None)}
    else:
        ref = {"number": (getattr(parent, "invoice", None) or getattr(parent, "item_name", "") or ""), "date": None}
    return {"kind": kind, "row_id": row.pk, "record_id": getattr(row, f"{header}_id", None), "import_item_id": import_item_id,
            "reference": ref["number"], "date": ref["date"].isoformat() if ref["date"] else None,
            "qty": _text(qty), "cif": _text(cif), "share": share}


def _usage_row_keys(usage, item_ids, target_id=None, unmapped_only=False):
    """("BOE" | "ALLOTMENT", row pk) of the usage rows on ``item_ids``; only rows whose header holds ``target_id`` when given
    (the persisted planning-target mapping the item cell reads through ``mapped_usage``); with ``unmapped_only`` only rows
    whose header has NO planning target (owner decision D2: the legacy fallback never takes a row mapped to some item)."""
    keys = []
    for item_id in dict.fromkeys(item_ids):  # a source listed twice is still one set of transactions
        values = usage.get(item_id, {})
        for kind, rows, header in (("BOE", values.get("boes", []), "bill_of_entry"), ("ALLOTMENT", values.get("allotments", []), "allotment")):
            keys.extend((kind, row.pk) for row in rows
                        if (not unmapped_only or getattr(getattr(row, header, None), "planning_target_item_id", None) is None)
                        and (target_id is None or getattr(getattr(row, header, None), "planning_target_item_id", None) == target_id))
    return keys


_USAGE_TO_CELL = (("boe_qty", "debited_qty"), ("boe_cif", "boe_used_cif"), ("allot_qty", "allotted_qty"), ("allot_cif", "allotted_cif"),
                  ("billed_qty", "billed_qty"), ("billed_cif", "billed_cif"))


def _unattributed_cell(sion, amounts, records):
    """Actual licence usage (BOE debits / outstanding allotments) on this licence's import items that no item cell
    carries — e.g. a BOE / allotment on a split source with no planning target yet. Shown as its own row so the Item
    Summary reconciles with the source records; never attributed to a guessed item. No entitlement, plan or capacity."""
    zero_q, zero_c = _text(ZERO_QTY), _text(ZERO_CIF)
    return {
        "canonical_item_id": None, "item_name": UNATTRIBUTED_CATEGORY, "sion": sion, "product_category": UNATTRIBUTED_CATEGORY,
        "hsn_code": "", "description": "BOE / allotment / billed usage no planned item carries (no planning target, or a target not planned on this licence) — map it in Mapping → BOE / Allotment",
        "unattributed": True, "unattributed_records": records,
        "total_qty": zero_q, "adjusted_total_qty": zero_q, "percentage_target_qty": zero_q, "own_excess_qty": zero_q, "excess_other_item_qty": zero_q,
        "debited_qty": _text(amounts["debited_qty"]), "boe_used_cif": _text(amounts["boe_used_cif"]),
        "allotted_qty": _text(amounts["allotted_qty"]), "allotted_cif": _text(amounts["allotted_cif"]),
        "billed_qty": _text(amounts["billed_qty"]), "billed_cif": _text(amounts["billed_cif"]), "balance_qty": zero_q, "plan_qty": zero_q, "planned_cif": zero_c,
        "effective_planned_qty": zero_q, "effective_planned_cif": zero_c, "has_item_cif_cap": False, "has_explicit_item_cif_cap": False,
        "item_cif_cap": None, "canonical_item_cif_capacity": zero_c, "available_cif": None, "restriction_percent": None, "restriction_value": None,
        "planning_priority": None, "planning_rule_id": None, "planning_rule_name": None, "planning_strategy": None, "priority_item_order": None,
        "priority_source": "unattributed", "source_items": [],
    }


CIF_TOLERANCE = Decimal("0.01")
QTY_TOLERANCE = Decimal("0.001")


def _group_reconciliation(group):
    """Licence Summary vs Item Summary, licence by licence (differences never cancel across licences).

    CIF: each licence's canonical allotted / debited / billed / planned CIF (balance engine; planned = active plan lines)
    vs the sum of its item cells incl. NOT ATTRIBUTED. Quantity: each licence's source BOE / allotment / billed rows vs
    the quantities its item cells carry (transaction-level attribution). A group is reconciled only when every licence
    is within tolerance on every metric; the group totals are informational."""
    metrics = (("allotted_cif", "allotted_cif"), ("debited_cif", "boe_used_cif"), ("billed_cif", "billed_cif"), ("planned_cif", "planned_cif"))
    licences = group["licenses"]
    out = {"license_ids": sorted(row["license_id"] for row in licences), "metrics": {}, "quantity_metrics": {},
           "tolerance": {"cif": _text(CIF_TOLERANCE), "qty": _text(QTY_TOLERANCE)}}
    unreconciled = set()
    for licence_field, cell_field in metrics:
        upper = lower = ZERO_CIF
        by_licence = []
        for row in licences:
            lic_upper = _decimal(row[licence_field])
            lic_lower = sum((_decimal(cell.get(cell_field)) for cell in row["items"].values()), ZERO_CIF)
            upper, lower = upper + lic_upper, lower + lic_lower
            if abs(lic_upper - lic_lower) >= CIF_TOLERANCE:
                unreconciled.add(row["license_id"])
                by_licence.append({"license_id": row["license_id"], "license_number": row["license_number"], "licence_summary": _text(lic_upper),
                                   "item_summary": _text(lic_lower), "difference": _text(lic_upper - lic_lower)})
        out["metrics"][licence_field] = {"licence_summary": _text(upper.quantize(CIF_TOLERANCE)), "item_summary": _text(lower.quantize(CIF_TOLERANCE)),
                                         "difference": _text((upper - lower).quantize(CIF_TOLERANCE)), "licences": by_licence}
    for field in ("debited_qty", "allotted_qty", "billed_qty"):
        upper = lower = ZERO_QTY
        by_licence = []
        for row in licences:
            recon = row.get("item_reconciliation") or {}
            lic_upper = _decimal((recon.get("source_usage") or {}).get(field))
            lic_lower = _decimal((recon.get("carried_by_items") or {}).get(field))
            upper, lower = upper + lic_upper, lower + lic_lower
            if abs(lic_upper - lic_lower) >= QTY_TOLERANCE:
                unreconciled.add(row["license_id"])
                by_licence.append({"license_id": row["license_id"], "license_number": row["license_number"], "source_rows": _text(lic_upper),
                                   "item_summary": _text(lic_lower), "difference": _text(lic_upper - lic_lower)})
        out["quantity_metrics"][field] = {"source_rows": _text(upper), "item_summary": _text(lower), "difference": _text(upper - lower), "licences": by_licence}
    out["unreconciled_license_count"] = len(unreconciled)
    out["reconciled"] = not unreconciled
    # Known definition differences (reported, never forced to zero): the licence figures exclude BOEs already represented
    # by invoices and net allotments covered by BOE allocations; the item cells are built from the raw rows.
    out["definitions"] = "Licence Summary: canonical balance engine (allocation-aware BOE debit, BOE-netted allotment). Item Summary: BOE / allotment / billed rows per item, each transaction once."
    out["not_attributed_records"] = [rec for row in licences for cell in row["items"].values() if cell.get("unattributed")
                                     for rec in cell.get("unattributed_records", [])]
    return out


class ItemPivotService:
    """Build a notification/purchase-status → licence → item matrix."""

    @classmethod
    def build(cls, licenses, trace_rows=False):
        """``trace_rows`` additionally puts every carried transaction row on its cell / identity part (``usage_rows``) so
        the product drill-down can trace a figure to its BOE / allotment / invoice rows; off by default (payload size)."""
        licenses = list(licenses)
        ids = [license_obj.id for license_obj in licenses]
        plans = list(
            LicenseItemPlan.objects.filter(
                license_id__in=ids,
                is_active=True,
                is_deleted=False,
                is_cancelled=False,
            )
            .select_related("item_name", "import_item", "planning_rule")
            .order_by("planning_rule_priority", "id")
        )
        plans_by_license = defaultdict(list)
        for plan in plans:
            plans_by_license[plan.license_id].append(plan)

        usage = get_item_usage_for_items(
            item.id for license_obj in licenses for item in license_obj.import_license.all()
        )
        # Licence-level CIF comes from the canonical balance engine (owner decision
        # 2026-11-18): allocation-aware BOE debit, BOE-netted outstanding allotments,
        # billed-without-BOE, and the signed financial balance (never floored).
        from apps.license.services.balance_calculator import LicenseBalanceCalculator
        canonical_debit = LicenseBalanceCalculator.calculate_debit_for_licenses(ids)
        canonical_allotment = LicenseBalanceCalculator.calculate_allotment_for_licenses(ids)
        canonical_billed = LicenseBalanceCalculator.calculate_trade_for_licenses(ids)
        canonical_balance = LicenseBalanceCalculator.calculate_financial_balance_for_licenses(ids)
        # Mapping is read from the persisted BOE/allotment target relationship
        # while the canonical allocation rows are still unique.  This is one
        # batched usage population for the entire report, never one query per
        # pivot cell or licence.
        mapped_usage = defaultdict(lambda: {"boe_used_quantity": ZERO_QTY, "boe_used_cif": ZERO_CIF, "unlinked_allotment_quantity": ZERO_QTY, "unlinked_allotment_cif": ZERO_CIF})
        for source_id, values in usage.items():
            for row in values["boes"]:
                target_id = getattr(row.bill_of_entry, "planning_target_item_id", None)
                if target_id:
                    mapped_usage[(source_id, target_id)]["boe_used_quantity"] += _decimal(row.qty)
                    mapped_usage[(source_id, target_id)]["boe_used_cif"] += _decimal(row.cif_fc)
            for row in values["allotments"]:
                target_id = getattr(row.allotment, "planning_target_item_id", None)
                if target_id:
                    mapped_usage[(source_id, target_id)]["unlinked_allotment_quantity"] += _decimal(row.qty)
                    mapped_usage[(source_id, target_id)]["unlinked_allotment_cif"] += _decimal(row.cif_fc)

        row_index = _row_index(usage)
        # Item Name links per import item regardless of norm (one query): tells "no Item Name at all" apart from "linked
        # only to Item Names not valid for this norm" when the report's norm-scoped prefetch shows none.
        from apps.license.models import LicenseImportItemsModel
        linked_name_counts = Counter(LicenseImportItemsModel.items.through.objects.filter(
            licenseimportitemsmodel_id__in=[item.id for lic in licenses for item in lic.import_license.all()]
        ).values_list("licenseimportitemsmodel_id", flat=True))

        # The same per-import-item row lists are used repeatedly below: once
        # for the licence roll-up and again for every plan that falls back to
        # its source item usage.  Aggregate them once here rather than
        # traversing the BOE/allotment rows for every plan cell.  Decimal
        # addition is exact, so this is a projection-only performance change.
        usage_totals = {
            item_id: {
                "boe_qty": sum((_decimal(row.qty) for row in values["boes"]), ZERO_QTY),
                "boe_cif": sum((_decimal(row.cif_fc) for row in values["boes"]), ZERO_CIF),
                "allot_qty": sum((_decimal(row.qty) for row in values["allotments"]), ZERO_QTY),
                "allot_cif": sum((_decimal(row.cif_fc) for row in values["allotments"]), ZERO_CIF),
            }
            for item_id, values in usage.items()
        }

        # Fetch billed (no BOE) quantity and CIF for all import items in one
        # batched query each — same source as the Customs Ledger "Billed (No BOE)"
        # fields: SALE trade lines with no BOE attached.
        all_import_item_ids = list(usage_totals.keys())
        billed_no_boe_cif_map = billed_no_boe_bulk_map(all_import_item_ids) if all_import_item_ids else {}
        billed_no_boe_qty_map = billed_no_boe_qty_bulk_map(all_import_item_ids) if all_import_item_ids else {}
        for item_id in all_import_item_ids:
            usage_totals[item_id]["billed_qty"] = _decimal(billed_no_boe_qty_map.get(item_id, 0))
            usage_totals[item_id]["billed_cif"] = _decimal(billed_no_boe_cif_map.get(item_id, 0))
        # Row-level billed-without-BOE lines (same filter): needed to apportion a percentage-split source's billed per line
        # (D3) and to trace invoices. One query, only when a split plan or a trace needs them.
        needs_billed_lines = trace_rows or any(_is_percentage(plan) for plan in plans)
        billed_lines = billed_no_boe_lines_bulk(all_import_item_ids) if needs_billed_lines and all_import_item_ids else {}

        # Load active SION planning rules so we can look up cif_restriction_percentage
        # per item.  We'll build a map: {sion_norm: {item_name_id: restriction_pct}}.
        from apps.license.models import SionPlanningRule
        active_rules = list(
            SionPlanningRule.objects.filter(is_active=True)
            .select_related("sion")
            .prefetch_related("unit_value_rows", "percentage_rows")
        )
        cif_restriction_by_sion_item = defaultdict(dict)  # {sion_norm: {item_name_id: pct}}
        for rule in active_rules:
            sion_norm = rule.sion.norm_class if rule.sion_id else None
            if not sion_norm:
                continue
            rule_pct = rule.cif_restriction_percentage
            # STANDARD strategy: restriction is on the rule's import_item
            if rule.strategy == "STANDARD" and rule.import_item_id:
                cif_restriction_by_sion_item[sion_norm][rule.import_item_id] = rule_pct
            # SPLIT_BY_UNIT_VALUE: each row has its own import_item and restriction
            if rule.strategy == "SPLIT_BY_UNIT_VALUE":
                for row in rule.unit_value_rows.all():
                    row_pct = row.cif_restriction_percentage if row.cif_restriction_percentage is not None else rule_pct
                    if row.import_item_id and row_pct is not None:
                        cif_restriction_by_sion_item[sion_norm][row.import_item_id] = row_pct
            # SPLIT_BY_PERCENT: each row has its own import_item and restriction
            if rule.strategy == "SPLIT_BY_PERCENT":
                for row in rule.percentage_rows.all():
                    row_pct = row.cif_restriction_percentage if row.cif_restriction_percentage is not None else rule_pct
                    if row.import_item_id and row_pct is not None:
                        cif_restriction_by_sion_item[sion_norm][row.import_item_id] = row_pct
            # Also store rule-level restriction for STANDARD when no import_item match
            # (the rule-level restriction applies to all items matched by the rule)
            if rule.strategy == "STANDARD" and rule_pct is not None and not rule.import_item_id:
                cif_restriction_by_sion_item[sion_norm]["__rule__"] = rule_pct
        output_groups = defaultdict(lambda: {"licenses": [], "item_groups": {}})

        # Imported once for the complete projection rather than once per
        # pivot cell.  Import caching makes the old code correct, but this
        # keeps large result sets from repeatedly resolving the module.
        from apps.license.services.item_pivot_item_summary import (
            PLANNING_QTY_TOLERANCE,
            determine_planning_status,
            project_item_summary,
        )

        canonical_category = _canonical_categories(licenses, plans_by_license)
        for license_obj in licenses:
            import_items = list(license_obj.import_license.all())
            item_by_id = {item.id: item for item in import_items}
            export_items = list(license_obj.export_license.all())
            default_sion = next(
                (getattr(item.norm_class, "norm_class", "") for item in export_items if item.norm_class_id),
                "",
            )
            total_cif = sum((_decimal(item.cif_fc) for item in export_items), ZERO_CIF)
            debited_cif = _decimal(canonical_debit.get(license_obj.id))
            allotted_cif = _decimal(canonical_allotment.get(license_obj.id))
            # Licence-level billed (canonical engine); never reused by the plan loop below (Opus B1, 2026-11-20).
            licence_billed_cif = _decimal(canonical_billed.get(license_obj.id))
            licence_balance_cif = _decimal(canonical_balance.get(license_obj.id))
            cells = {}
            planned_cif = ZERO_CIF

            # Look up CIF restriction map for this license's SION norm
            license_cif_restriction_map = cif_restriction_by_sion_item.get(default_sion, {})

            # Several canonical targets planned from the same source rows (a split) are separate items: each keeps its
            # own share. Keying them by the shared source description merged them into one cell, and the merge kept the
            # repeated source once — the other targets' shares vanished from the report (PKO / OLIVE OIL, 2026-11-19).
            split_sources = _split_source_targets(plans_by_license[license_obj.id])
            split_key_owner = {}
            plan_keys = {}
            # Transaction-level attribution: every BOE / allotment row and every billed-without-BOE item of the licence is
            # carried by at most one item cell; whatever no cell carries is reported once as NOT ATTRIBUTED (below).
            carried_rows, carried_billed = set(), set()
            planned_targets_by_source = defaultdict(set)
            for licence_plan in plans_by_license[license_obj.id]:
                if licence_plan.item_name_id:
                    for source_id in _plan_source_ids(licence_plan):
                        planned_targets_by_source[source_id].add(licence_plan.item_name_id)
            licence_plans = plans_by_license[license_obj.id]
            resolved_sources = {licence_plan.id: _resolve_source_ids(licence_plan, item_by_id) for licence_plan in licence_plans}

            def _is_split_target(candidate_plan):
                return bool(default_sion != "C969" and candidate_plan.item_name_id and _is_percentage(candidate_plan)
                            and any(len(split_sources.get(source_id, ())) > 1 for source_id in _plan_source_ids(candidate_plan)))

            # --- D1 (owner decision 2026-11-20): STANDARD plans on the same source(s) whose targets have no usage mapped to
            # them fall back to the source's UNMAPPED rows (header without a planning target — D2: never a row mapped to some
            # item). Two or more such plans share each row in proportion to their planned CIF; a row is counted once in total.
            fallback_plan_ids, fallback_by_row = set(), defaultdict(list)
            for fallback_plan in licence_plans:
                if _is_percentage(fallback_plan):
                    continue
                # A plan carries its own mapped rows whenever ANY row (even 0 qty with CIF) is mapped to its target — only
                # plans with no such row fall back (Opus N2, 2026-11-20: eligibility was tested on mapped quantity only).
                # A STANDARD plan without an Item Name has no target, so it is fallback-eligible (unmapped rows only).
                if fallback_plan.item_name_id and _usage_row_keys(usage, resolved_sources[fallback_plan.id], target_id=fallback_plan.item_name_id):
                    continue
                fallback_plan_ids.add(fallback_plan.id)
                for row_key in _usage_row_keys(usage, resolved_sources[fallback_plan.id], unmapped_only=True):
                    if fallback_plan.id not in fallback_by_row[row_key]:
                        fallback_by_row[row_key].append(fallback_plan.id)
            plan_by_id = {licence_plan.id: licence_plan for licence_plan in licence_plans}
            fallback_entries = defaultdict(list)  # plan id -> [(kind, row pk, qty, cif, share or None)]
            for row_key, plan_ids in fallback_by_row.items():
                row = row_index[row_key][0]
                if len(plan_ids) == 1:
                    fallback_entries[plan_ids[0]].append((row_key[0], row_key[1], _decimal(row.qty), _decimal(row.cif_fc), None))
                    continue
                weights = [(plan_id, _decimal(plan_by_id[plan_id].planned_cif_fc)) for plan_id in plan_ids]
                qty_shares, cif_shares = apportion(row.qty, weights, QTY_PLACES), apportion(row.cif_fc, weights, CIF_PLACES)
                for plan_id, weight in weights:
                    fallback_entries[plan_id].append((row_key[0], row_key[1], qty_shares[plan_id], cif_shares[plan_id],
                                                      _share_fraction(weight, [w for _, w in weights])))

            # --- N4 (owner decision 2026-11-20): where D1 shares a source between two or more fallback STANDARD plans, the
            # source's ENTITLEMENT (Total Qty and item CIF) is shared by the same planned-CIF weights (same remainder rule), so
            # each product's balance reflects its own share and the shares add back to the source exactly.
            fallback_by_source = defaultdict(list)
            for fallback_plan in licence_plans:
                if fallback_plan.id in fallback_plan_ids:
                    for source_id in resolved_sources[fallback_plan.id]:
                        fallback_by_source[source_id].append(fallback_plan.id)
            shared_qty, shared_cif = defaultdict(dict), defaultdict(dict)  # plan id -> {source id: entitlement share}
            for source_id, plan_ids in fallback_by_source.items():
                if len(plan_ids) < 2:
                    continue
                weights = [(plan_id, _decimal(plan_by_id[plan_id].planned_cif_fc)) for plan_id in plan_ids]
                qty_shares = apportion(item_by_id[source_id].quantity, weights, QTY_PLACES)
                cif_shares = apportion(item_by_id[source_id].cif_fc, weights, CIF_PLACES)
                for plan_id in plan_ids:
                    shared_qty[plan_id][source_id], shared_cif[plan_id][source_id] = qty_shares[plan_id], cif_shares[plan_id]

            # --- D3 (owner decision 2026-11-20): billed-without-BOE on a percentage-split source is apportioned to each split
            # target by its split percentage (normalised over the targets, so the parts sum to the source); one holder plan
            # per (target, source) carries the share; remainder rule as D1; lowest plan pk breaks ties.
            # N3: the weights are the targets of the EXACT split group (plans sharing the same source set), never every
            # percentage plan touching the source. N1: a source in a split group is claimed by that group BEFORE the plan loop —
            # its billed always goes to the split targets (a STANDARD plan on the same source takes none), whatever the plan
            # order. A source in several groups (partial overlap) is claimed by the group with the lowest plan pk.
            split_groups = {}  # source-set -> {"targets": {target: [pct, tiebreak pk, holder plan id]}, "first_pk": lowest plan pk}
            for split_plan in licence_plans:
                if not _is_split_target(split_plan):
                    continue
                group_info = split_groups.setdefault(_plan_source_ids(split_plan), {"targets": {}, "first_pk": split_plan.id})
                group_info["first_pk"] = min(group_info["first_pk"], split_plan.id)
                pct = _decimal((split_plan.allocation_provenance or {}).get("percentage", 0))
                target = group_info["targets"].setdefault(split_plan.item_name_id, [pct, split_plan.id, split_plan.id])
                target[0], target[1] = max(target[0], pct), min(target[1], split_plan.id)
            claiming_group = {}  # source id -> split-group key
            for group_key, group_info in sorted(split_groups.items(), key=lambda kv: kv[1]["first_pk"]):
                for source_id in group_key:
                    if source_id in item_by_id:
                        claiming_group.setdefault(source_id, group_key)
            split_billed = defaultdict(list)  # (holder plan id, source id) -> [(line, qty share, cif share, fraction)]
            split_cif = defaultdict(lambda: ZERO_CIF)  # holder plan id -> its apportioned share of its sources' CIF
            for source_id, group_key in claiming_group.items():
                targets = split_groups[group_key]["targets"]
                weights = [(info[1], info[0]) for info in targets.values()]
                holder_of = {info[1]: info[2] for info in targets.values()}
                fractions = {key: _share_fraction(weight, [w for _, w in weights]) for key, weight in weights}
                for key, cif_share in apportion(item_by_id[source_id].cif_fc, weights, CIF_PLACES).items():
                    split_cif[holder_of[key]] += cif_share
                for line in billed_lines.get(source_id, []):
                    qty_shares, cif_shares = apportion(line["qty"], weights, QTY_PLACES), apportion(line["cif"], weights, CIF_PLACES)
                    for key, _weight in weights:
                        split_billed[(holder_of[key], source_id)].append((line, qty_shares[key], cif_shares[key], fractions[key]))

            for plan in plans_by_license[license_obj.id]:
                provenance = plan.allocation_provenance or {}
                rule = plan.planning_rule
                planning_priority = plan.planning_rule_priority
                if planning_priority is None and rule and rule.is_active:
                    planning_priority = rule.priority
                priority_item_order = provenance.get("unit_value_row_priority")
                if priority_item_order is None:
                    priority_item_order = provenance.get("member_sequence", plan.id)
                item_name = (plan.item_name.name if plan.item_name_id else provenance.get("canonical_item_name")) or "UNMAPPED ITEM"
                sion = provenance.get("sion") or default_sion
                # Only this licence's import items: a provenance id of another licence's item never reads that
                # licence's transactions into this licence's cells (they would be counted on both licences).
                source_ids = resolved_sources[plan.id]
                source_items = [item_by_id[source_id] for source_id in source_ids]
                # Classify the item into a product category based on HSN and description
                description_for_class = next((item.description for item in source_items if item.description), item_name)
                if default_sion == "C969" and not any(item.description for item in source_items) and item_name == "UNMAPPED ITEM":
                    # C969 lines with no description are NO DESCRIPTION, not the UNMAPPED ITEM placeholder.
                    description_for_class = ""
                hsn_for_class = next((item.hs_code.hs_code for item in source_items if item.hs_code_id), "")
                product_category = classify_product(hsn_for_class, description_for_class, default_sion)
                # Collect all descriptions and HSN codes from source items for display.
                # Deduplicate by case-insensitive comparison, preserve original casing.
                source_descs = [item.description.strip() for item in source_items if item.description and item.description.strip()]
                seen_desc = set()
                unique_descs = []
                for d in source_descs:
                    if d.lower() not in seen_desc:
                        seen_desc.add(d.lower())
                        unique_descs.append(d)
                display_description = unique_descs[0] if len(unique_descs) == 1 else (", ".join(unique_descs) if unique_descs else item_name)
                source_hsns = [item.hs_code.hs_code.strip() for item in source_items if item.hs_code_id and item.hs_code.hs_code and item.hs_code.hs_code.strip()]
                unique_hsns = list(dict.fromkeys(hs for hs in source_hsns if hs))
                display_hsn = unique_hsns[0] if len(unique_hsns) == 1 else (", ".join(unique_hsns) if unique_hsns else "")
                # The matrix key uses product category so items with the same
                # category (e.g. DIETARY FIBRE) merge into one column per license.
                # A canonical item with two SIONs must remain two cells.
                plan_sources = _plan_source_ids(plan)
                is_split_target = (default_sion != "C969" and plan.item_name_id and _is_percentage(plan)
                                   and any(len(split_sources.get(source_id, ())) > 1 for source_id in plan_sources))
                if is_split_target:
                    # The category this canonical Item Name has on its single-target plans in this report (data-driven,
                    # consistent across licences), else the fallback above.
                    product_category = (canonical_category.get((plan.item_name_id, sion))
                                        or _split_target_category(item_name))
                    owner = split_key_owner.setdefault((plan_sources, product_category, sion), plan.item_name_id)
                    if owner != plan.item_name_id:  # two targets of one split classify alike: never merge them
                        product_category = item_name.strip().upper()
                        split_key_owner.setdefault((plan_sources, product_category, sion), plan.item_name_id)
                key = f"{product_category or 'UNCLASSIFIED'}:{sion}"
                plan_keys[plan.id] = key
                is_percentage = provenance.get("strategy") in {"SPLIT_BY_PERCENT", "SPLIT_BY_PERCENTAGE"}

                # Actual usage belongs to the planning target only if a persisted
                # mapping selected this item; split provenance already contains
                # the canonical result, so do not infer from descriptions here.
                # The solver persists the target's resolved actuals in these
                # fields.  They remain separate from the licence-wide usage
                # roll-up above, which intentionally includes unresolved rows.
                actual_qty = _decimal(provenance.get("actual_target_quantity", 0))
                actual_cif = _decimal(provenance.get("actual_target_cif", 0))
                boe_qty = sum((_decimal(mapped_usage.get((source_id, plan.item_name_id), {}).get("boe_used_quantity", 0)) for source_id in source_ids), ZERO_QTY)
                boe_cif = sum((_decimal(mapped_usage.get((source_id, plan.item_name_id), {}).get("boe_used_cif", 0)) for source_id in source_ids), ZERO_CIF)
                allot_qty = sum((_decimal(mapped_usage.get((source_id, plan.item_name_id), {}).get("unlinked_allotment_quantity", 0)) for source_id in source_ids), ZERO_QTY)
                allot_cif = sum((_decimal(mapped_usage.get((source_id, plan.item_name_id), {}).get("unlinked_allotment_cif", 0)) for source_id in source_ids), ZERO_CIF)
                total_qty = _decimal(provenance.get("theoretical_target_qty" if is_percentage else "total_quantity", 0))
                if is_percentage and not total_qty:
                    total_qty = _decimal(provenance.get("percentage_base_qty", 0)) * _decimal(provenance.get("percentage", 0)) / Decimal("100")
                if not total_qty:
                    total_qty = sum((_decimal(item.quantity) for item in source_items), ZERO_QTY)
                entitlement_apportioned = plan.id in shared_qty
                if entitlement_apportioned:
                    # N4: this plan's share of the shared source(s); a provenance quantity keeps its ratio to the sources.
                    old_source_qty = sum((_decimal(item.quantity) for item in source_items), ZERO_QTY)
                    new_source_qty = sum((shared_qty[plan.id].get(item.id, _decimal(item.quantity)) for item in source_items), ZERO_QTY)
                    entitlement_ratio = total_qty / old_source_qty if old_source_qty > ZERO_QTY else Decimal("1")
                    if old_source_qty > ZERO_QTY:
                        total_qty = (total_qty * new_source_qty / old_source_qty).quantize(QTY_PLACES, rounding=ROUND_HALF_UP)
                if plan.id in fallback_plan_ids:
                    # No usage mapped to this target: legacy fallback to the source's rows that have NO planning target
                    # (owner decision D2: a row mapped to an item this source does not plan is NOT ATTRIBUTED, never put
                    # here; D1: rows shared with another fallback plan are apportioned by planned CIF).
                    plan_entries = list(fallback_entries.get(plan.id, []))
                else:
                    # ``target_id=None`` means "every row" in _usage_row_keys: a percentage plan whose Item Name was removed
                    # (SET_NULL) must not take rows mapped to another target — it carries none (unmapped rows → NOT
                    # ATTRIBUTED). A STANDARD plan without an Item Name falls back to unmapped rows only (above).
                    mapped_keys = _usage_row_keys(usage, source_ids, target_id=plan.item_name_id) if plan.item_name_id else []
                    plan_entries = [(kind, pk, _decimal(row_index[(kind, pk)][0].qty), _decimal(row_index[(kind, pk)][0].cif_fc), None)
                                    for kind, pk in mapped_keys]
                # Exactly once per licence: a transaction already carried by another cell (overlapping plan sources,
                # repeated split rows) is never counted again.
                # (An apportioned row is, by construction, carried by several cells — each with its own share, once in total.)
                plan_entries = [entry for entry in plan_entries if entry[4] is not None or (entry[0], entry[1]) not in carried_rows]
                carried_rows.update((entry[0], entry[1]) for entry in plan_entries)
                boe_qty, boe_cif, allot_qty, allot_cif = _sum_entries(plan_entries)
                apportioned_rows = [{"kind": kind, "row_id": pk, "share": share, "qty": _text(qty), "cif": _text(cif)}
                                    for kind, pk, qty, cif, share in plan_entries if share is not None]
                usage_rows = ([_trace_row(kind, row_index[(kind, pk)][0], "bill_of_entry" if kind == "BOE" else "allotment",
                                          row_index[(kind, pk)][0].sr_number_id if kind == "BOE" else row_index[(kind, pk)][0].item_id, qty, cif, share)
                               for kind, pk, qty, cif, share in plan_entries] if trace_rows else [])
                if is_split_target:
                    # D3: each split target carries its percentage share of the source's billed-without-BOE lines.
                    billed_qty, billed_cif = ZERO_QTY, ZERO_CIF
                    for source_id in source_ids:
                        if claiming_group.get(source_id) != _plan_source_ids(plan):
                            continue  # another split group (or no split group) carries this source's billed lines
                        carried_billed.add(source_id)
                        for line, qty_share, cif_share, fraction in split_billed.get((plan.id, source_id), []):
                            billed_qty += qty_share
                            billed_cif += cif_share
                            apportioned_rows.append({"kind": "BILLED", "row_id": line["line_id"], "share": fraction, "qty": _text(qty_share), "cif": _text(cif_share)})
                            if trace_rows:
                                usage_rows.append({"kind": "BILLED", "row_id": line["line_id"], "record_id": line["invoice_id"], "import_item_id": source_id,
                                                   "reference": line["invoice_number"], "date": line["date"].isoformat() if line["date"] else None,
                                                   "qty": _text(qty_share), "cif": _text(cif_share), "share": fraction})
                else:
                    # N1: a source claimed by a split group is never taken by a STANDARD plan (order-independent).
                    billed_items = [item.id for item in dict.fromkeys(source_items) if item.id not in carried_billed and item.id not in claiming_group]
                    carried_billed.update(billed_items)
                    billed_qty = sum((usage_totals[item_id]["billed_qty"] for item_id in billed_items), ZERO_QTY)
                    billed_cif = sum((usage_totals[item_id]["billed_cif"] for item_id in billed_items), ZERO_CIF)
                    if trace_rows:
                        for item_id in billed_items:
                            usage_rows.extend({"kind": "BILLED", "row_id": line["line_id"], "record_id": line["invoice_id"], "import_item_id": item_id,
                                               "reference": line["invoice_number"], "date": line["date"].isoformat() if line["date"] else None,
                                               "qty": _text(line["qty"]), "cif": _text(line["cif"]), "share": None} for line in billed_lines.get(item_id, []))
                percentage_target_qty = total_qty
                own_actual_qty = boe_qty + allot_qty
                own_excess_qty = max(own_actual_qty - percentage_target_qty, ZERO_QTY) if is_percentage else ZERO_QTY
                excess_other_item_qty = _decimal(provenance.get("excess_other_item_quantity", 0)) if is_percentage else ZERO_QTY
                # Item Pivot represents the reconciled physical allocation,
                # unlike Planning's percentage-target audit.  An over-used
                # member keeps its own excess; its recipient yields that
                # same amount.  This preserves the split group's source qty.
                adjusted_total_qty = (
                    percentage_target_qty + own_excess_qty - excess_other_item_qty
                    if is_percentage else total_qty
                )
                adjusted_total_qty = max(adjusted_total_qty, ZERO_QTY)
                if is_percentage:
                    balance_qty = adjusted_total_qty - own_actual_qty - billed_qty
                else:
                    balance_qty = _decimal(provenance.get("audit_remaining_quantity", plan.planned_quantity))
                    if balance_qty == _decimal(plan.planned_quantity):
                        balance_qty = total_qty - boe_qty - allot_qty - billed_qty
                plan_qty = _decimal(plan.planned_quantity)
                plan_cif = _decimal(plan.planned_cif_fc)
                planned_cif += plan_cif
                source_total_qty = sum((_decimal(item.quantity) for item in source_items), ZERO_QTY)
                source_total_cif = sum((_decimal(item.cif_fc) for item in source_items), ZERO_CIF)
                source_used_cif = boe_cif + allot_cif + billed_cif
                # Look up CIF restriction percentage for this plan's item
                plan_restriction_pct = None
                if plan.item_name_id and plan.item_name_id in license_cif_restriction_map:
                    plan_restriction_pct = license_cif_restriction_map[plan.item_name_id]
                elif "__rule__" in license_cif_restriction_map:
                    plan_restriction_pct = license_cif_restriction_map["__rule__"]
                plan_restriction_value = None
                if plan_restriction_pct is not None:
                    plan_restriction_value = source_total_cif * _decimal(plan_restriction_pct) / Decimal("100")
                # Allocate only this target's adjusted share of its source
                # balance.  Never repeat the full licence balance per item.
                # A licence's CIF is a shared budget.  A proportional source
                # value is useful display information, but is *not* an item
                # CIF cap and must never create an item-CIF exception.  Only
                # an explicit cap supplied by canonical planning may do that.
                explicit_item_cif_cap = provenance.get("item_cif_cap")
                has_item_cif_cap = explicit_item_cif_cap is not None
                item_cif_cap = _decimal(explicit_item_cif_cap) if has_item_cif_cap else None
                canonical_item_cif_capacity = (source_total_cif * adjusted_total_qty / source_total_qty
                                               if source_total_qty > ZERO_QTY else ZERO_CIF)
                if entitlement_apportioned:
                    # N4: item CIF = this plan's apportioned share of each shared source (+ the engine's proportional value
                    # of any source it does not share).
                    canonical_item_cif_capacity = sum((shared_cif[plan.id][item.id] for item in source_items if item.id in shared_cif[plan.id]), ZERO_CIF) + sum(
                        (_decimal(item.cif_fc) * entitlement_ratio for item in source_items if item.id not in shared_cif[plan.id]), ZERO_CIF)
                available_cif = max(item_cif_cap - max(source_used_cif, ZERO_CIF), ZERO_CIF) if has_item_cif_cap else None
                candidate_cell = {
                    "canonical_item_id": plan.item_name_id, "item_name": item_name, "sion": sion,
                    "product_category": product_category,
                    "hsn_code": display_hsn, "description": display_description, "total_qty": _text(adjusted_total_qty),
                    # A pivot cell is a projection of particular import rows,
                    # not a substitute for them.  Keep the precise source
                    # lineage available to the API/UI/exporter rather than
                    # merging HSN/description strings or forcing consumers
                    # to reverse-engineer a source from a display label.
                    "source_items": [
                        {
                            "import_item_id": item.id,
                            "serial_number": item.serial_number,
                            "unit": (getattr(item, "unit", None) or "").upper() or None,
                            "hsn_code": item.hs_code.hs_code if item.hs_code_id else "",
                            "description": item.description or "",
                            "quantity": _text(_decimal(item.quantity)), "cif_fc": _text(_decimal(item.cif_fc)),
                            "allotted_quantity": _text(_decimal(item.allotted_quantity)),
                            "debited_quantity": _text(_decimal(item.debited_quantity)),
                            "available_quantity": _text(_decimal(item.available_quantity)),
                        }
                        for item in source_items
                    ],
                    "percentage_target_qty": _text(percentage_target_qty), "own_excess_qty": _text(own_excess_qty),
                    "excess_other_item_qty": _text(excess_other_item_qty), "adjusted_total_qty": _text(adjusted_total_qty),
                    "allotted_qty": _text(max(allot_qty, ZERO_QTY)), "debited_qty": _text(max(boe_qty, ZERO_QTY)),
                    "billed_qty": _text(max(billed_qty, ZERO_QTY)),
                    "boe_used_cif": _text(max(boe_cif, ZERO_CIF)), "allotted_cif": _text(max(allot_cif, ZERO_CIF)),
                    "billed_cif": _text(max(billed_cif, ZERO_CIF)),
                    "balance_qty": _text(max(balance_qty, ZERO_QTY)), "plan_qty": _text(max(plan_qty, ZERO_QTY)),
                    "planned_cif": _text(max(plan_cif, ZERO_CIF)), "effective_planned_qty": _text(max(plan_qty, ZERO_QTY)),
                    "effective_planned_cif": _text(max(plan_cif, ZERO_CIF)), "has_item_cif_cap": has_item_cif_cap, "has_explicit_item_cif_cap": has_item_cif_cap, "item_cif_cap": _text(item_cif_cap) if item_cif_cap is not None else None, "canonical_item_cif_capacity": _text(canonical_item_cif_capacity), "available_cif": _text(available_cif) if available_cif is not None else None,
                    "restriction_percent": _text(plan_restriction_pct) if plan_restriction_pct is not None else None,
                    "restriction_value": _text(plan_restriction_value) if plan_restriction_value is not None else None,
                    "planning_priority": planning_priority,
                    "planning_rule_id": rule.id if rule else plan.planning_rule_id,
                    "planning_rule_name": rule.name if rule else None,
                    "planning_strategy": (rule.strategy or "STANDARD").lower() if rule else provenance.get("strategy"),
                    "priority_item_order": priority_item_order,
                    "priority_source": "active_sion_rule" if rule and rule.is_active else "unmatched",
                    # Item CIF the report credits to this identity: a split target's percentage share of its source CIF (D3
                    # remainder rule), else the engine's item CIF capacity. Counted once per source (merge adds new sources only).
                    "item_total_cif": _text(split_cif[plan.id] if is_split_target else canonical_item_cif_capacity),
                    # Rows (BOE / allotment / billed line) split between several cells (D1 / D3): row, share, qty, cif.
                    "apportioned_rows": apportioned_rows,
                    # N4: the entitlement (Total Qty / item CIF) is this plan's share of a source shared with other fallback plans.
                    "entitlement_apportioned": entitlement_apportioned,
                    **({"usage_rows": usage_rows} if trace_rows else {}),
                }
                candidate_cell["identity_parts"] = [_identity_part(
                    candidate_cell, canonical_item_id=plan.item_name_id, item_name=plan.item_name.name if plan.item_name_id else item_name,
                    reason=None if plan.item_name_id else "plan_without_item_name")]
                cells[key] = (
                    _merge_plan_cell(cells[key], candidate_cell)
                    if key in cells else candidate_cell
                )
                # Add the column to the licence's notification/company group
                # after its identity is known below.

            # Build zero-plan cells for import items not covered by any active
            # plan so the pivot report shows the full licence contents — even
            # items with available quantity 0 or no plan at all.
            # Use product category as the key so unplanned items merge with
            # planned items in the same category (e.g. DIETARY FIBRE).
            planned_import_item_ids = {plan.import_item_id for plan in plans_by_license[license_obj.id]}
            for item in import_items:
                if item.id in planned_import_item_ids:
                    continue
                item_name_str = (item.description or "").strip() or "UNMAPPED ITEM"
                hsn_str = item.hs_code.hs_code if item.hs_code_id else ""
                sion_str = default_sion
                # Classify the unplanned item into a product category
                # C969 classifies the raw description so a blank line stays NO DESCRIPTION.
                unplanned_text = (item.description or "").strip() if default_sion == "C969" else item_name_str
                unplanned_product_category = classify_product(hsn_str, unplanned_text, default_sion)
                # Use product category as the key so items with the same
                # category merge into one column per license.
                unplanned_key = f"{unplanned_product_category or 'UNCLASSIFIED'}:{sion_str}"
                first_item_name_id = None
                for attached in item.items.all():
                    first_item_name_id = attached.id
                    break
                # This item's own transactions not carried by another cell. Merged into a cell that already holds this
                # source (a plan's secondary source), it carries nothing: rows that plan did not take are NOT ATTRIBUTED,
                # never moved onto the plan's target.
                holds_source = unplanned_key in cells and item.id in {row["import_item_id"] for row in cells[unplanned_key].get("source_items", [])}
                item_rows = [] if holds_source else [k for k in _usage_row_keys(usage, (item.id,)) if k not in carried_rows]
                carried_rows.update(item_rows)
                item_usage_boe_qty, item_usage_boe_cif, item_usage_allot_qty, item_usage_allot_cif = _sum_rows(item_rows, row_index)
                unplanned_usage_rows = ([_trace_row(kind, row_index[(kind, pk)][0], "bill_of_entry" if kind == "BOE" else "allotment", item.id,
                                                    _decimal(row_index[(kind, pk)][0].qty), _decimal(row_index[(kind, pk)][0].cif_fc), None)
                                         for kind, pk in item_rows] if trace_rows else [])
                takes_billed = not holds_source and item.id not in carried_billed
                if takes_billed:
                    carried_billed.add(item.id)
                if trace_rows and takes_billed:
                    unplanned_usage_rows.extend({"kind": "BILLED", "row_id": line["line_id"], "record_id": line["invoice_id"], "import_item_id": item.id,
                                                 "reference": line["invoice_number"], "date": line["date"].isoformat() if line["date"] else None,
                                                 "qty": _text(line["qty"]), "cif": _text(line["cif"]), "share": None} for line in billed_lines.get(item.id, []))
                item_usage_billed_qty = usage_totals[item.id]["billed_qty"] if takes_billed else ZERO_QTY
                item_usage_billed_cif = usage_totals[item.id]["billed_cif"] if takes_billed else ZERO_CIF
                item_total_qty = _decimal(item.quantity)
                item_total_cif = _decimal(item.cif_fc)
                balance_qty_unplanned = max(item_total_qty - item_usage_boe_qty - item_usage_allot_qty - item_usage_billed_qty, ZERO_QTY)
                # Look up CIF restriction for this unplanned item
                unplanned_restriction_pct = None
                if first_item_name_id is not None and first_item_name_id in license_cif_restriction_map:
                    unplanned_restriction_pct = license_cif_restriction_map[first_item_name_id]
                elif "__rule__" in license_cif_restriction_map:
                    unplanned_restriction_pct = license_cif_restriction_map["__rule__"]
                unplanned_restriction_value = None
                if unplanned_restriction_pct is not None:
                    unplanned_restriction_value = item_total_cif * _decimal(unplanned_restriction_pct) / Decimal("100")
                # Merge with existing cell if another unplanned item has the
                # same product category key, otherwise create a new one.
                unplanned_candidate = {
                    "canonical_item_id": first_item_name_id, "item_name": item_name_str, "sion": sion_str,
                    "product_category": unplanned_product_category,
                    "hsn_code": hsn_str, "description": item_name_str,
                    "total_qty": _text(item_total_qty),
                    "source_items": [
                        {
                            "import_item_id": item.id,
                            "serial_number": item.serial_number,
                            "unit": (getattr(item, "unit", None) or "").upper() or None,
                            "hsn_code": hsn_str,
                            "description": item.description or "",
                            "quantity": _text(item_total_qty), "cif_fc": _text(item_total_cif),
                            "allotted_quantity": _text(_decimal(item.allotted_quantity)),
                            "debited_quantity": _text(_decimal(item.debited_quantity)),
                            "available_quantity": _text(_decimal(item.available_quantity)),
                        }
                    ],
                    "percentage_target_qty": _text(ZERO_QTY), "own_excess_qty": _text(ZERO_QTY),
                    "excess_other_item_qty": _text(ZERO_QTY), "adjusted_total_qty": _text(item_total_qty),
                    "allotted_qty": _text(max(item_usage_allot_qty, ZERO_QTY)),
                    "debited_qty": _text(max(item_usage_boe_qty, ZERO_QTY)),
                    "billed_qty": _text(max(item_usage_billed_qty, ZERO_QTY)),
                    "boe_used_cif": _text(max(item_usage_boe_cif, ZERO_CIF)),
                    "allotted_cif": _text(max(item_usage_allot_cif, ZERO_CIF)),
                    "billed_cif": _text(max(item_usage_billed_cif, ZERO_CIF)),
                    "balance_qty": _text(max(balance_qty_unplanned, ZERO_QTY)),
                    "plan_qty": _text(ZERO_QTY), "planned_cif": _text(ZERO_CIF),
                    "effective_planned_qty": _text(ZERO_QTY), "effective_planned_cif": _text(ZERO_CIF),
                    "has_item_cif_cap": False, "has_explicit_item_cif_cap": False,
                    "item_cif_cap": None, "canonical_item_cif_capacity": _text(item_total_cif), "item_total_cif": _text(item_total_cif),
                    "apportioned_rows": [],
                    **({"usage_rows": unplanned_usage_rows} if trace_rows else {}),
                    "available_cif": None,
                    "restriction_percent": _text(unplanned_restriction_pct) if unplanned_restriction_pct is not None else None,
                    "restriction_value": _text(unplanned_restriction_value) if unplanned_restriction_value is not None else None,
                    "planning_priority": None, "planning_rule_id": None,
                    "planning_rule_name": None, "planning_strategy": None,
                    "priority_item_order": None, "priority_source": "unplanned",
                }
                # Identity: the import item's own Item Name link. None, or several, is NOT a guessed item — it is reported
                # as an unmapped identity (the matrix column keeps its first-name label for display only).
                attached_names = list(item.items.all())
                unplanned_candidate["identity_parts"] = [_identity_part(
                    unplanned_candidate, canonical_item_id=attached_names[0].pk if len(attached_names) == 1 else None,
                    item_name=attached_names[0].name if len(attached_names) == 1 else item_name_str,
                    reason=None if len(attached_names) == 1 else "ambiguous_item_name" if attached_names
                    else "item_name_not_valid_for_norm" if linked_name_counts.get(item.id) else "no_item_name")]
                cells[unplanned_key] = (
                    _merge_plan_cell(cells[unplanned_key], unplanned_candidate)
                    if unplanned_key in cells else unplanned_candidate
                )

            notification = license_obj.notification_number.code if license_obj.notification_number_id else "Unknown"
            # Purchase status is the report's grouping dimension.  Exporter,
            # owner, and transfer company are intentionally presentation-only
            # relationships and must never split a notification group.
            purchase_status = license_obj.purchase_status
            purchase_status_id = license_obj.purchase_status_id
            purchase_status_name = getattr(purchase_status, "label", None) or getattr(purchase_status, "name", None) or "UNASSIGNED"
            group_key = (license_obj.notification_number_id, purchase_status_id)
            group = output_groups[group_key]
            group["notification_number"] = notification
            group["purchase_status"] = {"id": purchase_status_id, "name": purchase_status_name}
            for plan in plans_by_license[license_obj.id]:
                provenance = plan.allocation_provenance or {}
                name = (plan.item_name.name if plan.item_name_id else provenance.get("canonical_item_name")) or "UNMAPPED ITEM"
                sion = provenance.get("sion") or default_sion
                # The key this plan's cell was stored under (not the last key of the loop above).
                key = plan_keys[plan.id]
                plan_cell = cells.get(key)
                plan_product_category = plan_cell.get("product_category") if plan_cell else None
                group["item_groups"].setdefault(key, {"key": key, "canonical_item_id": plan.item_name_id, "name": name, "sion": sion, "product_category": plan_product_category, "priority": plan.planning_rule_priority or 999999, "sequence": plan.id})
            # Register unplanned items in item_groups so they appear as columns
            # in the report matrix even when no plan exists for them.
            for item in import_items:
                if item.id in planned_import_item_ids:
                    continue
                item_name_str = (item.description or "").strip() or "UNMAPPED ITEM"
                hsn_str = item.hs_code.hs_code if item.hs_code_id else ""
                sion_str = default_sion
                # C969 classifies the raw description so a blank line stays NO DESCRIPTION.
                unplanned_text = (item.description or "").strip() if default_sion == "C969" else item_name_str
                unplanned_product_category = classify_product(hsn_str, unplanned_text, default_sion)
                unplanned_key = f"{unplanned_product_category or 'UNCLASSIFIED'}:{sion_str}"
                unplanned_cell = cells.get(unplanned_key)
                first_item_name_id = None
                for attached in item.items.all():
                    first_item_name_id = attached.id
                    break
                group["item_groups"].setdefault(unplanned_key, {"key": unplanned_key, "canonical_item_id": first_item_name_id, "name": item_name_str, "sion": sion_str, "product_category": unplanned_product_category, "priority": 999999, "sequence": item.id})
            # Usage that no item cell carries — BOE / allotment rows whose header has no planning target, or a target with
            # no plan on this licence's source, — is listed row by row and
            # shown once as NOT ATTRIBUTED, never dropped and never guessed onto an item. Exact rows, no netting.
            unattributed = {"debited_qty": ZERO_QTY, "boe_used_cif": ZERO_CIF, "allotted_qty": ZERO_QTY, "allotted_cif": ZERO_CIF,
                            "billed_qty": ZERO_QTY, "billed_cif": ZERO_CIF}
            records = []
            for item in import_items:
                # Source provenance of the import item each NOT ATTRIBUTED record sits on (display only; no arithmetic).
                provenance = {"serial_number": item.serial_number, "hsn_code": item.hs_code.hs_code if item.hs_code_id else "",
                              "description": item.description or "", "unit": (getattr(item, "unit", None) or "").upper() or None}
                for kind, rows, header, qty_field, cif_field in (
                        ("BOE", usage.get(item.id, {}).get("boes", []), "bill_of_entry", "debited_qty", "boe_used_cif"),
                        ("ALLOTMENT", usage.get(item.id, {}).get("allotments", []), "allotment", "allotted_qty", "allotted_cif")):
                    for row in rows:
                        if (kind, row.pk) in carried_rows:
                            continue
                        target_id = row_index[(kind, row.pk)][1]
                        unattributed[qty_field] += _decimal(row.qty)
                        unattributed[cif_field] += _decimal(row.cif_fc)
                        traced = _trace_row(kind, row, header, item.id, _decimal(row.qty), _decimal(row.cif_fc), None)
                        records.append({"kind": kind, "record_id": getattr(row, f"{header}_id", None), "row_id": row.pk, "import_item_id": item.id, **provenance,
                                        "reference": traced["reference"], "date": traced["date"],
                                        "qty": _text(_decimal(row.qty)), "cif_fc": _text(_decimal(row.cif_fc)), "planning_target_item_id": target_id,
                                        "reason": ("no_target" if not target_id else "target_not_planned"
                                                   if target_id not in planned_targets_by_source.get(item.id, set()) else "target_not_carried")})
                if item.id in carried_billed:
                    continue
                billed_qty_item, billed_cif_item = usage_totals.get(item.id, {}).get("billed_qty", ZERO_QTY), usage_totals.get(item.id, {}).get("billed_cif", ZERO_CIF)
                if _decimal(billed_qty_item) or _decimal(billed_cif_item):
                    unattributed["billed_qty"] += _decimal(billed_qty_item)
                    unattributed["billed_cif"] += _decimal(billed_cif_item)
                    records.append({"kind": "BILLED", "record_id": None, "row_id": None, "import_item_id": item.id, **provenance, "qty": _text(_decimal(billed_qty_item)),
                                    "cif_fc": _text(_decimal(billed_cif_item)), "planning_target_item_id": None, "reason": "billed_not_carried"})
            if records:
                unattributed_key = f"{UNATTRIBUTED_CATEGORY}:{default_sion}"
                cells[unattributed_key] = _unattributed_cell(default_sion, unattributed, records)
                group["item_groups"].setdefault(unattributed_key, {"key": unattributed_key, "canonical_item_id": None, "name": UNATTRIBUTED_CATEGORY,
                                                                   "sion": default_sion, "product_category": UNATTRIBUTED_CATEGORY,
                                                                   "priority": 10 ** 9, "sequence": 10 ** 9})
            # Diagnostics: the licence's source usage rows vs what the item cells carry (both directions, never netted).
            source_usage = {cell_field: sum((_decimal(usage_totals.get(item.id, {}).get(usage_field, 0)) for item in import_items), ZERO_CIF)
                            for usage_field, cell_field in _USAGE_TO_CELL}
            carried = {cell_field: sum((_decimal(cell.get(cell_field)) for cell in cells.values()), ZERO_CIF) for _, cell_field in _USAGE_TO_CELL}
            issues = []
            for item_key, cell in cells.items():
                adjusted_qty = _decimal(cell["adjusted_total_qty"])
                used_qty = _decimal(cell["debited_qty"]) + _decimal(cell["allotted_qty"]) + _decimal(cell.get("billed_qty", 0))
                actual_used_qty = max(used_qty, ZERO_QTY)
                available_qty = max(adjusted_qty - actual_used_qty, ZERO_QTY)
                planned_qty = max(_decimal(cell["plan_qty"]), ZERO_QTY)
                balance_after_plan = max(available_qty - planned_qty, ZERO_QTY)
                actual_used_cif = max(_decimal(cell["boe_used_cif"]) + _decimal(cell["allotted_cif"]) + _decimal(cell.get("billed_cif", 0)), ZERO_CIF)
                has_item_cif_cap = bool(cell.get("has_item_cif_cap"))
                item_cif_cap = _decimal(cell["item_cif_cap"]) if has_item_cif_cap else ZERO_CIF
                over_utilized_qty = max(actual_used_qty - adjusted_qty, ZERO_QTY)
                over_utilized_cif = max(actual_used_cif - item_cif_cap, ZERO_CIF) if has_item_cif_cap else ZERO_CIF
                over_planned_qty = max(planned_qty - available_qty, ZERO_QTY)
                # Compare the effective (already reconciled/capped) plan to
                # availability before planning; do not subtract it twice.
                over_planned_cif = max(_decimal(cell["effective_planned_cif"]) - _decimal(cell["available_cif"]), ZERO_CIF) if has_item_cif_cap else ZERO_CIF
                if cell.get("unattributed"):  # usage without an item: no entitlement to exceed (reported, not an item exception)
                    over_utilized_qty = over_utilized_cif = over_planned_qty = over_planned_cif = ZERO_QTY
                cell["available_qty"] = _text(available_qty)
                cell["balance_qty_after_plan"] = _text(balance_after_plan)
                cell.update({"actual_used_qty": _text(actual_used_qty), "actual_used_cif": _text(actual_used_cif), "item_available_cif_before_plan": _text(available_cif) if has_item_cif_cap else None, "item_balance_cif_after_plan": _text(max(available_cif - _decimal(cell["effective_planned_cif"]), ZERO_CIF)) if has_item_cif_cap else None, "over_utilized_qty": _text(over_utilized_qty), "over_utilized_cif": _text(over_utilized_cif), "over_planned_qty": _text(over_planned_qty), "over_planned_cif": _text(over_planned_cif)})
                cell.update({"remaining_qty": _text(max(available_qty - planned_qty, ZERO_QTY)), "planning_qty_tolerance": _text(PLANNING_QTY_TOLERANCE), "is_within_planning_tolerance": planned_qty > ZERO_QTY and max(available_qty - planned_qty, ZERO_QTY) <= PLANNING_QTY_TOLERANCE, "is_over_utilized": over_utilized_qty > ZERO_QTY or over_utilized_cif > ZERO_CIF, "is_over_planned": over_planned_qty > ZERO_QTY or over_planned_cif > ZERO_CIF, "status": determine_planning_status(planned_qty=planned_qty, available_qty=available_qty, over_utilized_qty=over_utilized_qty, over_utilized_cif=over_utilized_cif, over_planned_qty=over_planned_qty, over_planned_cif=over_planned_cif)})
                if over_utilized_qty > ZERO_QTY or over_utilized_cif > ZERO_CIF:
                    issues.append({"item_key": item_key, "canonical_item_id": cell["canonical_item_id"], "sion": cell["sion"], "type": "item_qty_over_utilized" if over_utilized_qty > ZERO_QTY else "item_cif_over_utilized", "severity": "critical", "total_qty": _text(adjusted_qty), "total_utilized_qty": _text(actual_used_qty), "actual_excess_qty": _text(over_utilized_qty), "actual_excess_cif": _text(over_utilized_cif), "planned_excess_qty": _text(ZERO_QTY), "planned_excess_cif": _text(ZERO_CIF), "item_cif_cap": cell["item_cif_cap"], "boe_used_cif": cell["boe_used_cif"], "allotted_cif": cell["allotted_cif"], "actual_used_cif": _text(actual_used_cif), "available_cif": cell["item_available_cif_before_plan"], "effective_planned_cif": cell["effective_planned_cif"], "balance_cif_after_plan": cell["item_balance_cif_after_plan"], "available_qty": _text(available_qty), "planned_qty": _text(planned_qty), "balance_qty": _text(balance_after_plan)})
                if over_planned_qty > ZERO_QTY or over_planned_cif > ZERO_CIF:
                    issues.append({"item_key": item_key, "canonical_item_id": cell["canonical_item_id"], "sion": cell["sion"], "type": "item_qty_over_planned" if over_planned_qty > ZERO_QTY else "item_cif_over_planned", "severity": "warning", "total_qty": _text(adjusted_qty), "total_utilized_qty": _text(actual_used_qty), "actual_excess_qty": _text(ZERO_QTY), "actual_excess_cif": _text(ZERO_CIF), "planned_excess_qty": _text(over_planned_qty), "planned_excess_cif": _text(over_planned_cif), "item_cif_cap": cell["item_cif_cap"], "boe_used_cif": cell["boe_used_cif"], "allotted_cif": cell["allotted_cif"], "actual_used_cif": _text(actual_used_cif), "available_cif": cell["item_available_cif_before_plan"], "effective_planned_cif": cell["effective_planned_cif"], "balance_cif_after_plan": cell["item_balance_cif_after_plan"], "available_qty": _text(available_qty), "planned_qty": _text(planned_qty), "balance_qty": _text(balance_after_plan)})
            # Defensive guard for decimal serialization and duplicate plan rows.
            unique_issues = {}
            for issue in issues:
                if not _positive_issue(issue):
                    continue
                unique_issues[(license_obj.id, issue.get("canonical_item_id"), issue.get("sion"), issue["type"])] = issue
            issues = list(unique_issues.values())
            group.setdefault("_licence_objects", []).append(license_obj)
            group["licenses"].append({
                "license_id": license_obj.id, "license_number": license_obj.license_number,
                "expiry_date": license_obj.license_expiry_date.isoformat() if license_obj.license_expiry_date else None,
                "exporter": getattr(license_obj.exporter, "name", None) or license_obj.archived_exporter_name or "—",
                "purchase_status": {"id": purchase_status_id, "name": purchase_status_name},
                "condition_available": bool(getattr(license_obj, "condition_sheet", None)),
                "condition_sheet": getattr(license_obj, "condition_sheet", None),
                "transfer_available": bool(getattr(license_obj, "latest_transfer", None)),
                "latest_transfer": str(getattr(license_obj, "latest_transfer", "") or ""),
                "total_cif": _text(total_cif), "debited_cif": _text(debited_cif), "allotted_cif": _text(allotted_cif),
                "billed_cif": _text(licence_billed_cif), "planned_cif": _text(planned_cif),
                "balance_cif": _text(licence_balance_cif), "is_over_utilised": licence_balance_cif < ZERO_CIF,
                "final_balance_cif": _text(licence_balance_cif - planned_cif), "items": cells,
                "item_reconciliation": {"source_usage": {k: _text(v) for k, v in source_usage.items()},
                                        "carried_by_items": {k: _text(v) for k, v in carried.items()},
                                        "difference": {k: _text(source_usage[k] - carried[k]) for k in source_usage}},
                "issues": issues, "issue_count": len(issues),
                "highest_issue": min(issues, key=lambda issue: 0 if issue["severity"] == "critical" else 1)["type"] if issues else None,
            })

        groups = []
        for group in output_groups.values():
            licence_objects = group.pop("_licence_objects", [])
            group["licenses"].sort(key=lambda row: (row["expiry_date"] or "", row["license_number"]))
            group["license_count"] = len(group["licenses"])
            group["issue_license_count"] = sum(1 for row in group["licenses"] if row["issue_count"])
            group["issue_record_count"] = sum(row["issue_count"] for row in group["licenses"])
            # Sort by norm-aware category sort key, then SION, priority, sequence, name
            # Items without a product category sort last
            group["item_groups"] = sorted(
                group["item_groups"].values(),
                key=lambda row: (
                    pivot_category_sort_key(row.get("product_category"), row["sion"]),
                    row.get("product_category") or "ZZZ_UNCLASSIFIED",
                    row["sion"],
                    row["priority"],
                    row["sequence"],
                    row["name"],
                )
            )
            for licence_row in group["licenses"]:
                for cell in licence_row["items"].values():
                    _add_balance_fields(cell)
            totals = {
                "total_cif": sum((_decimal(row["total_cif"]) for row in group["licenses"]), ZERO_CIF),
                "debited_cif": sum((_decimal(row["debited_cif"]) for row in group["licenses"]), ZERO_CIF),
                "allotted_cif": sum((_decimal(row["allotted_cif"]) for row in group["licenses"]), ZERO_CIF),
                "planned_cif": sum((_decimal(row["planned_cif"]) for row in group["licenses"]), ZERO_CIF),
                "balance_cif": sum((_decimal(row["balance_cif"]) for row in group["licenses"]), ZERO_CIF),
                "items": {},
            }
            for item in group["item_groups"]:
                key = item["key"]
                applicable = [row["items"][key] for row in group["licenses"] if key in row["items"]]
                totals["items"][key] = {
                    field: _text(sum((_decimal(cell.get(field)) for cell in applicable), ZERO_CIF if field in {"restriction_value", "planned_cif", "boe_used_cif", "allotted_cif", "billed_cif", "balance_cif"} else ZERO_QTY))
                    for field in ("total_qty", "allotted_qty", "allotted_cif", "debited_qty", "billed_qty", "boe_used_cif", "billed_cif", "balance_qty", "balance_cif", "restriction_value", "plan_qty", "planned_cif")
                }
                totals["items"][key]["unit_price"] = _unit_price(totals["items"][key]["balance_cif"], totals["items"][key]["balance_qty"])
            group["totals"] = {
                **{key: _text(value) for key, value in totals.items() if key != "items"},
                "items": totals["items"],
            }
            group["reconciliation"] = _group_reconciliation(group)
            # Per-notification C969 entitlement, so the notification summary matches the total table.
            group_c969 = _c969_entitlement_report(licence_objects, usage_totals)
            if group_c969 is not None:
                group["c969_entitlement"] = group_c969
            groups.append(group)
        groups = sorted(groups, key=lambda row: (row["notification_number"], row["purchase_status"]["name"]))
        # One pure projection is shared by per-notification and complete
        # report summaries.  It consumes the matrix cells above verbatim.
        for group in groups:
            group.update(project_item_summary(group["licenses"]))
        all_licenses = [license_row for group in groups for license_row in group["licenses"]]
        summary = {
            "license_count": len({row["license_id"] for row in all_licenses}),
            "total_cif": sum((_decimal(row["total_cif"]) for row in all_licenses), ZERO_CIF),
            "actual_boe_cif": sum((_decimal(row["debited_cif"]) for row in all_licenses), ZERO_CIF),
            "actual_allotment_cif": sum((_decimal(row["allotted_cif"]) for row in all_licenses), ZERO_CIF),
            "actual_billed_cif": sum((_decimal(row.get("billed_cif")) for row in all_licenses), ZERO_CIF),
            "actual_balance_cif": sum((_decimal(row["balance_cif"]) for row in all_licenses), ZERO_CIF),
            "effective_planned_cif": sum((_decimal(row["planned_cif"]) for row in all_licenses), ZERO_CIF),
        }
        summary["total_actual_used_cif"] = summary["actual_boe_cif"] + summary["actual_allotment_cif"] + summary["actual_billed_cif"]
        # Signed: a negative final balance is an over-plan / over-use signal, never hidden by a floor.
        summary["final_balance_cif"] = summary["actual_balance_cif"] - summary["effective_planned_cif"]
        # Shared licence CIF is reconciled at licence level.  Keep actual
        # overdraw and planning overage separate; neither is an item cap.
        # Over-use is read from the signed canonical balances (their opening / purchase-credit
        # terms are not part of total − used), never from a recomputed difference.
        summary["overdrawn_cif"] = sum((-_decimal(row["balance_cif"]) for row in all_licenses if _decimal(row["balance_cif"]) < ZERO_CIF), ZERO_CIF)
        summary["over_planned_cif"] = max(summary["effective_planned_cif"] - summary["actual_balance_cif"], ZERO_CIF)
        summary["planning_coverage_percent"] = (summary["effective_planned_cif"] * Decimal("100") / summary["actual_balance_cif"] if summary["actual_balance_cif"] else ZERO_CIF)
        item_summary = {}
        for group in groups:
            for item in group["item_groups"]:
                key = item["key"]
                target = item_summary.setdefault(key, {**item, "cells": []})
                target["cells"].extend({**row["items"][key], "license_id": row["license_id"], "license_number": row["license_number"]} for row in group["licenses"] if key in row["items"])
        items = []
        for key, row in item_summary.items():
            cells = row.pop("cells")
            values = lambda field, zero=ZERO_QTY: sum((_decimal(cell.get(field)) for cell in cells), zero)
            total_qty, boe_qty, allotted_qty, billed_qty, planned_qty = values("total_qty"), values("debited_qty"), values("allotted_qty"), values("billed_qty"), values("plan_qty")
            actual_qty = boe_qty + allotted_qty + billed_qty
            planned_cif = values("planned_cif", ZERO_CIF)
            actual_cif = values("boe_used_cif", ZERO_CIF) + values("allotted_cif", ZERO_CIF) + values("billed_cif", ZERO_CIF)
            available_qty = max(total_qty - actual_qty, ZERO_QTY)
            balance_qty = max(available_qty - planned_qty, ZERO_QTY)
            contributing = [
                {"license_id": cell["license_id"], "license_number": cell["license_number"], "available_qty": cell["available_qty"], "planned_qty": cell["plan_qty"], "planned_excess_qty": _text(max(-_decimal(cell["balance_qty_after_plan"]), ZERO_QTY))}
                for cell in cells if _decimal(cell["balance_qty_after_plan"]) < ZERO_QTY
            ]
            actual_contributing = [cell for cell in cells if _decimal(cell["available_qty"]) < ZERO_QTY]
            status = "over_utilized" if actual_contributing else ("over_planned" if contributing else ("planned" if planned_qty else "available"))
            items.append({
                "key": key, "item_name": row["name"], "sion": row["sion"],
                "product_category": row.get("product_category"),
                "priority": row["priority"], "sequence": row["sequence"],
                "hsn_codes": sorted({cell["hsn_code"] for cell in cells if cell.get("hsn_code")}),
                "license_count": len(cells), "total_qty": _text(total_qty), "boe_used_qty": _text(boe_qty),
                "allotted_qty": _text(allotted_qty), "actual_used_qty": _text(actual_qty),
                "available_qty": _text(available_qty), "planned_qty": _text(planned_qty), "balance_qty_after_plan": _text(balance_qty),
                "actual_used_cif": _text(max(actual_cif, ZERO_CIF)), "available_cif_before_plan": None,
                "planned_cif": _text(planned_cif), "balance_cif_after_plan": None,
                "average_planned_unit_price": _text(planned_cif / planned_qty) if planned_qty else None,
                "status": status, "planned_excess_qty": _text(sum((_decimal(row["planned_excess_qty"]) for row in contributing), ZERO_QTY)),
                "actual_excess_qty": _text(sum((-_decimal(cell["available_qty"]) for cell in actual_contributing), ZERO_QTY)),
                "contributing_licenses": contributing,
                "licenses": cells,
            })
        items = sorted(items, key=lambda row: (pivot_category_sort_key(row.get("product_category"), row["sion"]), row.get("product_category") or "ZZZ_UNCLASSIFIED", row["sion"], row["priority"], row["sequence"], row["item_name"]))
        global_summary = {key: _text(value) if isinstance(value, Decimal) else value for key, value in summary.items()}
        # Aliases make the report contract explicit while preserving the
        # existing consumers during the presentation-only migration.
        grand_projection = project_item_summary(all_licenses)
        # The Total Summary is the projection of exactly the notification groups' licence rows: prove it per metric (the
        # sum of every notification's Item Summary == the Total Summary) and state its licence population.
        check_fields = ("total_qty", "allotted_qty", "allotted_cif", "boe_used_qty", "boe_used_cif", "balance_qty", "planned_qty", "planned_cif")
        by_group = {f: sum((_decimal(row.get(f)) for group in groups for row in group.get("item_summary", [])), ZERO_CIF) for f in check_fields}
        by_total = {f: sum((_decimal(row.get(f)) for row in grand_projection["item_summary"]), ZERO_CIF) for f in check_fields}
        # Independent check against the licence-level matrix cells themselves (not the projection): the identity parts
        # must add back to exactly the cells for every summed metric.
        cell_fields = {"total_qty": "adjusted_total_qty", "allotted_qty": "allotted_qty", "allotted_cif": "allotted_cif", "boe_used_qty": "debited_qty",
                       "boe_used_cif": "boe_used_cif", "planned_qty": "effective_planned_qty", "planned_cif": "effective_planned_cif"}
        by_cells = {f: sum((max(_decimal(cell.get(c, cell.get("total_qty") if c == "adjusted_total_qty" else None)), ZERO_CIF)
                            for row in all_licenses for cell in row["items"].values()), ZERO_CIF) for f, c in cell_fields.items()}
        grand_projection["summary_check"] = {
            "license_population": [{"notification_number": g["notification_number"], "purchase_status": (g.get("purchase_status") or {}).get("name"),
                                    "license_count": g["license_count"]} for g in groups],
            "distinct_license_count": len({row["license_id"] for row in all_licenses}),
            "metrics": {f: {"notifications": _text(by_group[f]), "total_summary": _text(by_total[f]), "difference": _text(by_total[f] - by_group[f]),
                            **({"licence_detail_cells": _text(by_cells[f]), "difference_to_cells": _text(by_total[f] - by_cells[f])} if f in by_cells else {})}
                        for f in check_fields},
            "notifications_reconciled": all(group.get("reconciliation", {}).get("reconciled", True) for group in groups),
        }
        # Each summary row is rounded once at output (3 dp qty / 2 dp CIF) while cells are exact: the only legitimate
        # difference is that rounding, bounded by half a unit per summed row. Anything larger is a real inconsistency.
        group_rows = sum(len(group.get("item_summary", [])) for group in groups)
        total_rows = len(grand_projection["item_summary"])
        def _half_unit(field):
            return Decimal("0.005") if field.endswith("_cif") else Decimal("0.0005")
        grand_projection["summary_check"]["consistent"] = all(
            abs(_decimal(m["difference"])) <= _half_unit(f) * (group_rows + total_rows)
            and abs(_decimal(m.get("difference_to_cells", 0))) <= _half_unit(f) * total_rows
            for f, m in grand_projection["summary_check"]["metrics"].items())
        report = {"groups": groups, "notification_groups": groups, "summary": global_summary,
                "global_summary": global_summary, "items": items, "item_columns": [{"key": row["key"], "name": row["item_name"], "sion": row["sion"]} for row in items],
                "grand_total": {"notification_count": len(groups), "license_count": global_summary["license_count"], "summary": global_summary, **grand_projection},
                "report_version": "canonical-item-pivot-v1"}
        # C969 gets the flat entitlement table; other norms' output is unchanged.
        c969_entitlement = _c969_entitlement_report(licenses, usage_totals)
        if c969_entitlement is not None:
            report["c969_entitlement"] = c969_entitlement
        return report


# Columns of the flat C969 entitlement table, in display order. Labels follow the
# report's existing spelling.
C969_ENTITLEMENT_COLUMNS = (
    ("hsn_code", "HSN CODE"),
    ("description", "DESCRIPTION"),
    ("total_qty", "TOTAL QTY"),
    ("allotted_qty", "ALLOTTED QTY"),
    ("allotted_cif", "ALLOTTED CIF"),
    ("debited_qty", "DEBITED QTY"),
    ("debited_cif", "DEBITED CIF"),
    ("balance_qty", "BALANCE QTY"),
)

_C969_CONFIGURED_CATEGORIES = C969_CLASSIFIER_ORDER + tuple(name for name, _ in C969_GENERIC_CATEGORIES)


def c969_balance_qty(total_qty, debited_qty, allotted_qty, billed_qty):
    """Unplanned-line balance, as in build(): total - debited - allotted - billed, floored at 0."""
    return max(_decimal(total_qty) - _decimal(debited_qty) - _decimal(allotted_qty) - _decimal(billed_qty), ZERO_QTY)


def _c969_entitlement_report(licenses, usage_totals):
    """One row per C969 product category, built from every C969 import-item line.

    Entitlement comes from the import items, not from plans or allocations, so unplanned
    and never-used lines are included. Per line the values are the same ones build() uses
    for an unplanned item: total = item quantity, allotted and debited from usage totals,
    balance = max(total - debited - allotted - billed, 0). Every configured C969 category
    is returned, zero where no line exists. The two fallback categories appear only when
    a line falls in them. Returns None when no licence in the set carries C969.
    """
    c969_licences = [
        licence for licence in licenses
        if any(e.norm_class_id and e.norm_class.norm_class == C969_NORM for e in licence.export_license.all())
    ]
    if not c969_licences:
        return None

    totals = {}
    unrecognised_items = []

    def bucket(category):
        if category not in totals:
            totals[category] = {
                "total_qty": ZERO_QTY, "allotted_qty": ZERO_QTY, "allotted_cif": ZERO_CIF,
                "debited_qty": ZERO_QTY, "debited_cif": ZERO_CIF, "balance_qty": ZERO_QTY,
                "hsn_codes": set(), "source_descriptions": set(), "licence_ids": set(), "line_count": 0,
            }
        return totals[category]

    for category in _C969_CONFIGURED_CATEGORIES:
        bucket(category)

    for licence in c969_licences:
        for item in licence.import_license.all():
            usage = usage_totals.get(item.id, {})
            boe_qty = usage.get("boe_qty", ZERO_QTY)
            boe_cif = usage.get("boe_cif", ZERO_CIF)
            allot_qty = usage.get("allot_qty", ZERO_QTY)
            allot_cif = usage.get("allot_cif", ZERO_CIF)
            billed_qty = usage.get("billed_qty", ZERO_QTY)
            description = (item.description or "").strip()
            hsn = item.hs_code.hs_code if item.hs_code_id else ""
            # Classification reads the product name only; HSN is reported, never used.
            category = classify_product(hsn, description, C969_NORM)
            row = bucket(category)
            row["total_qty"] += _decimal(item.quantity)
            row["allotted_qty"] += allot_qty
            row["allotted_cif"] += allot_cif
            row["debited_qty"] += boe_qty
            row["debited_cif"] += boe_cif
            row["balance_qty"] += c969_balance_qty(item.quantity, boe_qty, allot_qty, billed_qty)
            if hsn:
                row["hsn_codes"].add(hsn)
            if description:
                row["source_descriptions"].add(description)
            row["licence_ids"].add(licence.id)
            row["line_count"] += 1
            if category == UNRECOGNISED:
                unrecognised_items.append({
                    "import_item_id": item.id,
                    "serial_number": item.serial_number,
                    "licence_number": licence.license_number,
                    "description": item.description or "",
                    "quantity": _text(_decimal(item.quantity)),
                    "unit": item.unit or "",
                    "current_classifiers": sorted(item.items.values_list("name", flat=True)),
                })

    ordered = list(C969_CATEGORY_ORDER) + [c for c in totals if c not in C969_CATEGORY_ORDER]
    rows = []
    for category in ordered:
        if category not in totals:
            continue
        row = totals[category]
        if category not in _C969_CONFIGURED_CATEGORIES and row["line_count"] == 0:
            continue
        rows.append({
            "category": category,
            "hsn_code": ", ".join(sorted(row["hsn_codes"])),
            "description": category,
            "total_qty": _text(row["total_qty"]),
            "allotted_qty": _text(row["allotted_qty"]),
            "allotted_cif": _text(row["allotted_cif"]),
            "debited_qty": _text(row["debited_qty"]),
            "debited_cif": _text(row["debited_cif"]),
            "balance_qty": _text(row["balance_qty"]),
            "line_count": row["line_count"],
            "license_count": len(row["licence_ids"]),
            "source_descriptions": sorted(row["source_descriptions"]),
        })
    return {
        "columns": [{"key": k, "label": label} for k, label in C969_ENTITLEMENT_COLUMNS],
        "rows": rows,
        "unrecognised_items": unrecognised_items,
    }

