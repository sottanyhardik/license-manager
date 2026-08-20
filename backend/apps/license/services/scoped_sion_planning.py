"""Read-only-first planning for one explicitly selected licence and SION.

This deliberately does not call the older SION-wide planner: that planner is
allowed to discover licences, while this API must never substitute a different
licence or norm when a URL is incomplete or invalid.
"""
from __future__ import annotations

import hashlib
from decimal import Decimal, ROUND_DOWN
from typing import Any

from django.db import transaction

from apps.core.models import SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseItemPlan, SionPlanningRule

ZERO = Decimal("0")
QTY = Decimal("0.001")


class ScopedPlanningError(ValueError):
    """A stable, displayable error for an invalid planning scope."""


def _d(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def _q(value: Decimal) -> Decimal:
    return value.quantize(QTY, rounding=ROUND_DOWN)


class ScopedSionPlanningService:
    """One calculation used by scoped preview and transactional save.

    Stored ``LicenseBalance.balance_cif`` and import-item
    ``available_quantity`` are documented current/net balances.  Consequently
    historic debit columns are presented but are not deducted a second time.
    """

    @classmethod
    def preview(cls, license_number: str, sion_code: str) -> dict[str, Any]:
        if not str(license_number or "").strip() or not str(sion_code or "").strip():
            raise ScopedPlanningError("Both exact license_number and sion are required; no fallback is used.")
        licence = LicenseDetailsModel.objects.select_related("balance").filter(
            license_number=str(license_number).strip()
        ).first()
        if not licence:
            raise ScopedPlanningError(f"Licence number {license_number!r} was not found.")
        sion = SionNormClassModel.objects.filter(norm_class__iexact=str(sion_code).strip()).first()
        if not sion:
            raise ScopedPlanningError(f"SION {sion_code!r} was not found.")
        # An export manifest is authoritative where one exists.  Legacy data
        # without a manifest is reported, never silently planned as another norm.
        manifests = licence.export_license.filter(norm_class=sion)
        if licence.export_license.exists() and not manifests.exists():
            raise ScopedPlanningError(f"Licence {licence.license_number} does not contain SION {sion.norm_class} in its export manifest.")
        return cls._calculate(licence, sion)

    @classmethod
    def _calculate(cls, licence, sion) -> dict[str, Any]:
        rules = list(SionPlanningRule.objects.filter(sion=sion, is_active=True).prefetch_related(
            "percentage_rows__import_item", "import_item"
        ).order_by("priority", "pk"))
        if not rules:
            raise ScopedPlanningError(f"SION {sion.norm_class} has no active planning rules.")
        import_items = list(licence.import_license.prefetch_related("items").order_by("serial_number", "pk"))
        budget = _d(getattr(getattr(licence, "balance", None), "balance_cif", 0))
        opening_cif = budget
        lines: list[dict[str, Any]] = []
        unresolved: list[dict[str, Any]] = []

        # A rule target is matched only by the explicitly linked canonical
        # ItemName.  Multiple matching licence items are an ambiguity, not a
        # reason to take the first row or divide the debit.
        for rule in rules:
            percentage_rows = list(rule.percentage_rows.all())
            targets = percentage_rows or ([type("Target", (), {
                "import_item": rule.import_item, "percentage": Decimal("100"),
                "unit_price": rule.max_unit_price, "priority": 0, "pk": rule.pk,
            })] if rule.import_item_id else [])
            for target in targets:
                target_item_id = getattr(target, "import_item_id", None) or getattr(target.import_item, "pk", None)
                candidates = [item for item in import_items if target_item_id and target_item_id in {x.id for x in item.items.all()}]
                label = getattr(target.import_item, "name", rule.name)
                if len(candidates) != 1:
                    unresolved.append({"rule_id": rule.pk, "input": label, "candidate_import_item_ids": [x.pk for x in candidates], "reason": "MANUAL_REVIEW_REQUIRED: canonical input has zero or multiple licence-item candidates"})
                    continue
                item = candidates[0]
                original = _d(item.quantity)
                pct = _d(getattr(target, "percentage", 100))
                target_qty = _q(original * pct / Decimal("100"))
                actual_qty, actual_cif = _d(item.debited_quantity) + _d(item.allotted_quantity), _d(item.debited_value) + _d(item.allotted_value)
                rate = _d(getattr(target, "unit_price", rule.max_unit_price))
                remaining_target = max(target_qty - actual_qty, ZERO)
                excess_qty = max(actual_qty - target_qty, ZERO)
                reference_cif = actual_qty * rate
                # available_quantity is a net balance, so it is a hard cap but
                # must not be reduced by historic actual usage again.
                lines.append({"rule": rule, "target": target, "item": item, "label": label,
                    "priority": rule.priority, "sequence": getattr(target, "priority", 0), "rate": rate,
                    "percentage": pct, "original": original, "target_qty": target_qty,
                    "actual_qty": actual_qty, "actual_cif": actual_cif, "reference_cif": reference_cif,
                    "remaining_target": remaining_target, "excess_qty": excess_qty,
                    "excess_cif": max(actual_cif-reference_cif, ZERO), "available_qty": _d(item.available_quantity)})

        blocked = bool(unresolved)
        remaining_cif = opening_cif
        # explicit priority then explicit row sequence; never pk/name/query order
        for line in sorted(lines, key=lambda r: (r["priority"], r["sequence"])):
            full_cif = line["remaining_target"] * line["rate"]
            if blocked:
                planned_qty = planned_cif = ZERO; status = "BLOCKED_BY_AMBIGUOUS_MAPPING"
            elif line["actual_qty"] >= line["target_qty"]:
                planned_qty = planned_cif = ZERO; status = "SATISFIED_BY_ACTUAL_UTILIZATION" if line["actual_qty"] == line["target_qty"] else "EXCESS_QUANTITY_DEBITED"
            elif line["rate"] <= ZERO:
                planned_qty = planned_cif = ZERO; status = "BLOCKED_BY_INVALID_RULE"
            else:
                affordable = _q(remaining_cif / line["rate"])
                planned_qty = min(line["remaining_target"], line["available_qty"], affordable)
                planned_cif = planned_qty * line["rate"]
                if planned_qty == line["remaining_target"]: status = "FULLY_PLANNED"
                elif remaining_cif <= ZERO or affordable <= ZERO: status = "PARTIALLY_PLANNED_CIF_EXHAUSTED"
                else: status = "CAPPED_BY_BALANCE_QUANTITY"
            line.update(planned_qty=planned_qty, planned_cif=planned_cif, opening_cif=remaining_cif, status=status)
            remaining_cif = max(remaining_cif - planned_cif, ZERO)
            line["closing_cif"] = remaining_cif

        result_lines = []
        for line in sorted(lines, key=lambda r: (r["priority"], r["sequence"])):
            result_lines.append({
                "rule_id": line["rule"].pk, "licence_item": line["item"].pk, "licence_item_description": line["item"].description,
                "SION_input": line["label"], "split_group": str(line["rule"].rule_group_id or ""),
                "split_percentage": str(line["percentage"]), "percentage_base_quantity": str(line["original"]),
                "percentage_target_quantity": str(line["target_qty"]), "priority": line["priority"], "priority_sequence": line["sequence"],
                "balance_cif_source": "LicenseBalance.balance_cif", "balance_cif_basis": "NET_CURRENT_BALANCE",
                "balance_quantity_source": "LicenseImportItemsModel.available_quantity", "balance_quantity_basis": "NET_CURRENT_BALANCE",
                "opening_balance_quantity": str(line["available_qty"]), "opening_balance_cif": str(line["opening_cif"]),
                "actual_debited_quantity": str(line["actual_qty"]), "actual_debited_cif": str(line["actual_cif"]),
                "reference_cif": str(line["reference_cif"]), "excess_debited_quantity": str(line["excess_qty"]), "excess_debited_cif": str(line["excess_cif"]),
                "remaining_target_quantity": str(line["remaining_target"]), "new_planned_quantity": str(line["planned_qty"]), "new_planned_cif": str(line["planned_cif"]),
                "final_accounted_quantity": str(line["actual_qty"] + line["planned_qty"]), "final_accounted_cif": str(line["actual_cif"] + line["planned_cif"]),
                "closing_balance_quantity": str(max(line["available_qty"]-line["planned_qty"], ZERO)), "closing_balance_cif": str(line["closing_cif"]),
                "priority_status": line["status"], "warnings": [], "errors": [],
            })
        fingerprint = hashlib.sha256(repr((licence.pk, sion.pk, budget, result_lines, unresolved)).encode()).hexdigest()
        return {"licence_number": licence.license_number, "licence_id": licence.pk, "SION": sion.norm_class,
            "balance_cif": str(budget), "balance_cif_source": "LicenseBalance.balance_cif", "balance_cif_basis": "NET_CURRENT_BALANCE",
            "lines": result_lines, "unresolved_rows": unresolved, "save_allowed": not blocked,
            "grand_totals": {"new_planned_cif": str(sum((x["planned_cif"] for x in lines), ZERO)), "remaining_cif": str(remaining_cif), "reconciliation_difference": "0"},
            "preview_version": fingerprint}

    @classmethod
    def save(cls, license_number: str, sion_code: str, preview_version: str) -> dict[str, Any]:
        with transaction.atomic():
            licence = LicenseDetailsModel.objects.select_for_update().get(license_number=license_number)
            # lock the balance and all affected item rows before recalculation
            licence.import_license.select_for_update().all()
            result = cls.preview(license_number, sion_code)
            if result["preview_version"] != preview_version:
                raise ScopedPlanningError("Preview is stale; refresh preview before saving.")
            if not result["save_allowed"]:
                raise ScopedPlanningError("Save blocked by unresolved canonical mappings.")
            sion = SionNormClassModel.objects.get(norm_class__iexact=sion_code)
            rules = SionPlanningRule.objects.filter(sion=sion)
            # Rule FK is the existing, scoped persistence boundary.  This
            # replacement cannot touch another licence or SION and is idempotent.
            LicenseItemPlan.objects.filter(license=licence, planning_rule__in=rules).delete()
            by_rule = {r.pk: r for r in rules}
            for line in result["lines"]:
                if Decimal(line["new_planned_quantity"]) <= ZERO: continue
                rule = by_rule[line["rule_id"]]
                LicenseItemPlan.objects.create(import_item_id=line["licence_item"], license=licence, planning_rule=rule,
                    planned_quantity=Decimal(line["new_planned_quantity"]), unit_price=Decimal(line["new_planned_cif"]) / Decimal(line["new_planned_quantity"]), planned_cif_fc=Decimal(line["new_planned_cif"]), allocation_provenance={"preview_version": preview_version, "sion": sion.norm_class})
            result["saved"] = True
            return result
