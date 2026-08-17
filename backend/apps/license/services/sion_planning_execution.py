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


class LegacyPlannerAdapter(Protocol):
    def execute(self, records: list[dict[str, Any]], balance_cif: Any, configuration: "ResolvedPlannerConfiguration", *, options: dict[str, Any] | None = None): ...


@dataclass(frozen=True)
class ResolvedPlannerConfiguration:
    sion_code: str
    rules: tuple[Any, ...]
    output_by_rule_key: dict[str, str]

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
                stable_key = rule.stable_key if hasattr(rule, "stable_key") else rule.get("stable_key")
                output = self.output_by_rule_key.get(str(stable_key or ""))
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


class SionPlanningExecutionService:
    """One registry and configuration loader for transitional execution."""

    _registry: dict[str, LegacyPlannerAdapter] = {"E1": _E1Adapter(), "E5": _E5Adapter()}

    @classmethod
    def register(cls, sion_code: str, adapter: LegacyPlannerAdapter) -> None:
        cls._registry[sion_code.strip().upper()] = adapter

    @classmethod
    def resolve_configuration(cls, sion) -> ResolvedPlannerConfiguration:
        from apps.license.models import SionPlanningProfile, SionPlanningRule

        rules = tuple(SionPlanningRule.objects.filter(
            sion=sion, is_active=True,
        ).order_by("priority", "pk"))
        if not rules:
            raise PlannerConfigurationError("The selected SION has no active saved rules.")
        profile = SionPlanningProfile.objects.filter(
            sion=sion, is_active=True,
        ).prefetch_related("actions").first()
        if profile is None:
            raise PlannerConfigurationError("The selected SION has no active execution profile.")
        output_by_rule_key: dict[str, str] = {}
        for action in profile.actions.filter(is_active=True).order_by("priority", "pk"):
            output_by_rule_key.update(action.config.get("rule_outputs", {}))
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

