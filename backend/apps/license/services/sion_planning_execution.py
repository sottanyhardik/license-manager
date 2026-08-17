"""Central bridge from persisted SION rules to proven legacy mechanics.

This is intentionally migration infrastructure.  Classification is owned by
saved database rules; allocation remains in the mature E1/E5 waterfall
functions.  Dispatch is kept here so views, reports and exports never grow
norm-specific branches.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from apps.license.services.sion_rule_engine import evaluate_expression


class PlannerConfigurationError(ValueError):
    pass


PLAN_MODE_NEW = "NEW"
PLAN_MODE_ALL = "ALL"
PLAN_MODES = frozenset((PLAN_MODE_NEW, PLAN_MODE_ALL))


def normalize_plan_mode(mode: str | None) -> str:
    """Return the canonical execution mode used by every planning interface.

    Historically ``plan_norms`` skipped licences already planned to at least
    99% unless ``--all`` was supplied.  ``NEW`` and ``ALL`` deliberately map
    to that existing ``force_replan`` contract instead of introducing another
    definition of "already planned" here.
    """
    normalized = str(mode or PLAN_MODE_NEW).strip().upper()
    if normalized not in PLAN_MODES:
        raise PlannerConfigurationError(
            f"Unsupported planning mode {mode!r}. Expected NEW or ALL."
        )
    return normalized


class LegacyPlannerAdapter(Protocol):
    def execute(self, records: list[dict[str, Any]], balance_cif: Any, configuration: "ResolvedPlannerConfiguration", *, options: dict[str, Any] | None = None): ...
    def compute_license(self, license_obj, configuration: "ResolvedPlannerConfiguration", *, preview: bool): ...


@dataclass(frozen=True)
class ResolvedPlannerConfiguration:
    sion_code: str
    rules: tuple[Any, ...]
    output_by_rule_key: dict[str, str]

    @property
    def price_by_output(self) -> dict[str, Decimal]:
        result = {}
        for rule in self.rules:
            output = getattr(rule, "execution_output", "")
            if output:
                result[output] = Decimal(str(rule.max_unit_price))
        return result

    def classify(self, record: dict[str, Any]) -> str | None:
        matched = self.match(record)
        return matched[1] if matched else None

    def match(self, record: dict[str, Any]):
        """Return ``(rule, output)`` for the first saved priority match."""
        context = {
            "hs_code": record.get("hs_code", record.get("hsn", "")),
            "description": record.get("description", record.get("product_description", "")),
            "item_key": record.get("item_key", record.get("item_name", "")),
            "available_qty": record.get("available_quantity", record.get("quantity", record.get("qty", 0))),
            "total_qty": record.get("quantity", record.get("qty", 0)),
            "available_value": record.get("available_value", 0),
            "cif_fc": record.get("cif_fc", 0),
            "license_balance_cif": record.get("license_balance_cif", 0),
            "condition_type": record.get("condition_type", ""),
            "is_restricted": record.get("is_restricted", False),
            "unit": record.get("unit", ""),
            "serial_number": record.get("serial_number", 0),
        }
        for rule in self.rules:
            expression = rule.expression if hasattr(rule, "expression") else rule["expression"]
            if evaluate_expression(expression, context):
                explicit_output = getattr(rule, "execution_output", "") if not isinstance(rule, dict) else rule.get("execution_output", "")
                if explicit_output:
                    return rule, explicit_output
                stable_key = rule.stable_key if hasattr(rule, "stable_key") else rule.get("stable_key")
                output = self.output_by_rule_key.get(str(stable_key or ""))
                if not output:
                    rule_id = rule.get("id") if isinstance(rule, dict) else getattr(rule, "pk", None)
                    output = self.output_by_rule_key.get(f"pk:{rule_id}")
                if not output:
                    raise PlannerConfigurationError(
                        f"Saved rule {stable_key or getattr(rule, 'pk', '<unknown>')} has no execution output mapping."
                    )
                return rule, output
        return None


class _E1Adapter:
    def execute(self, records, balance_cif, configuration, *, options=None):
        from apps.license.services.e1_plan import E1Item, plan_e1_items

        items = []
        for index, record in enumerate(records):
            category = configuration.classify(record)
            if category:
                items.append(E1Item(
                    record.get("record_id", record.get("id", index)), category,
                    Decimal(str(record.get("available_quantity", record.get("quantity", record.get("qty", 0))))),
                ))
        options = options or {}
        return plan_e1_items(items, balance_cif, min_plan_qty=Decimal(str(options.get("min_plan_qty", 0))))

    def compute_license(self, license_obj, configuration, *, preview):
        from apps.license.services.e1_auto_plan import compute_e1_auto_plan
        return compute_e1_auto_plan(
            license_obj, configuration=configuration, create_item_names=not preview,
        )


class _E5Adapter:
    def execute(self, records, balance_cif, configuration, *, options=None):
        from apps.license.services.e5_plan import E5Item, plan_e5_items

        items = []
        for index, record in enumerate(records):
            category = configuration.classify(record)
            if category:
                items.append(E5Item(
                    record.get("record_id", record.get("id", index)), category,
                    Decimal(str(record.get("available_quantity", record.get("quantity", record.get("qty", 0))))),
                ))
        options = options or {}
        return plan_e5_items(
            items, balance_cif,
            min_plan_qty=Decimal(str(options.get("min_plan_qty", 0))),
            floor_qty=bool(options.get("floor_qty", False)),
        )

    def compute_license(self, license_obj, configuration, *, preview):
        from apps.license.services.e5_auto_plan import compute_e5_auto_plan
        return compute_e5_auto_plan(
            license_obj, configuration=configuration, create_item_names=not preview,
        )


class _LegacyFactoryAdapter:
    """Central compatibility bridge for planners not yet DB-classified.

    E126/E132/A3627 still contain proven mechanics and configuration together.
    Keeping this fallback in the one registry preserves existing CLI callers
    while their classifiers are migrated; API/CLI dispatch must not re-create
    PlannerFactory branches of their own.
    """
    requires_configuration = False

    def execute(self, records, balance_cif, configuration, *, options=None):
        raise PlannerConfigurationError(
            f"Record-level execution is not available for {configuration.sion_code}."
        )

    def compute_license(self, license_obj, configuration, *, preview):
        from apps.license.services.planner_factory import PlannerFactory
        result = PlannerFactory.run(license_obj, configuration.sion_code)
        return result.lines, result.remaining_cif


class SionPlanningExecutionService:
    """One registry and configuration loader for transitional execution."""

    _registry: dict[str, LegacyPlannerAdapter] = {
        "E1": _E1Adapter(),
        "E5": _E5Adapter(),
        "E126": _LegacyFactoryAdapter(),
        "E132": _LegacyFactoryAdapter(),
        "A3627": _LegacyFactoryAdapter(),
    }

    @classmethod
    def register(cls, sion_code: str, adapter: LegacyPlannerAdapter) -> None:
        cls._registry[sion_code.strip().upper()] = adapter

    @classmethod
    def supports(cls, sion) -> bool:
        if sion.norm_class.strip().upper() not in cls._registry:
            return False
        from apps.license.models import SionPlanningProfile
        return SionPlanningProfile.objects.filter(sion=sion).exists()

    @classmethod
    def resolve_configuration(cls, sion) -> ResolvedPlannerConfiguration:
        from apps.license.models import SionPlanningProfile, SionPlanningRule

        rules = tuple(SionPlanningRule.objects.filter(
            sion=sion, is_active=True,
        ).order_by("priority", "pk"))
        if not rules:
            adapter = cls._registry.get(sion.norm_class.strip().upper())
            if adapter is not None and not getattr(adapter, "requires_configuration", True):
                return ResolvedPlannerConfiguration(
                    sion.norm_class.strip().upper(), (), {},
                )
            raise PlannerConfigurationError("The selected SION has no active saved rules.")
        profile = SionPlanningProfile.objects.filter(sion=sion).order_by(
            "-is_active", "-version", "-pk",
        ).prefetch_related("actions").first()
        if profile is None:
            raise PlannerConfigurationError("The selected SION has no active execution profile.")
        output_by_rule_key: dict[str, str] = {}
        for action in profile.actions.filter(is_active=True).order_by("priority", "pk"):
            output_by_rule_key.update(action.config.get("rule_outputs", {}))
        allowed_outputs = set(output_by_rule_key.values())
        for rule in rules:
            if rule.execution_output:
                if rule.execution_output not in allowed_outputs:
                    raise PlannerConfigurationError(
                        f"Saved rule {rule.pk} has unsupported execution output {rule.execution_output!r}."
                    )
                continue
            if rule.stable_key and rule.stable_key in output_by_rule_key:
                continue
            raise PlannerConfigurationError(
                f"Saved rule {rule.pk} has no execution output. Save an execution bucket before planning."
            )
        return ResolvedPlannerConfiguration(
            sion.norm_class.strip().upper(), rules, output_by_rule_key,
        )

    @classmethod
    def execute(cls, sion, records, balance_cif, *, options=None, configuration=None):
        configuration = configuration or cls.resolve_configuration(sion)
        try:
            adapter = cls._registry[configuration.sion_code]
        except KeyError as exc:
            raise PlannerConfigurationError(
                f"No transitional execution adapter is registered for {configuration.sion_code}."
            ) from exc
        return adapter.execute(list(records), balance_cif, configuration, options=options)

    @classmethod
    def _eligible_licenses(cls, sion, license_ids=None, *, company_id=None):
        from apps.license.models import LicenseDetailsModel
        from django.db.models import Q
        from django.utils import timezone
        from apps.license.services.canonical_planning_service import (
            CanonicalPlanningService, CompanyIsolationError,
        )

        base = LicenseDetailsModel.objects.filter(
            export_license__norm_class=sion,
            flags__is_active=True,
            flags__is_expired=False,
        ).filter(
            Q(license_expiry_date__isnull=True)
            | Q(license_expiry_date__gte=timezone.localdate()),
        )
        if license_ids:
            ids = CanonicalPlanningService._strict_id_list(license_ids, "license_ids")
            base = base.filter(pk__in=ids)
        else:
            scoped = base.filter(exporter_id=company_id) if company_id is not None else base
            ids = list(scoped.order_by("pk").values_list("pk", flat=True).distinct())
        licenses = list(base.filter(pk__in=ids).distinct().select_related("exporter").order_by("pk"))
        if len(licenses) != len(ids):
            raise PlannerConfigurationError("One or more selected licenses are unavailable for this SION.")
        if company_id is not None and any(row.exporter_id != int(company_id) for row in licenses):
            raise CompanyIsolationError("One or more selected licenses belong to another company.")
        from apps.license.services.balance_calculator import LicenseBalanceCalculator
        live_balances = LicenseBalanceCalculator.calculate_financial_balance_for_licenses(
            [row.pk for row in licenses]
        )
        licenses = [row for row in licenses if live_balances.get(row.pk, Decimal("0")) > 0]
        return licenses, live_balances

    @classmethod
    def _compute_license(cls, license_obj, configuration, *, preview):
        try:
            adapter = cls._registry[configuration.sion_code]
        except KeyError as exc:
            raise PlannerConfigurationError(
                f"No transitional execution adapter is registered for {configuration.sion_code}."
            ) from exc
        return adapter.compute_license(license_obj, configuration, preview=preview)

    @staticmethod
    def _decimal(value) -> Decimal:
        return Decimal(str(value or 0))

    @classmethod
    def _group_preview(cls, results, licenses, configuration, sion):
        """Attach canonical existing/proposed snapshots to unique license DTOs.

        Import items, their item names and current plans use a fixed bulk query set;
        this intentionally lives in the execution service so REST, CLI and any
        future preview consumer observe exactly the same comparison.
        """
        from apps.license.models import LicenseImportItemsModel, LicenseItemPlan

        license_by_id = {row.pk: row for row in licenses}
        result_ids = [row["license_id"] for row in results]
        if len(result_ids) != len(set(result_ids)):
            raise PlannerConfigurationError(
                "Canonical preview produced duplicate top-level license results."
            )
        ids = sorted(license_by_id)
        import_items = list(
            LicenseImportItemsModel.objects.filter(license_id__in=ids)
            .select_related("hs_code").prefetch_related("items")
            .order_by("license_id", "serial_number", "pk")
        )
        matched_by_license: dict[int, list[dict[str, Any]]] = {pk: [] for pk in ids}
        for item in import_items:
            item_names = [row.name for row in item.items.all()]
            match = configuration.match({
                "record_id": item.pk,
                "item_key": ", ".join(sorted(item_names)) if item_names else (item.description or "-"),
                "hs_code": item.hs_code.hs_code if item.hs_code_id else "",
                "description": item.description or "",
                "available_quantity": item.available_quantity,
                "quantity": item.quantity,
                "unit": item.unit,
                "serial_number": item.serial_number,
            })
            if match:
                rule, output = match
                matched_by_license[item.license_id].append({
                    "import_item_id": item.pk,
                    "serial_number": item.serial_number,
                    "hsn": item.hs_code.hs_code if item.hs_code_id else "",
                    "product_description": item.description or "",
                    "unit": item.unit or "",
                    "available_quantity": item.available_quantity,
                    "rule_id": rule.pk,
                    "rule_name": rule.name,
                    "rule_priority": rule.priority,
                    "max_unit_price": rule.max_unit_price,
                    "execution_output": output,
                })

        existing_by_license: dict[int, list[dict[str, Any]]] = {pk: [] for pk in ids}
        current_rows = LicenseItemPlan.objects.filter(license_id__in=ids).values(
            "license_id", "import_item_id", "item_name_id", "planned_quantity",
            "unit_price", "planned_cif_fc", "remaining_quantity", "remaining_cif_fc",
            "note", "planning_rule_id", "planning_rule_version", "planning_rule_priority",
        ).order_by("license_id", "planning_rule_priority", "import_item_id", "pk")
        for plan in current_rows:
            existing_by_license[plan["license_id"]].append(dict(plan))

        def plan_summary(lines, *, proposed=False):
            qty_key = "requested_quantity" if proposed else "planned_quantity"
            return {
                "item_count": len(lines),
                "total_quantity": sum((cls._decimal(row.get(qty_key)) for row in lines), Decimal("0")),
                "total_value": sum((
                    cls._decimal(row.get(qty_key)) * cls._decimal(row.get("unit_price"))
                    for row in lines
                ), Decimal("0")),
                "items": lines,
            }

        from apps.license.services.canonical_planning_service import quantize_cif, quantize_qty

        def plan_signature(row, *, proposed=False):
            qty = quantize_qty(row.get("requested_quantity" if proposed else "planned_quantity", 0))
            price = quantize_cif(row.get("unit_price", 0))
            cif = quantize_cif(qty * price) if proposed else quantize_cif(row.get("planned_cif_fc", 0))
            return (
                int(row.get("import_item_id") or 0), row.get("item_name_id"), qty,
                price, cif, row.get("note") or "", row.get("planning_rule_id"),
                row.get("planning_rule_version"), row.get("planning_rule_priority"),
            )

        grouped = []
        for raw in results:
            license_id = raw["license_id"]
            proposed = list(raw.get("lines", ()))
            existing = existing_by_license.get(license_id, [])
            matched = matched_by_license.get(license_id, [])
            if configuration.rules and not matched:
                # Preview is a rule-match view, not the raw eligible-universe
                # list. This also gives the UI an unambiguous empty state.
                # Transitional planners without DB classifiers must retain
                # their legacy dry-run universe until their rules are cut over.
                continue
            proposed_by_item = {}
            for line in proposed:
                proposed_by_item.setdefault(line["import_item_id"], []).append(line)
            existing_by_item = {}
            for line in existing:
                existing_by_item.setdefault(line["import_item_id"], []).append(line)
            children = []
            for detail in matched:
                proposed_lines = proposed_by_item.get(detail["import_item_id"], [])
                existing_lines = existing_by_item.get(detail["import_item_id"], [])
                proposed_qty = sum((cls._decimal(row["requested_quantity"]) for row in proposed_lines), Decimal("0"))
                current_qty = sum((cls._decimal(row["planned_quantity"]) for row in existing_lines), Decimal("0"))
                children.append({
                    **detail,
                    "current_planned_quantity": current_qty,
                    "proposed_planned_quantity": proposed_qty,
                    "quantity_change": proposed_qty - current_qty,
                    "current_unit_price": existing_lines[0]["unit_price"] if existing_lines else None,
                    "proposed_unit_price": proposed_lines[0]["unit_price"] if proposed_lines else None,
                })
            has_shortage = (
                bool(matched) and not proposed and raw.get("status") != "SKIPPED_ALREADY_PLANNED"
            ) or bool(raw.get("has_shortage")) or raw.get("status") == "SHORTAGE" or any(
                cls._decimal(row.get("shortage_quantity", row.get("shortage_qty"))) > 0
                for row in proposed
            )
            if raw.get("status") == "SKIPPED_ALREADY_PLANNED":
                change_status = "SKIPPED"
            elif has_shortage:
                change_status = "SHORTAGE"
            elif not existing and proposed:
                change_status = "NEW"
            else:
                # Same canonical identity as build_canonical_plan, evaluated
                # from the bulk-loaded snapshot to avoid one query per license.
                current_signature = sorted(repr(plan_signature(row)) for row in existing)
                proposed_signature = sorted(repr(plan_signature(row, proposed=True)) for row in proposed)
                change_status = "NO_CHANGE" if current_signature == proposed_signature else "CHANGE"
            rule_ids = {row["rule_id"] for row in matched}
            rules = sorted({row["rule_priority"] for row in matched})
            grouped.append({
                **raw,
                "sion": sion.norm_class,
                "matched_item_count": len(matched),
                "matched_rule_count": len(rule_ids),
                "matched_rule_priorities": rules,
                "existing_plan": plan_summary(existing),
                "proposed_plan": plan_summary(proposed, proposed=True),
                "change_status": change_status,
                "has_shortage": has_shortage,
                "items": children,
            })
        rank = {"CHANGE": 0, "NEW": 1, "SHORTAGE": 2, "NO_CHANGE": 3, "SKIPPED": 4}
        return sorted(grouped, key=lambda row: (rank[row["change_status"]], row["license_id"]))

    @classmethod
    def plan_sion(
        cls, sion, license_ids=None, *, company_id=None, persist=True,
        mode=PLAN_MODE_NEW,
    ):
        """Execute saved DB classification through the proven E1/E5 mechanics."""
        from django.db import transaction
        from apps.license.services.canonical_planning_service import (
            ALREADY_PLANNED_THRESHOLD, CanonicalPlanningService,
        )

        mode = normalize_plan_mode(mode)
        results = []
        with transaction.atomic():
            # One SION-wide lock serializes API and management-command runs.
            # The API may already hold this row lock; reacquiring it in the
            # nested transaction is harmless and keeps direct callers safe.
            sion = type(sion).objects.select_for_update().get(pk=sion.pk)
            configuration = cls.resolve_configuration(sion)
            licenses, live_balances = cls._eligible_licenses(
                sion, license_ids, company_id=company_id,
            )
            planned_cif_by_license = {}
            if mode == PLAN_MODE_NEW:
                from django.db.models import Sum
                from apps.license.models import LicenseItemPlan
                planned_cif_by_license = {
                    row["license_id"]: cls._decimal(row["total"])
                    for row in LicenseItemPlan.objects.filter(
                        license_id__in=[license_obj.pk for license_obj in licenses],
                    ).values("license_id").annotate(total=Sum("planned_cif_fc"))
                }
            for license_obj in licenses:
                if (
                    mode == PLAN_MODE_NEW
                    and planned_cif_by_license.get(license_obj.pk, Decimal("0")) > 0
                    and planned_cif_by_license[license_obj.pk] >= (
                        Decimal(str(live_balances[license_obj.pk])) * ALREADY_PLANNED_THRESHOLD
                    )
                ):
                    results.append({
                        "license_id": license_obj.pk,
                        "license_number": license_obj.license_number,
                        "lines": [],
                        "status": "SKIPPED_ALREADY_PLANNED",
                        **({
                            "write_result": {
                                "license_id": license_obj.pk,
                                "status": "SKIPPED_ALREADY_PLANNED",
                            },
                        } if persist else {}),
                    })
                    continue
                lines, remaining = cls._compute_license(
                    license_obj, configuration, preview=not persist,
                )
                canonical_lines = [{
                    "import_item_id": row["import_item"],
                    "item_name_id": row.get("item_name"),
                    "requested_quantity": row["planned_quantity"],
                    "unit_price": row["unit_price"],
                    "priority": index,
                    "note": row.get("note", ""),
                } for index, row in enumerate(lines)]
                result = {
                    "license_id": license_obj.pk,
                    "license_number": license_obj.license_number,
                    "lines": canonical_lines,
                    "remaining_balance_cif": remaining,
                    "status": "PLANNED" if persist else "PREVIEWED",
                }
                if not canonical_lines:
                    # A license-level Planned badge is canonically derived from
                    # LicenseItemPlan existence. Never claim PLANNED (or erase a
                    # valid existing plan) when the active rules produced no
                    # persistable line.
                    result["status"] = "SKIPPED_NO_MATCH"
                    if persist:
                        result["write_result"] = {
                            "license_id": license_obj.pk,
                            "status": "SKIPPED_NO_MATCH",
                            "reason": "Active saved rules produced no persistable planning lines.",
                        }
                elif persist:
                    result["write_result"] = CanonicalPlanningService.build_canonical_plan(
                        license_id=license_obj.pk, norm_class=sion.norm_class,
                        items=canonical_lines,
                        force_replan=mode == PLAN_MODE_ALL,
                        company_id=company_id,
                    )
                results.append(result)
        raw_results = results
        if not persist:
            results = cls._group_preview(results, licenses, configuration, sion)
        rules = [{"id": rule.pk, "version": rule.version, "priority": rule.priority}
                 for rule in configuration.rules]
        return {
            "sion_id": sion.pk,
            "sion": sion.norm_class,
            "mode": mode,
            "rules_executed" if persist else "rules_processed": rules,
            "licenses": results,
            "results": results,
            "write_results": [row["write_result"] for row in results] if persist else [],
            "eligible_licenses": len(licenses),
            "matched_licenses": len(results),
            "planned_licenses": sum(
                bool(row.get("lines")) and row.get("status") not in {
                    "SKIPPED_ALREADY_PLANNED", "SKIPPED_NO_MATCH",
                }
                for row in raw_results
            ),
            "already_planned": sum(
                row.get("status") == "SKIPPED_ALREADY_PLANNED" for row in raw_results
            ),
            "skipped_count": sum(
                str(row.get("status", "")).startswith("SKIPPED") for row in raw_results
            ),
            "failed_count": 0,
            "excluded_licenses": [
                {
                    "license_id": row["license_id"],
                    "license_number": row.get("license_number"),
                    "reason": row["status"],
                }
                for row in raw_results if row.get("status") == "SKIPPED_NO_MATCH"
            ],
            "matched_items": sum(len(row.get("lines", ())) for row in raw_results),
            "summary": {
                "rules": len(rules),
                "rules_processed": len(rules),
                "active_rules": len(rules),
                "eligible_licenses": len(licenses),
                "matched_licenses": len(results),
                "matched_items": sum(len(row.get("lines", ())) for row in raw_results),
                "already_planned": sum(
                    row.get("status") == "SKIPPED_ALREADY_PLANNED" for row in raw_results
                ),
                "licenses_matched": len(results),
                "licenses_new": sum(row.get("change_status") == "NEW" for row in results),
                "licenses_changed": sum(row.get("change_status") == "CHANGE" for row in results),
                "licenses_unchanged": sum(row.get("change_status") == "NO_CHANGE" for row in results),
                "licenses_shortage": sum(row.get("change_status") == "SHORTAGE" for row in results),
                "licenses_skipped": sum(row.get("change_status") == "SKIPPED" for row in results),
            },
            "can_plan": True,
        }
