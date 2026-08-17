"""Safe, data-driven SION planning rules.

Rules are predicates over a deliberately small read-only context.  JSON is
walked as data: no ``eval``, dynamic imports, attributes, SQL, or callables.
Matched lines are handed to ``CanonicalPlanningService`` for every quantity,
CIF, concurrency and persistence invariant.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.license.models import LicenseDetailsModel, SionPlanningRule
from apps.license.services.canonical_planning_service import (
    CanonicalPlanningService, CompanyIsolationError, SionPlanningError,
)

MAX_DEPTH = 12
MAX_NODES = 128
FIELDS = {
    "available_qty", "total_qty", "available_value", "cif_fc",
    "license_balance_cif", "hs_code", "description", "condition_type",
    "is_restricted", "unit", "serial_number",
}
FIELD_ALIASES = {"HSN": "hs_code", "PRODUCT_DESCRIPTION": "description"}
BOOL_OPS = {"and", "or", "not"}
CMP_OPS = {"eq", "ne", "gt", "gte", "lt", "lte", "contains", "not_contains", "in", "starts_with"}


def _op(node):
    op = str(node.get("op", node.get("comparator", node.get("operator", "")))).strip().lower()
    return {"equals": "eq", "not_equals": "ne"}.get(op, op)


def validate_expression(expression: Any) -> None:
    count = 0
    leaves = set()

    def walk(node, depth=0):
        nonlocal count
        count += 1
        if count > MAX_NODES or depth > MAX_DEPTH:
            raise ValidationError("Rule expression is too large or deeply nested.")
        if not isinstance(node, dict):
            raise ValidationError("Every rule expression node must be an object.")
        op = _op(node)
        if op in {"and", "or"}:
            children = node.get("args", node.get("conditions"))
            if not isinstance(children, list) or not children:
                raise ValidationError(f"{op.upper()} requires a non-empty conditions list.")
            for child in children:
                walk(child, depth + 1)
            return
        if op == "not":
            child = node.get("arg", node.get("condition"))
            if child is None and isinstance(node.get("conditions"), list) and len(node["conditions"]) == 1:
                child = node["conditions"][0]
            if child is None:
                raise ValidationError("NOT requires one condition.")
            walk(child, depth + 1)
            return
        if op not in CMP_OPS:
            raise ValidationError(f"Unsupported rule operator: {op or '<empty>'}.")
        field = FIELD_ALIASES.get(node.get("field"), node.get("field"))
        if field not in FIELDS:
            raise ValidationError(f"Unsupported rule field: {field!r}.")
        if "value" not in node:
            raise ValidationError(f"{op.upper()} requires a value.")
        signature = (field, op, str(node["value"]).strip().casefold())
        if signature in leaves:
            raise ValidationError("Duplicate rule conditions are not allowed.")
        inverse = {"contains": "not_contains", "not_contains": "contains", "eq": "ne", "ne": "eq"}.get(op)
        if inverse and (field, inverse, signature[2]) in leaves:
            raise ValidationError("Conflicting rule conditions are not allowed.")
        leaves.add(signature)

    walk(expression)


def _decimal(value):
    if isinstance(value, bool) or value is None:
        raise InvalidOperation
    return Decimal(str(value))


def _normalized_text(field, value):
    text = " ".join(str(value or "").split()).casefold()
    if field == "hs_code":
        return "".join(ch for ch in text if ch.isalnum())
    return text


def evaluate_expression(expression: dict, context: dict) -> bool:
    validate_expression(expression)

    def evaluate(node):
        op = _op(node)
        if op in {"and", "or"}:
            values = [evaluate(child) for child in node.get("args", node.get("conditions"))]
            return all(values) if op == "and" else any(values)
        if op == "not":
            child = node.get("arg", node.get("condition"))
            if child is None:
                child = node["conditions"][0]
            return not evaluate(child)
        field = FIELD_ALIASES.get(node.get("field"), node.get("field"))
        left, right = context.get(field), node["value"]
        if op in {"gt", "gte", "lt", "lte"}:
            try:
                left, right = _decimal(left), _decimal(right)
            except (InvalidOperation, ValueError, TypeError):
                return False
            return {"gt": left > right, "gte": left >= right,
                    "lt": left < right, "lte": left <= right}[op]
        if op in {"contains", "not_contains"}:
            contained = _normalized_text(field, right) in _normalized_text(field, left)
            return contained if op == "contains" else not contained
        if op == "starts_with":
            return _normalized_text(field, left).startswith(_normalized_text(field, right))
        if op == "in":
            return isinstance(right, list) and any(
                str(left).casefold() == str(value).casefold() for value in right
            )
        equal = (
            left == right if isinstance(left, bool) or isinstance(right, bool)
            else _normalized_text(field, left) == _normalized_text(field, right)
        )
        return equal if op == "eq" else not equal

    return evaluate(expression)


def _item_context(item, license_balance):
    return {
        "available_qty": item.available_quantity,
        "total_qty": item.quantity,
        "available_value": item.available_value,
        "cif_fc": item.cif_fc,
        "license_balance_cif": license_balance,
        "hs_code": getattr(item.hs_code, "hs_code", "") if item.hs_code_id else "",
        "description": item.description or "",
        "condition_type": item.condition_type or "",
        "is_restricted": item.is_restricted,
        "unit": item.unit,
        "serial_number": item.serial_number,
    }


class SionRulePlanningService:
    @staticmethod
    def preview(rule: SionPlanningRule, license_ids, *, company_id=None):
        base = LicenseDetailsModel.objects.filter(
            export_license__norm_class_id=rule.sion_id,
        )
        if license_ids:
            lids = CanonicalPlanningService._strict_id_list(license_ids, "license_ids")
            base = base.filter(pk__in=lids)
        else:
            scoped = base.filter(exporter_id=company_id) if company_id is not None else base
            lids = list(scoped.order_by("pk").values_list("pk", flat=True).distinct())
        licenses = list(
            base.filter(pk__in=lids).distinct()
            .select_related("exporter")
            .prefetch_related("export_license", "import_license__hs_code", "import_license__items")
            .order_by("pk")
        )
        if len(licenses) != len(lids):
            raise SionPlanningError("One or more selected licenses are unavailable.")
        if company_id is not None and any(obj.exporter_id != int(company_id) for obj in licenses):
            raise CompanyIsolationError("One or more selected licenses belong to another company.")
        if any(not any(row.norm_class_id == rule.sion_id for row in obj.export_license.all()) for obj in licenses):
            raise SionPlanningError("The rule SION is not applicable to every selected license.")

        competitors = list(SionPlanningRule.objects.filter(
            sion_id=rule.sion_id, unit=rule.unit, is_active=True,
        ).exclude(pk=rule.pk).order_by("priority", "pk"))
        from apps.core.models import UnitPriceModel
        price_by_name = {
            " ".join(row.name.split()).casefold(): row.unit_price
            for row in UnitPriceModel.objects.all().only("name", "unit_price")
        }
        from apps.license.services.balance_calculator import LicenseBalanceCalculator
        balances = LicenseBalanceCalculator.calculate_financial_balance_for_licenses(
            [license_obj.pk for license_obj in licenses],
        )
        results, conflicts = [], []
        for license_obj in licenses:
            license_balance = balances.get(license_obj.pk, Decimal("0"))
            matched, shadowed = [], []
            for item in license_obj.import_license.all():
                if str(item.unit).casefold() != str(rule.unit).casefold():
                    continue
                context = _item_context(item, license_balance)
                if not evaluate_expression(rule.expression, context):
                    continue
                competing = [other for other in competitors if evaluate_expression(other.expression, context)]
                winning_priority = min([rule.priority, *[other.priority for other in competing]])
                tied = [other for other in competing if other.priority == rule.priority == winning_priority]
                if tied:
                    conflict = {
                        "license_id": license_obj.pk, "import_item_id": item.pk,
                        "rule_ids": sorted([rule.pk, *[other.pk for other in tied]]),
                        "message": "Multiple active rules with the same priority match this item.",
                    }
                    conflicts.append(conflict)
                    continue
                if rule.priority != winning_priority:
                    shadowed.append(item.pk)
                    continue
                current_price = item.hs_code.unit_price if item.hs_code_id else Decimal("0")
                price_source = "HS_CODE"
                if current_price <= 0:
                    price_source = "UNIT_PRICE_MASTER"
                    for item_name in item.items.all():
                        candidate = price_by_name.get(" ".join(item_name.name.split()).casefold())
                        if candidate is not None and candidate > 0:
                            current_price = candidate
                            break
                if current_price <= 0:
                    price_status = "MISSING"
                elif current_price > rule.max_unit_price:
                    price_status = "ABOVE_MAX"
                else:
                    price_status = "WITHIN_MAX"
                line = {
                    "import_item_id": item.pk,
                    "description": item.description,
                    "unit": item.unit,
                    "available_qty": item.available_quantity,
                    "planned_quantity": item.available_quantity,
                    "max_unit_price": rule.max_unit_price,
                    "current_unit_price": current_price,
                    "price_source": price_source,
                    "price_status": price_status,
                    "context": context,
                }
                matched.append(line)
                if price_status != "WITHIN_MAX":
                    conflicts.append({
                        "license_id": license_obj.pk, "import_item_id": item.pk,
                        "rule_ids": [rule.pk], "price_status": price_status,
                        "current_unit_price": current_price,
                        "max_unit_price": rule.max_unit_price,
                        "message": "Current unit price is missing or exceeds the rule ceiling.",
                    })
            results.append({
                "license_id": license_obj.pk,
                "license_number": license_obj.license_number,
                "matched_lines": matched,
                "shadowed_item_ids": shadowed,
            })
        return {
            "rule": {"id": rule.pk, "sion": rule.sion_id, "name": rule.name, "version": rule.version},
            "licenses_requested": len(lids), "results": results,
            "conflicts": conflicts, "can_plan": not conflicts,
        }

    @staticmethod
    def plan(rule: SionPlanningRule, license_ids, *, company_id=None):
        if not rule.is_active:
            raise SionPlanningError("Only an active rule can be planned.")
        with transaction.atomic():
            preview = SionRulePlanningService.preview(rule, license_ids, company_id=company_id)
            locked_ids = sorted(row["license_id"] for row in preview["results"])
            # Serialize the idempotency check and canonical write for the full
            # population. A second identical request waits, then observes the
            # committed plan and returns UNCHANGED instead of replacing it.
            list(LicenseDetailsModel.objects.select_for_update().filter(
                pk__in=locked_ids,
            ).order_by("pk").values_list("pk", flat=True))
            preview = SionRulePlanningService.preview(rule, locked_ids, company_id=company_id)
            if preview["conflicts"]:
                raise SionPlanningError("Rule conflicts must be resolved before planning.", conflicts=preview["conflicts"])
            write_results = []
            for result in preview["results"]:
                lines = [{
                    "import_item_id": line["import_item_id"],
                    "requested_quantity": line["planned_quantity"],
                    "unit_price": line["current_unit_price"],
                    "note": f"SION rule {rule.pk} v{rule.version}",
                } for line in result["matched_lines"]]
                if not lines:
                    continue
                if CanonicalPlanningService._generated_plan_matches_current(
                    result["license_id"], lines,
                ):
                    write_results.append({
                        "license_id": result["license_id"],
                        "mutation_status": "UNCHANGED",
                    })
                    continue
                write_results.append(CanonicalPlanningService.build_canonical_plan(
                    license_id=result["license_id"], norm_class=rule.sion.norm_class,
                    items=lines, force_replan=True, company_id=company_id,
                ))
            preview["write_results"] = write_results
            preview["planned_licenses"] = len(write_results)
            return preview
