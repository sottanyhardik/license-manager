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
                    return explicit_output
                stable_key = rule.stable_key if hasattr(rule, "stable_key") else rule.get("stable_key")
                output = self.output_by_rule_key.get(str(stable_key or ""))
                if not output:
                    rule_id = rule.get("id") if isinstance(rule, dict) else getattr(rule, "pk", None)
                    output = self.output_by_rule_key.get(f"pk:{rule_id}")
                if not output:
                    raise PlannerConfigurationError(
                        f"Saved rule {stable_key or getattr(rule, 'pk', '<unknown>')} has no execution output mapping."
                    )
                return output
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
        from apps.license.services.canonical_planning_service import (
            CanonicalPlanningService, CompanyIsolationError,
        )

        base = LicenseDetailsModel.objects.filter(
            export_license__norm_class=sion,
            flags__is_active=True,
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

    @classmethod
    def plan_sion(
        cls, sion, license_ids=None, *, company_id=None, persist=True,
        mode=PLAN_MODE_NEW,
    ):
        """Execute saved DB classification through the proven E1/E5 mechanics."""
        from django.db import transaction
        from apps.license.services.canonical_planning_service import CanonicalPlanningService

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
            for license_obj in licenses:
                if (
                    mode == PLAN_MODE_NEW
                    and CanonicalPlanningService._is_already_planned(
                        license_obj, Decimal(str(live_balances[license_obj.pk])),
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
                if persist:
                    result["write_result"] = CanonicalPlanningService.build_canonical_plan(
                        license_id=license_obj.pk, norm_class=sion.norm_class,
                        items=canonical_lines,
                        force_replan=mode == PLAN_MODE_ALL,
                        company_id=company_id,
                    )
                results.append(result)
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
            "eligible_licenses": len(results),
            "planned_licenses": sum(
                bool(row.get("lines")) and row.get("status") != "SKIPPED_ALREADY_PLANNED"
                for row in results
            ),
            "already_planned": sum(
                row.get("status") == "SKIPPED_ALREADY_PLANNED" for row in results
            ),
            "matched_items": sum(len(row.get("lines", ())) for row in results),
            "summary": {
                "rules": len(rules),
                "active_rules": len(rules),
                "eligible_licenses": len(results),
                "matched_items": sum(len(row.get("lines", ())) for row in results),
                "already_planned": sum(
                    row.get("status") == "SKIPPED_ALREADY_PLANNED" for row in results
                ),
            },
            "can_plan": True,
        }
