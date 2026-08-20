"""Canonical data set for the item pivot report.

This deliberately consumes persisted effective plans and the item-linked usage
queries.  It is a report projection, not another planning engine.
"""
from collections import defaultdict
from decimal import Decimal

from apps.license.models import LicenseItemPlan
from apps.license.services.item_usage import get_item_usage_for_items

ZERO_QTY = Decimal("0.000")
ZERO_CIF = Decimal("0.00")


def _decimal(value, default=Decimal("0")):
    return Decimal(str(value if value is not None else default))


def _text(value):
    """JSON has no Decimal; retain exact values instead of converting to float."""
    return str(value)


class ItemPivotService:
    """Build a notification/purchase-status → licence → item matrix."""

    @classmethod
    def build(cls, licenses):
        licenses = list(licenses)
        ids = [license_obj.id for license_obj in licenses]
        plans = list(
            LicenseItemPlan.objects.filter(license_id__in=ids)
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
        output_groups = defaultdict(lambda: {"licenses": [], "item_groups": {}})

        for license_obj in licenses:
            import_items = list(license_obj.import_license.all())
            item_by_id = {item.id: item for item in import_items}
            total_cif = sum((_decimal(item.cif_fc) for item in license_obj.export_license.all()), ZERO_CIF)
            debited_cif = sum((sum((_decimal(row.cif_fc) for row in usage[item.id]["boes"]), ZERO_CIF) for item in import_items), ZERO_CIF)
            allotted_cif = sum((sum((_decimal(row.cif_fc) for row in usage[item.id]["allotments"]), ZERO_CIF) for item in import_items), ZERO_CIF)
            cells = {}
            planned_cif = ZERO_CIF

            for plan in plans_by_license[license_obj.id]:
                provenance = plan.allocation_provenance or {}
                item_name = (plan.item_name.name if plan.item_name_id else provenance.get("canonical_item_name")) or "UNMAPPED ITEM"
                sion = provenance.get("sion") or next((getattr(x.norm_class, "norm_class", "") for x in license_obj.export_license.all() if x.norm_class_id), "")
                key = f"{sion}:{item_name.strip().upper().replace(' ', '_')}"
                source_ids = [int(source_id) for source_id in provenance.get("source_item_ids", []) if str(source_id).isdigit()] or [plan.import_item_id]
                source_items = [item_by_id[source_id] for source_id in source_ids if source_id in item_by_id]
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
                    boe_qty = sum((sum((_decimal(row.qty) for row in usage[item.id]["boes"]), ZERO_QTY) for item in source_items), ZERO_QTY)
                    boe_cif = sum((sum((_decimal(row.cif_fc) for row in usage[item.id]["boes"]), ZERO_CIF) for item in source_items), ZERO_CIF)
                    allot_qty = sum((sum((_decimal(row.qty) for row in usage[item.id]["allotments"]), ZERO_QTY) for item in source_items), ZERO_QTY)
                    allot_cif = sum((sum((_decimal(row.cif_fc) for row in usage[item.id]["allotments"]), ZERO_CIF) for item in source_items), ZERO_CIF)
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
                if is_percentage:
                    balance_qty = adjusted_total_qty - own_actual_qty
                else:
                    balance_qty = _decimal(provenance.get("audit_remaining_quantity", plan.planned_quantity))
                    if balance_qty == _decimal(plan.planned_quantity):
                        balance_qty = total_qty - boe_qty - allot_qty
                plan_qty = _decimal(plan.planned_quantity)
                plan_cif = _decimal(plan.planned_cif_fc)
                planned_cif += plan_cif
                description = next((item.description for item in source_items if item.description), item_name)
                hsn = next((item.hs_code.hs_code for item in source_items if item.hs_code_id), "")
                cells[key] = {
                    "hsn_code": hsn, "description": description, "total_qty": _text(adjusted_total_qty),
                    "percentage_target_qty": _text(percentage_target_qty), "own_excess_qty": _text(own_excess_qty),
                    "excess_other_item_qty": _text(excess_other_item_qty), "adjusted_total_qty": _text(adjusted_total_qty),
                    "allotted_qty": _text(allot_qty), "debited_qty": _text(boe_qty),
                    "boe_used_cif": _text(boe_cif), "allotted_cif": _text(allot_cif),
                    "balance_qty": _text(balance_qty), "plan_qty": _text(plan_qty),
                    "planned_cif": _text(plan_cif), "restriction_percent": None,
                    "restriction_value": None,
                }
                # Add the column to the licence's notification/company group
                # after its identity is known below.

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
                sion = provenance.get("sion") or next((getattr(x.norm_class, "norm_class", "") for x in license_obj.export_license.all() if x.norm_class_id), "")
                key = f"{sion}:{name.strip().upper().replace(' ', '_')}"
                group["item_groups"].setdefault(key, {"key": key, "name": name, "sion": sion, "priority": plan.planning_rule_priority or 999999, "sequence": plan.id})
            issues = []
            for item_key, cell in cells.items():
                adjusted_qty = _decimal(cell["adjusted_total_qty"])
                used_qty = _decimal(cell["debited_qty"]) + _decimal(cell["allotted_qty"])
                available_qty = adjusted_qty - used_qty
                planned_qty = _decimal(cell["plan_qty"])
                balance_after_plan = available_qty - planned_qty
                cell["available_qty"] = _text(available_qty)
                cell["balance_qty_after_plan"] = _text(balance_after_plan)
                if available_qty < ZERO_QTY:
                    issues.append({"item_key": item_key, "type": "over_utilized", "severity": "critical", "actual_excess_qty": _text(-available_qty), "planned_excess_qty": _text(ZERO_QTY), "available_qty": _text(available_qty), "planned_qty": _text(planned_qty), "balance_qty": _text(balance_after_plan)})
                if balance_after_plan < ZERO_QTY:
                    issues.append({"item_key": item_key, "type": "over_planned", "severity": "warning", "actual_excess_qty": _text(ZERO_QTY), "planned_excess_qty": _text(-balance_after_plan), "available_qty": _text(available_qty), "planned_qty": _text(planned_qty), "balance_qty": _text(balance_after_plan)})
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
            group["licenses"].sort(key=lambda row: (row["expiry_date"] or "", row["license_number"]))
            group["license_count"] = len(group["licenses"])
            group["issue_license_count"] = sum(1 for row in group["licenses"] if row["issue_count"])
            group["issue_record_count"] = sum(row["issue_count"] for row in group["licenses"])
            group["item_groups"] = sorted(group["item_groups"].values(), key=lambda row: (row["sion"], row["priority"], row["sequence"], row["name"]))
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
                    field: _text(sum((_decimal(cell.get(field)) for cell in applicable), ZERO_CIF if field in {"restriction_value", "planned_cif"} else ZERO_QTY))
                    for field in ("total_qty", "allotted_qty", "debited_qty", "balance_qty", "restriction_value", "plan_qty", "planned_cif")
                }
            group["totals"] = {
                **{key: _text(value) for key, value in totals.items() if key != "items"},
                "items": totals["items"],
            }
            groups.append(group)
        groups = sorted(groups, key=lambda row: (row["notification_number"], row["purchase_status"]["name"]))
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
        summary["overdrawn_cif"] = max(summary["effective_planned_cif"] - summary["actual_balance_cif"], ZERO_CIF)
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
            total_qty, boe_qty, allotted_qty, planned_qty = values("total_qty"), values("debited_qty"), values("allotted_qty"), values("plan_qty")
            actual_qty = boe_qty + allotted_qty
            planned_cif = values("planned_cif", ZERO_CIF)
            actual_cif = values("boe_used_cif", ZERO_CIF) + values("allotted_cif", ZERO_CIF)
            available_qty = total_qty - actual_qty
            balance_qty = available_qty - planned_qty
            contributing = [
                {"license_id": cell["license_id"], "license_number": cell["license_number"], "available_qty": cell["available_qty"], "planned_qty": cell["plan_qty"], "planned_excess_qty": _text(max(-_decimal(cell["balance_qty_after_plan"]), ZERO_QTY))}
                for cell in cells if _decimal(cell["balance_qty_after_plan"]) < ZERO_QTY
            ]
            actual_contributing = [cell for cell in cells if _decimal(cell["available_qty"]) < ZERO_QTY]
            status = "over_utilized" if actual_contributing else ("over_planned" if contributing else ("planned" if planned_qty else "available"))
            items.append({
                "key": key, "item_name": row["name"], "sion": row["sion"],
                "priority": row["priority"], "sequence": row["sequence"],
                "hsn_codes": sorted({cell["hsn_code"] for cell in cells if cell.get("hsn_code")}),
                "license_count": len(cells), "total_qty": _text(total_qty), "boe_used_qty": _text(boe_qty),
                "allotted_qty": _text(allotted_qty), "actual_used_qty": _text(actual_qty),
                "available_qty": _text(available_qty), "planned_qty": _text(planned_qty), "balance_qty_after_plan": _text(balance_qty),
                "actual_used_cif": _text(actual_cif), "available_cif_before_plan": None,
                "planned_cif": _text(planned_cif), "balance_cif_after_plan": None,
                "average_planned_unit_price": _text(planned_cif / planned_qty) if planned_qty else None,
                "status": status, "planned_excess_qty": _text(sum((_decimal(row["planned_excess_qty"]) for row in contributing), ZERO_QTY)),
                "actual_excess_qty": _text(sum((-_decimal(cell["available_qty"]) for cell in actual_contributing), ZERO_QTY)),
                "contributing_licenses": contributing,
                "licenses": cells,
            })
        items = sorted(items, key=lambda row: (row["sion"], row["priority"], row["sequence"], row["item_name"]))
        global_summary = {key: _text(value) if isinstance(value, Decimal) else value for key, value in summary.items()}
        # Aliases make the report contract explicit while preserving the
        # existing consumers during the presentation-only migration.
        return {"groups": groups, "notification_groups": groups, "summary": global_summary,
                "global_summary": global_summary, "items": items, "item_columns": [{"key": row["key"], "name": row["item_name"], "sion": row["sion"]} for row in items],
                "grand_total": {"notification_count": len(groups), "license_count": global_summary["license_count"], "summary": global_summary, "item_summary": items},
                "report_version": "canonical-item-pivot-v1"}
