"""Canonical data set for the item pivot report.

This deliberately consumes persisted effective plans and the item-linked usage
queries.  It is a report projection, not another planning engine.
"""
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from apps.license.models import LicenseItemPlan
from apps.license.services.item_usage import (
    get_item_usage_for_items,
    billed_no_boe_bulk_map,
    billed_no_boe_qty_bulk_map,
)
from apps.license.services.c969_product_classifier import (
    C969_CATEGORY_ORDER,
    C969_CLASSIFIER_ORDER,
    C969_GENERIC_CATEGORIES,
    C969_NORM,
    UNRECOGNISED,
)
from apps.license.services.product_classification import classify_product, pivot_category_sort_key

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
    existing_sources.update(candidate_sources)
    existing["source_items"] = [existing_sources[key] for key in sorted(existing_sources)]

    for field in ("plan_qty", "planned_cif", "effective_planned_qty", "effective_planned_cif"):
        existing[field] = _text(_decimal(existing.get(field)) + _decimal(candidate.get(field)))

    # Repeated split rows have the same source entitlement/usage, so retain
    # it once.  Distinct source rows contribute their own independently
    # reconciled quantities and CIFs.
    if new_source_ids:
        for field in (
            "total_qty", "percentage_target_qty", "own_excess_qty",
            "excess_other_item_qty", "adjusted_total_qty", "allotted_qty",
            "debited_qty", "boe_used_cif", "allotted_cif", "balance_qty",
            "canonical_item_cif_capacity",
        ):
            existing[field] = _text(_decimal(existing.get(field)) + _decimal(candidate.get(field)))
        if existing.get("available_cif") is not None and candidate.get("available_cif") is not None:
            existing["available_cif"] = _text(_decimal(existing["available_cif"]) + _decimal(candidate["available_cif"]))

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


class ItemPivotService:
    """Build a notification/purchase-status → licence → item matrix."""

    @classmethod
    def build(cls, licenses):
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

        # Load active SION planning rules so we can look up cif_restriction_percentage
        # per item.  We'll build a map: {sion_norm: {item_name_id: restriction_pct}}.
        from apps.license.models import SionPlanningRule, SionPlanningUnitValueRow, SionPlanningPercentageRow
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

        for license_obj in licenses:
            import_items = list(license_obj.import_license.all())
            item_by_id = {item.id: item for item in import_items}
            export_items = list(license_obj.export_license.all())
            default_sion = next(
                (getattr(item.norm_class, "norm_class", "") for item in export_items if item.norm_class_id),
                "",
            )
            total_cif = sum((_decimal(item.cif_fc) for item in export_items), ZERO_CIF)
            debited_cif = sum((usage_totals[item.id]["boe_cif"] for item in import_items), ZERO_CIF)
            allotted_cif = sum((usage_totals[item.id]["allot_cif"] for item in import_items), ZERO_CIF)
            cells = {}
            planned_cif = ZERO_CIF

            # Look up CIF restriction map for this license's SION norm
            license_cif_restriction_map = cif_restriction_by_sion_item.get(default_sion, {})

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
                source_ids = [int(source_id) for source_id in provenance.get("source_item_ids", []) if str(source_id).isdigit()] or [plan.import_item_id]
                source_items = [item_by_id[source_id] for source_id in source_ids if source_id in item_by_id]
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
                key = f"{product_category or 'UNCLASSIFIED'}:{sion}"
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
                if not boe_qty and not allot_qty and not is_percentage:
                    boe_qty = sum((usage_totals[item.id]["boe_qty"] for item in source_items), ZERO_QTY)
                    boe_cif = sum((usage_totals[item.id]["boe_cif"] for item in source_items), ZERO_CIF)
                    allot_qty = sum((usage_totals[item.id]["allot_qty"] for item in source_items), ZERO_QTY)
                    allot_cif = sum((usage_totals[item.id]["allot_cif"] for item in source_items), ZERO_CIF)
                billed_qty = sum((usage_totals[item.id]["billed_qty"] for item in source_items), ZERO_QTY)
                billed_cif = sum((usage_totals[item.id]["billed_cif"] for item in source_items), ZERO_CIF)
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
                            "hsn_code": item.hs_code.hs_code if item.hs_code_id else "",
                            "description": item.description or "",
                            "quantity": _text(_decimal(item.quantity)),
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
                }
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
                item_usage_boe_qty = usage_totals[item.id]["boe_qty"]
                item_usage_boe_cif = usage_totals[item.id]["boe_cif"]
                item_usage_allot_qty = usage_totals[item.id]["allot_qty"]
                item_usage_allot_cif = usage_totals[item.id]["allot_cif"]
                item_usage_billed_qty = usage_totals[item.id]["billed_qty"]
                item_usage_billed_cif = usage_totals[item.id]["billed_cif"]
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
                            "hsn_code": hsn_str,
                            "description": item.description or "",
                            "quantity": _text(item_total_qty),
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
                    "item_cif_cap": None, "canonical_item_cif_capacity": _text(item_total_cif),
                    "available_cif": None,
                    "restriction_percent": _text(unplanned_restriction_pct) if unplanned_restriction_pct is not None else None,
                    "restriction_value": _text(unplanned_restriction_value) if unplanned_restriction_value is not None else None,
                    "planning_priority": None, "planning_rule_id": None,
                    "planning_rule_name": None, "planning_strategy": None,
                    "priority_item_order": None, "priority_source": "unplanned",
                }
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
                # Use the same product category key as the cells dict
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
                "planned_cif": _text(planned_cif), "balance_cif": _text(max(total_cif - debited_cif - allotted_cif, ZERO_CIF)), "items": cells,
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
            "actual_balance_cif": sum((_decimal(row["balance_cif"]) for row in all_licenses), ZERO_CIF),
            "effective_planned_cif": sum((_decimal(row["planned_cif"]) for row in all_licenses), ZERO_CIF),
        }
        summary["total_actual_used_cif"] = summary["actual_boe_cif"] + summary["actual_allotment_cif"]
        summary["final_balance_cif"] = max(summary["actual_balance_cif"] - summary["effective_planned_cif"], ZERO_CIF)
        # Shared licence CIF is reconciled at licence level.  Keep actual
        # overdraw and planning overage separate; neither is an item cap.
        summary["overdrawn_cif"] = max(summary["total_actual_used_cif"] - summary["total_cif"], ZERO_CIF)
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

