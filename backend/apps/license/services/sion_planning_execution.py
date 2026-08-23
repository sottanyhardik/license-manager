"""Database-driven SION planning orchestration.

All planning is driven by persisted SION rules and profiles stored in the
database. Classification and allocation logic is centralized in the generic
planning engine, eliminating norm-specific dispatch.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Any

from django.db import transaction

from apps.license.services.sion_rule_engine import evaluate_expression
from apps.license.services.output_item_resolver import OutputItemResolver


class PlannerConfigurationError(ValueError):
    """Invalid declarative planning configuration with a stable public code."""

    def __init__(self, message: str, *, code: str = "INVALID_PLANNER_CONFIGURATION"):
        super().__init__(message)
        self.code = code


SUPPORTED_GENERIC_STRATEGIES = frozenset((
    "STANDARD", "SPLIT_BY_PERCENT", "SPLIT_BY_UNIT_VALUE", "REDUCE_EFFECTIVE_RATE",
))


def _configured_rows(rule, attribute: str) -> list[Any]:
    rows = getattr(rule, attribute, ())
    if hasattr(rows, "all"):
        rows = rows.all()
    return list(rows)


def validate_declarative_rules(rules) -> tuple[Any, ...]:
    """Validate generic rule shape before any licence data is read or mutated."""
    rules = tuple(rules)
    if not rules:
        raise PlannerConfigurationError("The selected SION has no active planning rules.", code="NO_ACTIVE_RULE")
    stable_keys = [getattr(rule, "stable_key", None) for rule in rules]
    if any(key and stable_keys.count(key) > 1 for key in stable_keys):
        raise PlannerConfigurationError("Multiple active rules share a stable key.", code="MULTIPLE_ACTIVE_RULES")
    for rule in rules:
        strategy = getattr(rule, "strategy", None) or "STANDARD"
        if strategy not in SUPPORTED_GENERIC_STRATEGIES:
            raise PlannerConfigurationError(
                f"Unsupported generic strategy {strategy!r}.", code="UNSUPPORTED_GENERIC_STRATEGY"
            )
        if strategy == "SPLIT_BY_PERCENT":
            rows = _configured_rows(rule, "percentage_rows")
            if not rows:
                raise PlannerConfigurationError("Percentage strategy has no configured lines.", code="MISSING_RULE_LINES")
            if any(not getattr(row, "import_item_id", None) and not getattr(row, "import_item", None) for row in rows):
                raise PlannerConfigurationError("Percentage line has no canonical input.", code="MISSING_CANONICAL_INPUT")
            total = sum((Decimal(str(row.percentage)) for row in rows), Decimal("0"))
            if total != Decimal("100"):
                raise PlannerConfigurationError(
                    f"Percentage lines must total 100, got {total}.", code="INVALID_PERCENTAGE_TOTAL"
                )
        elif strategy == "SPLIT_BY_UNIT_VALUE" and not _configured_rows(rule, "unit_value_rows"):
            raise PlannerConfigurationError("Unit-value strategy has no configured lines.", code="MISSING_RULE_LINES")
    return rules


PLAN_MODE_NEW = "NEW"
PLAN_MODE_ALL = "ALL"
PLAN_MODES = frozenset((PLAN_MODE_NEW, PLAN_MODE_ALL))


def source_unit_value(import_item) -> Decimal | None:
    """Return the immutable source-item unit value used for band matching.

    Unit-value rules classify the imported entitlement, not a previous plan,
    its remaining balance, or a configured output price.  The authoritative
    value is therefore the original per-item CIF divided by original quantity.
    A zero CIF is an explicit zero unit value and belongs to a lower band when
    configured; only a non-positive source quantity is unclassifiable.
    """
    quantity = Decimal(str(import_item.quantity or 0))
    cif = Decimal(str(import_item.cif_fc or 0))
    if quantity <= 0:
        return None
    return cif / quantity


def select_unit_value_row(rows, unit_value: Decimal):
    """Select exactly one non-overlapping unit-value row using Decimal.

    Rows are sorted on a copy, so UI order is irrelevant.  Touching bands are
    deliberately deterministic: the lower band owns its maximum and every
    later band is open at the previous maximum.
    """
    ordered = sorted(rows, key=lambda row: (
        Decimal(str(row.min_unit_price)),
        Decimal(str(row.max_unit_price)),
        row.priority,
        row.pk,
    ))
    previous_max = None
    for row in ordered:
        minimum = Decimal(str(row.min_unit_price))
        maximum = Decimal(str(row.max_unit_price))
        lower_bound = minimum if previous_max is None else max(minimum, previous_max)
        matches = (
            minimum <= unit_value <= maximum
            if previous_max is None
            else lower_bound < unit_value <= maximum
        )
        if matches:
            return row
        previous_max = maximum
    return None


def ordered_unit_value_rows(rows):
    """Return allocation tiers in persisted priority order.

    Existing E1 rows both have priority zero; their higher configured maximum
    is the deterministic first tier (DWP before SWP). Explicit priorities
    always take precedence over this compatibility tie-break.
    """
    return sorted(rows, key=lambda row: (
        row.priority,
        -Decimal(str(row.max_unit_price)),
        row.pk,
    ))


def solve_unit_value_mix(rows, quantity: Decimal, available_cif: Decimal):
    """Return deterministic Decimal quantities for configured price rows.

    The solver preserves total eligible quantity.  For a two-price range it
    solves the exact linear mix; for more rows it fills deterministically from
    the lowest price upward, then moves quantity to higher prices until the
    available CIF is consumed as closely as possible.
    """
    quantity = Decimal(str(quantity))
    available_cif = Decimal(str(available_cif))
    # The configured rows are *prices*, not source-CIF bands.  Sort by price
    # first and persisted row order second so a database's incidental order
    # can never affect a rebuild.  A two-extreme mix spans every value between
    # the lowest and highest configured price, including when there are >2
    # rows, and is therefore the deterministic bounded N-row solution.
    ordered = sorted(rows, key=lambda row: (
        Decimal(str(row.preferred_unit_price if row.preferred_unit_price > 0 else row.max_unit_price)),
        row.priority, row.pk,
    ))
    if not ordered or quantity <= 0:
        return []
    prices = [Decimal(str(row.preferred_unit_price if row.preferred_unit_price > 0 else row.max_unit_price)) for row in ordered]
    result = [Decimal("0")] * len(ordered)
    result[0] = quantity
    minimum = quantity * prices[0]
    maximum = quantity * prices[-1]
    # Underfunding intentionally retains the valid full quantity at its
    # lowest configured price.  The caller caps financial consumption and
    # records the diagnostic; negative quantities are never manufactured.
    if available_cif <= minimum:
        return list(zip(ordered, result))
    if available_cif >= maximum:
        result[0] = Decimal("0")
        result[-1] = quantity
        return list(zip(ordered, result))

    high_index = len(ordered) - 1
    spread = prices[high_index] - prices[0]
    if spread > 0:
        high_quantity = (available_cif - minimum) / spread
        result[0] = quantity - high_quantity
        result[high_index] = high_quantity
    return list(zip(ordered, result))


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


@dataclass(frozen=True)
class ResolvedPlannerConfiguration:
    sion_code: str
    rules: tuple[Any, ...]
    output_by_rule_key: dict[str, str]
    actions: tuple[Any, ...] = ()

    def split_action_for_category(self, category: str) -> dict[str, Any] | None:
        """Return the persisted split action for a matched output category."""
        for action in self.actions:
            config = action.config if hasattr(action, "config") else action.get("config", {})
            action_type = action.action_type if hasattr(action, "action_type") else action.get("action_type")
            if (
                action_type == "SPLIT"
                and config.get("algorithm") == "SPLIT_BY_UNIT_VALUE"
                and config.get("category") == category
            ):
                return config
        return None

    def rule_for_output(self, output: str):
        for rule in self.rules:
            if getattr(rule, "execution_output", "") == output:
                return rule
        return None

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


@dataclass(frozen=True)
class PlanningContext:
    """Immutable input snapshot for one canonical license planning run.

    It deliberately keeps the opening planning ceiling separate from the live
    financial-balance audit figure.  Every strategy receives the carried
    ``remaining_planning_cif`` from the single execution loop; no strategy is
    allowed to create an alternative opening balance.
    """
    license_id: int
    sion_id: int
    license_total_cif: Decimal
    planning_cif_ceiling: Decimal
    live_financial_balance_cif: Decimal
    source_items: tuple[Any, ...]
    actual_usage: dict[str, Any]
    ordered_rules: tuple[Any, ...]


class SionPlanningExecutionService:
    """Generic database-driven planning orchestration for all SIONs."""

    @classmethod
    def resolve_configuration(cls, sion) -> ResolvedPlannerConfiguration:
        from apps.license.models import SionPlanningProfile, SionPlanningRule

        active_rules = list(SionPlanningRule.objects.filter(
            sion=sion, is_active=True,
        ).order_by("priority", "-version", "-pk"))
        # A rule edit is version-appended.  Legacy/manual data can contain
        # more than one active revision, but a plan must never mix their
        # percentage rows. Select the newest active revision per stable key.
        selected = {}
        unversioned = []
        for rule in active_rules:
            if rule.stable_key:
                selected.setdefault(rule.stable_key, rule)
            else:
                unversioned.append(rule)
        rules = tuple(sorted([*selected.values(), *unversioned], key=lambda rule: (rule.priority, rule.pk)))
        if not rules:
            raise PlannerConfigurationError(
                f"The selected SION {sion.norm_class} has no active saved rules. "
                "Database rules are required for all planning operations."
            )
        profile = SionPlanningProfile.objects.filter(sion=sion).order_by(
            "-is_active", "-version", "-pk",
        ).prefetch_related("actions").first()
        output_by_rule_key: dict[str, str] = {}
        actions = tuple(profile.actions.filter(is_active=True).order_by("priority", "pk")) if profile is not None else ()
        if profile is not None:
            for action in actions:
                output_by_rule_key.update(action.config.get("rule_outputs", {}))
        # UI-created rules already carry their execution bucket.  Use it
        # directly so DB rules remain executable even when an older database
        # predates the optional profile migration.  Rule name is the UI's
        # bucket definition for newly-created rules that have no hidden
        # execution_output field.
        import re
        for rule in rules:
            output = (rule.execution_output or re.sub(r"^\s*\d+\s*[-–—.]?\s*", "", rule.name)).strip()
            if output:
                if rule.stable_key:
                    output_by_rule_key.setdefault(str(rule.stable_key), output)
                output_by_rule_key.setdefault(f"pk:{rule.pk}", output)
        allowed_outputs = set(output_by_rule_key.values())
        for rule in rules:
            if rule.execution_output:
                if profile is not None and rule.execution_output not in allowed_outputs:
                    raise PlannerConfigurationError(
                        f"Saved rule {rule.pk} has unsupported execution output {rule.execution_output!r}."
                    )
                continue
            if (rule.stable_key and rule.stable_key in output_by_rule_key) or f"pk:{rule.pk}" in output_by_rule_key:
                continue
            raise PlannerConfigurationError(
                f"Saved rule {rule.pk} has no execution output. Save an execution bucket before planning."
            )
        return ResolvedPlannerConfiguration(
            sion.norm_class.strip().upper(), rules, output_by_rule_key, actions,
        )

    @classmethod
    def _eligible_licenses(cls, sion, license_ids=None, *, company_id=None, force_plan=False):
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
        # The live financial balance is the absolute planning budget.  History
        # reconciliation provides a second safety cap, but must never replace
        # the currently available CIF: a zero live balance cannot generate a
        # positive-CIF plan.
        return licenses, live_balances

    @classmethod
    def _compute_license_new_architecture(
        cls, license_obj, sion, strategy_rules, *, preview, force_plan=False,
        operational_balance_cif=None,
    ):
        """Build a priority-waterfall strategy plan from saved configuration."""
        from apps.license.models import LicenseImportItemsModel, LicenseExportItemModel
        from apps.license.services.canonical_planning_service import (
            SplitPercentIncompleteError,
            SplitPercentQuantityMismatchError,
        )

        strategy_rules = validate_declarative_rules(strategy_rules)
        import_items = list(
            LicenseImportItemsModel.objects.filter(license=license_obj)
            .select_related("hs_code").prefetch_related("items").order_by("pk")
        )
        item_name_ids = {item.pk: {name.pk for name in item.items.all()} for item in import_items}
        total_cif = sum(
            (Decimal(str(value or 0)) for value in LicenseExportItemModel.objects.filter(
                license=license_obj, norm_class=sion,
            ).values_list("cif_fc", flat=True)),
            Decimal("0"),
        )
        # Source ``available_quantity`` is a legacy operational cache with
        # whole-unit precision in some imports.  Planning must retain the
        # canonical three-decimal entitlement and deduct actual rows only
        # after aggregating them, never truncate every matched item first.
        from apps.license.services.planning_usage_reconciliation import aggregate_license_usage
        actual_usage = aggregate_license_usage(license_obj.pk)
        original_import_qty = sum((Decimal(str(item.quantity or 0)) for item in import_items), Decimal("0"))
        actual_import_qty = sum((
            values["boe_used_quantity"] + values["unlinked_allotment_quantity"]
            for values in actual_usage["mapped"].values()
        ), Decimal("0")) + sum((
            values["boe_used_quantity"] + values["unlinked_allotment_quantity"]
            for values in actual_usage["unmapped_by_source"].values()
        ), Decimal("0"))
        remaining_waterfall_qty = max(original_import_qty - actual_import_qty, Decimal("0")).quantize(
            Decimal("0.001"), rounding=ROUND_DOWN,
        )
        # ``operational_balance_cif`` is the gross export entitlement less
        # authoritative BOE/allotment CIF.  It is calculated once by
        # ``plan_sion`` and is the opening CIF for *new* planning.  Starting
        # again from ``total_cif`` here both double-counts the historical
        # capacity and makes a balancing effective price impossible (the
        # residual can exceed the member's configured maximum rate).
        planning_cif_ceiling = (
            Decimal(str(operational_balance_cif))
            if operational_balance_cif is not None
            else total_cif
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        remaining_waterfall_cif = planning_cif_ceiling
        # Snapshot all legitimate inputs once.  Actual usage is loaded before
        # any strategy runs and is retained in provenance for reconciliation;
        # it is never inferred from an old generated plan.
        context = PlanningContext(
            license_id=license_obj.pk,
            sion_id=sion.pk,
            license_total_cif=planning_cif_ceiling,
            planning_cif_ceiling=planning_cif_ceiling,
            live_financial_balance_cif=Decimal(str(operational_balance_cif or 0)),
            source_items=tuple(import_items),
            actual_usage=actual_usage,
            ordered_rules=tuple(sorted(strategy_rules, key=lambda value: (value.priority, value.pk))),
        )

        def matching_group(item_name_id):
            matched = [item for item in import_items if item_name_id in item_name_ids[item.pk]]
            # A single physical entitlement row is unambiguous even when an
            # older import did not populate its item-name M2M classification.
            return matched or (import_items if len(import_items) == 1 else [])

        claimed_source_item_ids: set[int] = set()

        def source_group(rule, fallback_item_name_id=None):
            expression = rule.expression if isinstance(rule.expression, dict) else {}
            children = expression.get("conditions", expression.get("args", []))
            if children or expression.get("field"):
                matched = []
                for item in import_items:
                    record = {
                        "hs_code": item.hs_code.hs_code if item.hs_code_id else "",
                        "description": item.description or "",
                        "item_key": ", ".join(
                            sorted(name.name for name in item.items.all())
                        ),
                        "total_qty": item.quantity,
                        "available_qty": item.available_quantity,
                        "unit": item.unit or "",
                        "serial_number": item.serial_number,
                    }
                    if evaluate_expression(expression, record):
                        matched.append(item)
                return [item for item in matched if item.pk not in claimed_source_item_ids]
            # Compatibility for pre-redesign strategy records created with an
            # empty expression. Newly edited rules use explicit match logic.
            return [
                item for item in (matching_group(fallback_item_name_id) if fallback_item_name_id else [])
                if item.pk not in claimed_source_item_ids
            ]

        def available_group_quantity(group):
            """Return the operationally available source quantity for a rule.

            The priority waterfall plans future capacity after BOE/allotment
            commitments, so it must never re-offer an import item's original
            quantity once a portion has been consumed.  Older imports without
            an availability value retain their original quantity as a
            compatibility fallback.
            """
            source_ids = {item.pk for item in group}
            original = sum((Decimal(str(item.quantity or 0)) for item in group), Decimal("0"))
            actual = sum((
                values["boe_used_quantity"] + values["unlinked_allotment_quantity"]
                for (source_id, _target_id), values in context.actual_usage["mapped"].items()
                if source_id in source_ids
            ), Decimal("0")) + sum((
                values["boe_used_quantity"] + values["unlinked_allotment_quantity"]
                for source_id, values in context.actual_usage["unmapped_by_source"].items()
                if source_id in source_ids
            ), Decimal("0"))
            return max(original - actual, Decimal("0")).quantize(Decimal("0.001"), rounding=ROUND_DOWN)

        def add_line(rule, item_name, group, quantity, price, provenance, *, emit_zero=False):
            nonlocal remaining_waterfall_qty, remaining_waterfall_cif
            if not group or (quantity <= 0 and not emit_zero):
                return Decimal("0")
            price = Decimal(str(price or 0))
            # Quantity ownership and CIF funding are intentionally separate.
            # A valid source quantity belongs to its highest-priority rule
            # even where the licence cannot fund its whole theoretical CIF.
            allocated_quantity = min(max(Decimal(str(quantity)), Decimal("0")), remaining_waterfall_qty)
            if price > 0 and remaining_waterfall_cif.is_finite():
                affordable_quantity = (remaining_waterfall_cif / price).quantize(
                    Decimal("0.001"), rounding=ROUND_DOWN,
                )
                allocated_quantity = min(allocated_quantity, affordable_quantity)
            allocated_quantity = allocated_quantity.quantize(Decimal("0.001"), rounding=ROUND_DOWN)
            if allocated_quantity <= 0 and not emit_zero:
                return Decimal("0")
            # A percentage target is an immutable *cap*, while the persisted
            # line is the balance-aware new plan.  Keep both values so a
            # report can never accidentally present the target as a plan.
            theoretical_quantity = Decimal(str(
                provenance.get("theoretical_target_qty", allocated_quantity)
            )).quantize(Decimal("0.001"), rounding=ROUND_DOWN)
            theoretical_cif = (theoretical_quantity * price).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP,
            )
            new_planned_cif = (allocated_quantity * price).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP,
            )
            # Persisted plan CIF is the operational/reconciled financial
            # commitment. The configured price and uncapped theoretical CIF
            # remain explicit provenance rather than being faked by changing
            # the rule price or shrinking the valid quantity.
            allocated_cif = new_planned_cif
            provenance = {
                **provenance,
                "source_item_ids": [item.pk for item in group],
                "theoretical_quantity": str(theoretical_quantity),
                "theoretical_cif": str(theoretical_cif),
                "operational_planned_quantity": str(allocated_quantity),
                "operational_planned_cif": str(allocated_cif),
                "cif_status": "CAPPED" if allocated_cif < new_planned_cif else "FULLY_FUNDED",
            }
            all_lines.append({
                "import_item": group[0].pk,
                "item_name": item_name.pk,
                "planned_quantity": allocated_quantity,
                "unit_price": price,
                "planned_cif": allocated_cif,
                "planning_rule_id": rule.pk,
                "planning_rule_version": rule.version,
                "planning_rule_priority": rule.priority,
                "allocation_provenance": provenance,
            })
            remaining_waterfall_qty = max(remaining_waterfall_qty - allocated_quantity, Decimal("0"))
            remaining_waterfall_cif = max(remaining_waterfall_cif - allocated_cif, Decimal("0"))
            return allocated_quantity

        all_lines = []
        diagnostics = []
        percent_rows_flat = [
            row
            for percent_rule in strategy_rules if percent_rule.strategy == "SPLIT_BY_PERCENT"
            for row in percent_rule.percentage_rows.all().order_by("priority", "pk")
        ]
        global_percent_total = sum((row.percentage for row in percent_rows_flat), Decimal("0"))
        global_percent_index = 0
        global_assigned_nominal = Decimal("0")
        waterfall_diagnostics = []
        for rule in context.ordered_rules:
            stage_qty_before = remaining_waterfall_qty
            stage_cif_before = remaining_waterfall_cif
            strategy = rule.strategy or "STANDARD"
            # Keep evaluating rules after capacity is exhausted so Auto Plan
            # can distinguish an unmatched source from a matched source that
            # correctly received nothing under the global waterfall cap.
            # This is diagnostic-only; it never claims or mutates a source.
            if remaining_waterfall_qty <= 0 or remaining_waterfall_cif <= 0:
                if strategy == "SPLIT_BY_UNIT_VALUE":
                    configured_rows = ordered_unit_value_rows(rule.unit_value_rows.all())
                    group = source_group(
                        rule, configured_rows[0].import_item_id if configured_rows else None,
                    )
                    requested_quantity = available_group_quantity(group)
                    requested_cif = sum((
                        requested_quantity * (
                            Decimal(str(row.preferred_unit_price))
                            if Decimal(str(row.preferred_unit_price)) > 0
                            else Decimal(str(row.max_unit_price))
                        )
                        for row in configured_rows
                    ), Decimal("0"))
                elif strategy == "SPLIT_BY_PERCENT":
                    configured_rows = list(rule.percentage_rows.all().order_by("priority", "pk"))
                    group = source_group(rule, configured_rows[0].import_item_id if configured_rows else None)
                    requested_quantity = available_group_quantity(group)
                    requested_cif = sum((
                        requested_quantity * row.percentage / Decimal("100") * row.unit_price
                        for row in configured_rows
                    ), Decimal("0"))
                else:
                    group = source_group(rule, rule.import_item_id) if rule.import_item_id else []
                    requested_quantity = available_group_quantity(group)
                    requested_cif = requested_quantity * Decimal(str(rule.max_unit_price or 0))
                waterfall_diagnostics.append({
                    "priority": rule.priority,
                    "rule_id": rule.pk,
                    "rule_version": rule.version,
                    "rule_name": rule.name,
                    "strategy": strategy,
                    "matched_source_item_ids": [item.pk for item in group],
                    "requested_qty": str(requested_quantity),
                    "requested_cif": str(requested_cif),
                    "allocated_qty": "0",
                    "allocated_cif": "0",
                    "remaining_qty_before": str(stage_qty_before),
                    "remaining_cif_before": str(stage_cif_before),
                    "remaining_qty": str(remaining_waterfall_qty),
                    "remaining_cif": str(remaining_waterfall_cif),
                    "skip_reason": (
                        "WATERFALL_QTY_EXHAUSTED"
                        if remaining_waterfall_qty <= 0
                        else "WATERFALL_CIF_EXHAUSTED"
                    ),
                })
                continue
            if strategy == "STANDARD":
                # The source predicate is independent from the *target* item.
                # A deliberately unlinked STANDARD rule is valid configuration:
                # execution resolves its canonical ``import_item`` lazily after
                # a real source match proves that it is needed.  Previously an
                # absent target made the source group empty, so the resolver was
                # unreachable and a legitimate first execution could never
                # create its target item.
                group = source_group(rule, rule.import_item_id)
                # A source entitlement has exactly one highest-priority SION
                # rule owner.  This matters for legacy descriptions/HSNs that
                # happen to satisfy more than one configured rule (for
                # example a milk-solid source carrying an old fruit-juice
                # HSN).  Later rules must not create a second target row.
                # Standard rules use the persisted operational balance for
                # each source item. Percentage rules below calculate their
                # own original-target minus actual reconciliation.
                quantity = sum((
                    Decimal(str(item.available_quantity if item.available_quantity is not None else (item.quantity or 0)))
                    for item in group
                ), Decimal("0")).quantize(Decimal("0.001"), rounding=ROUND_DOWN)
                # Preview is strictly read-only.  It must not create a master
                # ItemNameModel merely to render a hypothetical row.  Execution
                # creates/links the target only for a matched, positive-quantity
                # source whose live CIF ceiling can actually fund planning.
                item_name = rule.import_item
                if group and quantity > 0 and item_name is None:
                    if preview:
                        waterfall_diagnostics.append({
                            "priority": rule.priority,
                            "rule_id": rule.pk,
                            "rule_version": rule.version,
                            "rule_name": rule.name,
                            "strategy": strategy,
                            "matched_source_item_ids": [item.pk for item in group],
                            "requested_qty": str(quantity),
                            "requested_cif": str(quantity * Decimal(str(rule.max_unit_price or 0))),
                            "allocated_qty": "0",
                            "allocated_cif": "0",
                            "remaining_qty_before": str(stage_qty_before),
                            "remaining_cif_before": str(stage_cif_before),
                            "remaining_qty": str(remaining_waterfall_qty),
                            "remaining_cif": str(remaining_waterfall_cif),
                            "matched": True,
                            "skip_reason": "OUTPUT_ITEM_UNRESOLVED_PREVIEW",
                        })
                        continue
                    item_name = OutputItemResolver.resolve_or_create(rule)

                allocated = add_line(rule, item_name, group, quantity, rule.max_unit_price, {
                    "strategy": "STANDARD", "quantity_source": "available_import_group_quantity",
                })
                if allocated > 0:
                    claimed_source_item_ids.update(item.pk for item in group)
                waterfall_diagnostics.append({
                    "priority": rule.priority, "rule_id": rule.pk,
                    "rule_version": rule.version, "rule_name": rule.name, "strategy": strategy,
                    "matched_source_item_ids": [item.pk for item in group],
                    "requested_qty": str(quantity),
                    "requested_cif": str(quantity * Decimal(str(rule.max_unit_price or 0))),
                    "allocated_qty": str(stage_qty_before - remaining_waterfall_qty),
                    "allocated_cif": str(stage_cif_before - remaining_waterfall_cif)
                    if remaining_waterfall_cif.is_finite() else "0",
                    "remaining_qty_before": str(stage_qty_before),
                    "remaining_cif_before": str(stage_cif_before),
                    "remaining_qty": str(remaining_waterfall_qty),
                    "remaining_cif": str(remaining_waterfall_cif), "matched": bool(group),
                    "skip_reason": None if group else "NO_MATCH",
                })
                continue

            if strategy == "SPLIT_BY_UNIT_VALUE":
                # Configured Unit Value rows are allocation instruments.  The
                # current waterfall CIF, not source average CIF, determines
                # the mathematical mix.
                configured_rows = ordered_unit_value_rows(rule.unit_value_rows.all())
                matched_source = source_group(
                    rule, configured_rows[0].import_item_id if configured_rows else None,
                )
                for source_item in matched_source:
                    if remaining_waterfall_qty <= 0:
                        break
                    source_remaining_qty = available_group_quantity([source_item])
                    mix = solve_unit_value_mix(configured_rows, source_remaining_qty, remaining_waterfall_cif)
                    for row, split_quantity in mix:
                        if split_quantity <= 0:
                            continue
                        planning_price = Decimal(str(row.preferred_unit_price if row.preferred_unit_price > 0 else row.max_unit_price))
                        add_line(rule, row.import_item, [source_item], split_quantity, planning_price, {
                            "strategy": "SPLIT_BY_UNIT_VALUE",
                            "quantity_source": "available_import_item_quantity",
                            "min_unit_price": str(row.min_unit_price),
                            "max_unit_price": str(row.max_unit_price),
                            "unit_value_row_priority": row.priority,
                            "price_source": (
                                "preferred_unit_price"
                                if Decimal(str(row.preferred_unit_price)) > 0
                                else "row_max_unit_price"
                            ),
                            "opening_operational_cif": str(stage_cif_before),
                            "unit_value_solver": "DECIMAL_BOUNDED_MIX",
                        })
                if any(line["planning_rule_id"] == rule.pk for line in all_lines):
                    claimed_source_item_ids.update(item.pk for item in matched_source)
                waterfall_diagnostics.append({
                    "priority": rule.priority, "rule_id": rule.pk,
                    "rule_version": rule.version, "rule_name": rule.name, "strategy": strategy,
                    "matched_source_item_ids": [item.pk for item in matched_source],
                    "requested_qty": str(sum((available_group_quantity([item]) for item in matched_source), Decimal("0"))),
                    "requested_cif": None,
                    "allocated_qty": str(stage_qty_before - remaining_waterfall_qty),
                    "allocated_cif": str(stage_cif_before - remaining_waterfall_cif)
                    if remaining_waterfall_cif.is_finite() else "0",
                    "remaining_qty_before": str(stage_qty_before),
                    "remaining_cif_before": str(stage_cif_before),
                    "remaining_qty": str(remaining_waterfall_qty),
                    "remaining_cif": str(remaining_waterfall_cif), "matched": bool(matched_source),
                    "skip_reason": None if matched_source else "NO_MATCH",
                })
                continue

            if strategy == "SPLIT_BY_PERCENT":
                configured = list(rule.percentage_rows.all().order_by("priority", "pk"))
                # All rows in one percentage rule describe alternate labels for the
                # same entitlement group. Count each physical import row once.
                matched_source = source_group(rule, configured[0].import_item_id if configured else None)
                matched_by_row = {row.pk: matched_source for row in configured}
                # Percentage theory is based on original source quantity.  A
                # parent BOE/allotment target reserves historical use first;
                # only the real source balance can become future plan qty.
                total_planning_quantity = sum((Decimal(str(item.quantity or 0)) for item in matched_source), Decimal("0"))
                source_ids = [item.pk for item in matched_source]
                actual_by_target = {}
                actual_cif_by_target = {}
                total_actual_qty = Decimal("0")
                for source_id in source_ids:
                    for (usage_source_id, target_id), values in context.actual_usage["mapped"].items():
                        if usage_source_id == source_id:
                            qty = values["boe_used_quantity"] + values["unlinked_allotment_quantity"]
                            cif = values["boe_used_cif"] + values["unlinked_allotment_cif"]
                            actual_by_target[target_id] = actual_by_target.get(target_id, Decimal("0")) + qty
                            actual_cif_by_target[target_id] = actual_cif_by_target.get(target_id, Decimal("0")) + cif
                            total_actual_qty += qty
                    unknown = context.actual_usage["unmapped_by_source"].get(source_id, {})
                    total_actual_qty += unknown.get("boe_used_quantity", Decimal("0")) + unknown.get("unlinked_allotment_quantity", Decimal("0"))
                # ``available_quantity`` is the authoritative current/net
                # operational balance.  It is a hard cap and must not be
                # replaced by the theoretical percentage target.  Historical
                # usage is only subtracted from the original entitlement when
                # a legacy source lacks that net field.
                authoritative_balance_qty = available_group_quantity(matched_source)
                future_source_balance = min(
                    max(total_planning_quantity - total_actual_qty, Decimal("0")),
                    authoritative_balance_qty,
                )
                generated = 0
                assigned_nominal = Decimal("0")
                generated_quantity_total = Decimal("0")
                rule_percent_total = sum((row.percentage for row in configured), Decimal("0"))
                use_global_split = rule_percent_total != Decimal("100") and global_percent_total == Decimal("100")
                # Percentage siblings are one atomic priority unit.  Solve the
                # common final group scale before writing either child; a
                # sequential Olive-then-PKO waterfall destroys 70/30 (or
                # 50/50) proportions whenever CIF is constrained.
                from apps.license.services.percentage_group_solver import solve_balancing_price_group
                solved = solve_balancing_price_group(
                    base_qty=total_planning_quantity,
                    group_available_cif=remaining_waterfall_cif,
                    group_available_qty=future_source_balance,
                    # Target CIF is the gross entitlement left after prior
                    # rule targets. It is distinct from the actual-balance
                    # waterfall budget passed above.
                    group_target_cif=total_cif - (planning_cif_ceiling - stage_cif_before),
                    members=[{
                        "row": row,
                        "percentage": row.percentage,
                        "configured_max_unit_price": row.unit_price,
                        "actual_used_qty": actual_by_target.get(row.import_item_id, Decimal("0")),
                        "actual_used_cif": actual_cif_by_target.get(row.import_item_id, Decimal("0")),
                        "member_sequence": row.priority,
                    } for row in configured],
                )
                solved_by_row = {entry["row"].pk: entry for entry in solved["members"]}
                for row_index, row in enumerate(configured):
                    # Percent rows are one already-owned source allocation.
                    # Emit every configured percentage quantity even when an
                    # earlier sibling consumes the last operational CIF.
                    if remaining_waterfall_qty <= 0:
                        break
                    raw_nominal = total_planning_quantity * row.percentage / Decimal("100")
                    # Plan quantities are Decimal(_, 3), not whole kilograms.
                    # Allocate any sub-milligram rounding remainder to the final
                    # row so a 100% rule conserves the source entitlement.
                    if use_global_split:
                        nominal = (
                            total_planning_quantity - global_assigned_nominal
                            if global_percent_index == len(percent_rows_flat) - 1
                            else raw_nominal.quantize(Decimal("0.001"), rounding=ROUND_DOWN)
                        )
                        global_assigned_nominal += nominal
                        global_percent_index += 1
                    else:
                        nominal = (
                            total_planning_quantity - assigned_nominal
                            if row_index == len(configured) - 1
                            else raw_nominal.quantize(Decimal("0.001"), rounding=ROUND_DOWN)
                        )
                    assigned_nominal += nominal
                    # ``max_quantity`` is retained for legacy data/audit only.
                    # Percentage is authoritative for SPLIT_BY_PERCENT; no cap
                    # is enforced without a future explicit opt-in flag.
                    # Historical use attributed by the authoritative parent
                    # document mapping consumes this child's theoretical
                    # capacity. Persisted row order decides the deterministic
                    # allocation of any remaining source balance.
                    solved_member = solved_by_row[row.pk]
                    remaining_capacity = max(nominal - actual_by_target.get(row.import_item_id, Decimal("0")), Decimal("0"))
                    final_quantity = solved_member["remaining_qty"]
                    generated_quantity_total += final_quantity
                    generated += bool(add_line(rule, row.import_item, matched_by_row[row.pk], final_quantity,
                                              solved_member["effective_unit_price"], {
                        "strategy": "SPLIT_BY_PERCENT",
                        "percentage": str(row.percentage),
                        "total_planning_quantity": str(total_planning_quantity),
                        "raw_nominal_quantity": str(raw_nominal),
                        "nominal_quantity": str(nominal),
                        "theoretical_target_qty": str(nominal),
                        "percentage_base_qty": str(total_planning_quantity),
                        "actual_target_quantity": str(actual_by_target.get(row.import_item_id, Decimal("0"))),
                        "actual_target_cif": str(actual_cif_by_target.get(row.import_item_id, Decimal("0"))),
                        "excess_other_item_quantity": str(solved_member.get("excess_other_item_qty", Decimal("0"))),
                        "excess_other_item_cif": str(solved_member.get("excess_other_item_cif", Decimal("0"))),
                        "audit_remaining_quantity": str(solved_member.get("audit_remaining_qty", final_quantity)),
                        "audit_remaining_cif": str(solved_member.get("audit_remaining_cif", solved_member["remaining_cif"])),
                        "future_source_balance": str(future_source_balance),
                        "authoritative_balance_qty": str(authoritative_balance_qty),
                        "remaining_percentage_capacity": str(remaining_capacity),
                        "final_accounted_quantity": str(solved_member["actual_used_qty"] + solved_member["remaining_qty"]),
                        "effective_unit_price": str(solved_member["effective_unit_price"]),
                        "configured_max_unit_price": str(row.unit_price),
                        # Candidate is the configured-max-price projection;
                        # the effective fields are the plan actually funded by
                        # this rule's waterfall share.  Keeping both removes
                        # any ambiguity for the API/UI and audit export.
                        "candidate_planned_quantity": str(solved_member["remaining_qty"]),
                        "candidate_planned_cif": str((
                            solved_member["remaining_qty"] * Decimal(str(row.unit_price))
                        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                        "effective_planned_quantity": str(solved_member["remaining_qty"]),
                        "effective_planned_cif": str(solved_member["remaining_cif"]),
                        "cif_cap_adjustment": str((
                            (solved_member["remaining_qty"] * Decimal(str(row.unit_price))
                            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                            - solved_member["remaining_cif"]
                        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                        "percentage_target_cif": str(solved_member["percentage_target_cif"]),
                        "remaining_cif": str(solved_member["remaining_cif"]),
                        "legacy_max_quantity_ignored": (
                            str(row.max_quantity) if row.max_quantity is not None else None
                        ),
                        "quantity_source": "available_import_group_quantity",
                    }, emit_zero=True))
                    diagnostics.append({
                        "rule_id": rule.pk, "row_id": row.pk, "item_name": row.import_item.name,
                        "raw_nominal_quantity": str(raw_nominal),
                        "nominal_quantity": str(nominal), "max_quantity": str(row.max_quantity),
                        "generated": bool(matched_by_row[row.pk] and final_quantity > 0),
                    })
                waterfall_diagnostics.append({
                    "priority": rule.priority, "rule_id": rule.pk,
                    "rule_version": rule.version, "rule_name": rule.name, "strategy": strategy,
                    "matched_source_item_ids": [item.pk for item in matched_source],
                    "requested_qty": str(total_planning_quantity),
                    "requested_cif": None,
                    "allocated_qty": str(stage_qty_before - remaining_waterfall_qty),
                    "allocated_cif": str(stage_cif_before - remaining_waterfall_cif)
                    if remaining_waterfall_cif.is_finite() else "0",
                    "remaining_qty_before": str(stage_qty_before),
                    "remaining_cif_before": str(stage_cif_before),
                    "remaining_qty": str(remaining_waterfall_qty),
                    "remaining_cif": str(remaining_waterfall_cif), "matched": bool(matched_source),
                    "skip_reason": None if matched_source else "NO_MATCH",
                })
                # A target exhausted by mapped history legitimately has no
                # future row.  This is not a configuration failure.
                # A 100% configuration defines the target distribution, not
                # an entitlement to exceed the authoritative current quantity
                # or CIF caps.  Record the shortage for audit; do not reject a
                # valid balance-capped rebuild (e.g. the live 1.130kg gap).
                if configured and total_planning_quantity > 0 and rule_percent_total == Decimal("100") and abs(generated_quantity_total - future_source_balance) > Decimal("0.001"):
                    diagnostics.append({
                        "rule_id": rule.pk, "shortage_reason": "BALANCE_OR_CIF_CAP",
                        "source_quantity": str(future_source_balance),
                        "generated_quantity": str(generated_quantity_total),
                    })
                if generated:
                    claimed_source_item_ids.update(item.pk for item in matched_source)

        planned_cif = sum((line["planned_cif"] for line in all_lines), Decimal("0"))
        # Persist the one run-level capacity snapshot with every generated
        # strategy row. Downstream reconciliation must not substitute a
        # different live-balance ceiling and silently re-cap these rows.
        for line in all_lines:
            line["allocation_provenance"].update({
                "planning_cif_ceiling": str(planning_cif_ceiling),
                "remaining_planning_cif_after_run": str(remaining_waterfall_cif),
                # Compatibility fields for records/projections deployed
                # before the canonical names. They mean the same planning
                # snapshot, never the live financial balance.
                "opening_operational_cif": str(planning_cif_ceiling),
                "remaining_operational_cif_after_run": str(remaining_waterfall_cif),
            })
        return all_lines, total_cif - planned_cif, {
            "architecture": "strategy", "total_cif": planning_cif_ceiling,
            "planning_cif_ceiling": planning_cif_ceiling,
            "total_planned_cif": planned_cif, "percentage_rows": diagnostics,
            "waterfall": waterfall_diagnostics,
            "remaining_waterfall_qty": remaining_waterfall_qty,
            "remaining_waterfall_cif": remaining_waterfall_cif,
            "context": context,
        }

    @classmethod
    def _compute_license(cls, license_obj, sion, *, preview, force_plan=False, operational_balance_cif=None):
        """Compute planned lines using database-driven rules and generic planner.

        Args:
            license_obj: LicenseDetailsModel instance
            sion: SionNormClassModel instance
            preview: If True, don't persist ItemNameModel creation
            force_plan: If True, bypass availability constraints
        """
        from apps.license.models import SionPlanningRule

        # NEW ARCHITECTURE: Check for rules with strategy set (new dispatch path)
        active_rules = list(SionPlanningRule.objects.filter(sion=sion, is_active=True).order_by("priority"))
        if active_rules:
            # A blank persisted strategy is the backwards-compatible spelling
            # of STANDARD, never permission to dispatch to a second planner.
            # This keeps every active SION in the same priority waterfall.
            return cls._compute_license_new_architecture(
                license_obj, sion, active_rules, preview=preview, force_plan=force_plan,
                operational_balance_cif=operational_balance_cif,
            )

        # No active rules is a configuration error, not a reason to revive a
        # historical planner.  Callers surface this rather than guessing.
        raise PlannerConfigurationError(
            f"The selected SION {getattr(sion, 'norm_class', sion)!r} has no active planning rules.",
            code="NO_ACTIVE_RULE",
        )

    @classmethod
    def _compute_license_generic(
        cls,
        license_obj,
        sion,
        records: list[dict[str, Any]],
        balance_cif: Decimal,
        *,
        preview: bool,
        force_plan: bool = False,
    ) -> "DatabaseDrivenPlanResult":
        """Generic rules-based planning without requiring a legacy profile.

        Executes active database rules against import items directly,
        auto-creating output ItemNameModels as needed during execution.

        Args:
            license_obj: LicenseDetailsModel instance
            sion: SionNormClassModel instance
            records: List of import item records with hs_code, description, qty, etc.
            balance_cif: Available CIF for allocation
            preview: If True, don't persist ItemNameModel creation (preview only)
            force_plan: Selection mode for an explicit re-plan. It never
                bypasses availability or balance-CIF constraints.

        Returns:
            DatabaseDrivenPlanResult with planned rows and remaining CIF
        """
        from apps.license.services.database_driven_sion_planner import (
            DatabaseDrivenPlanResult, PlanningRow, InvalidPlannerConfiguration
        )
        from apps.license.models import SionPlanningRule

        # Get the configuration (rules)
        configuration = cls.resolve_configuration(sion)

        # Match every record before allocating.  The execution order is the
        # persisted rule priority, with source order only as a stable tie
        # breaker.  Allocating directly while iterating source rows makes an
        # otherwise identical plan depend on import-row ordering and violates
        # the configured waterfall when CIF is scarce.
        rows = []
        remaining_cif = balance_cif
        skip_reasons = []  # Track why items were skipped for diagnostics

        matched_records = []
        for source_index, record in enumerate(records):
            record_id = record.get("record_id", "unknown")
            item_key = record.get("item_key", "-")
            match = configuration.match(record)
            if not match:
                skip_reasons.append({
                    "record_id": record_id,
                    "item_key": item_key,
                    "reason": "NO_RULE_MATCH"
                })
                continue
            rule, _output = match
            matched_records.append((rule.priority, source_index, record, match))

        for _priority, _source_index, record, match in sorted(
            matched_records,
            key=lambda value: (value[0], value[1]),
        ):
            record_id = record.get("record_id", "unknown")
            item_key = record.get("item_key", "-")
            rule, output = match

            # During execution (not preview), auto-create missing output items
            if not preview:
                try:
                    with transaction.atomic():
                        output_item = OutputItemResolver.resolve_or_create(rule)
                except Exception as exc:
                    raise InvalidPlannerConfiguration(
                        f"Failed to resolve output item for rule {rule.pk} ({rule.name}): {exc}"
                    ) from exc

            # Get the total quantity available
            available_qty = Decimal(str(record.get("available_quantity", 0)))
            total_imported_qty = Decimal(str(record.get("quantity", 0)))

            # ``force_plan`` controls whether an existing plan may be rebuilt;
            # it is not authority to consume already-used quantity.
            total_qty = available_qty

            if total_qty <= 0:
                skip_reasons.append({
                    "record_id": record_id,
                    "item_key": item_key,
                    "reason": "ZERO_QUANTITY",
                    "total_imported_qty": str(total_imported_qty),
                    "available_qty": str(available_qty),
                    "force_plan": force_plan
                })
                continue

            # Every execution path is capped by the live remaining CIF.
            unit_price = rule.max_unit_price or Decimal("0")

            if unit_price > 0:
                # Normal planning: cap by both available qty and balance
                qty_by_balance = remaining_cif / unit_price if remaining_cif > 0 else Decimal("0")
                planned_qty = min(available_qty, qty_by_balance)
            else:
                # Free items get all available quantity
                planned_qty = available_qty

            if planned_qty <= 0:
                continue

            # Calculate actual CIF consumed
            actual_value = planned_qty * unit_price
            remaining_cif -= actual_value

            # Add to result rows
            rows.append(
                PlanningRow(
                    record_id=str(record.get("record_id", "")),
                    category=output,
                    output_key=output,
                    quantity=planned_qty,
                    unit_price=unit_price,
                    value=actual_value,
                    source_output=None,
                )
            )

        # Return in the format expected by _compute_license caller
        # Include diagnostic info about skipped items
        metadata = {
            "method": "generic_rules",
            "force_plan": force_plan,
            "total_records_evaluated": len(records),
            "total_rows_planned": len(rows),
            "skip_reasons": skip_reasons if not rows and records else [],
        }

        # CRITICAL: If force_plan=True and we have records but no planned rows,
        # this is a configuration/matching error that should be reported
        if force_plan and records and not rows:
            metadata["warning"] = (
                f"Force plan enabled but no planning rows generated for "
                f"{len(records)} import items. Check SION rule matching and configuration."
            )

        return DatabaseDrivenPlanResult(
            rows=rows,
            remaining_cif=max(remaining_cif, Decimal("0")),
            metadata=metadata,
        )

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
                child = {
                    **detail,
                    "current_planned_quantity": current_qty,
                    "proposed_planned_quantity": proposed_qty,
                    "quantity_change": proposed_qty - current_qty,
                    "current_unit_price": existing_lines[0]["unit_price"] if existing_lines else None,
                    "proposed_unit_price": proposed_lines[0]["unit_price"] if proposed_lines else None,
                }
                split_lines = [
                    row for row in proposed_lines
                    if row.get("allocation_provenance", {}).get("allocation_strategy") == "SPLIT_BY_UNIT_VALUE"
                ]
                if split_lines:
                    provenance = split_lines[0]["allocation_provenance"]
                    allocated_qty = sum((cls._decimal(row["requested_quantity"]) for row in split_lines), Decimal("0"))
                    allocated_cif = sum((
                        cls._decimal(row["requested_quantity"]) * cls._decimal(row["unit_price"])
                        for row in split_lines
                    ), Decimal("0"))
                    total_qty = cls._decimal(provenance["original_quantity"])
                    balance = cls._decimal(provenance["original_balance_cif"])
                    child["allocation"] = {
                        "strategy": "SPLIT_BY_UNIT_VALUE",
                        "status": "ALLOCATED",
                        "total_quantity": total_qty,
                        "balance_cif": balance,
                        "effective_unit_price": balance / total_qty if total_qty else None,
                        "quantity_remaining": total_qty - allocated_qty,
                        "cif_remaining": balance - allocated_cif,
                        "lines": [{
                            "bucket": row["allocation_provenance"]["bucket"],
                            "quantity": row["requested_quantity"],
                            "unit_price": row["unit_price"],
                            "cif": cls._decimal(row["requested_quantity"]) * cls._decimal(row["unit_price"]),
                        } for row in split_lines],
                    }
                children.append(child)
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
        mode=PLAN_MODE_NEW, force_plan=False,
    ):
        """Execute saved DB classification through the proven E1/E5 mechanics.

        Args:
            sion: SionNormClassModel instance
            license_ids: Optional list of license IDs to plan
            company_id: Optional company ID for isolation
            persist: If True, save results to database
            mode: Planning mode (NEW or ALL)
            force_plan: If True, bypass balance_cif > 0 filter and availability caps
        """
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
                sion, license_ids, company_id=company_id, force_plan=force_plan,
            )
            for license_obj in licenses:
                from apps.license.services.planning_tolerances import effective_planning_balance_cif
                raw_balance_cif = cls._decimal(live_balances[license_obj.pk])
                effective_balance_cif = effective_planning_balance_cif(raw_balance_cif)
                # The export/history reconciliation identifies the maximum
                # entitlement remaining under this SION.  The actual live
                # license balance is an independent absolute cap, so use the
                # lower value.  This makes zero Actual Balance CIF fail closed
                # even for Force All / New Only runs.
                from apps.license.models import LicenseExportItemModel
                opening_operational_cif = sum((
                    cls._decimal(value) for value in LicenseExportItemModel.objects.filter(
                        license=license_obj, norm_class=sion,
                    ).values_list("cif_fc", flat=True)
                ), Decimal("0"))
                # Export-manifest CIF is a gross entitlement.  Historical
                # BOE/unlinked-allotment CIF is authoritative and consumes it
                # exactly once before the new-plan waterfall begins.
                from apps.license.services.planning_usage_reconciliation import aggregate_license_usage
                historical_usage = aggregate_license_usage(license_obj.pk)
                actual_debited_cif = sum((
                    bucket["boe_used_cif"] + bucket["unlinked_allotment_cif"]
                    for bucket in historical_usage["mapped"].values()
                ), Decimal("0")) + sum((
                    row["cif_fc"] for row in historical_usage["unmapped_usage"]
                ), Decimal("0"))
                reconciled_cif_ceiling = max(opening_operational_cif - actual_debited_cif, Decimal("0"))
                new_plan_cif_ceiling = min(
                    effective_balance_cif,
                    reconciled_cif_ceiling,
                )
                lines, remaining, planning_metadata = cls._compute_license(
                    license_obj, sion, preview=not persist, force_plan=force_plan,
                    operational_balance_cif=new_plan_cif_ceiling,
                )
                canonical_lines = [{
                    "import_item_id": row["import_item"],
                    "item_name_id": row.get("item_name"),
                    "requested_quantity": row["planned_quantity"],
                    "unit_price": row["unit_price"],
                    "priority": index,
                    "note": row.get("note", ""),
                    "planning_rule_id": row.get("planning_rule_id"),
                    "planning_rule_version": row.get("planning_rule_version"),
                    "planning_rule_priority": row.get("planning_rule_priority"),
                    "allocation_provenance": row.get("allocation_provenance", {}),
                } for index, row in enumerate(lines)]
                result = {
                    "license_id": license_obj.pk,
                    "license_number": license_obj.license_number,
                    "lines": canonical_lines,
                    "remaining_balance_cif": remaining,
                    "status": "PLANNED" if persist else "PREVIEWED",
                    "raw_balance_cif": raw_balance_cif,
                    "effective_balance_cif": effective_balance_cif,
                    "planning_cif_ceiling": planning_metadata.get("planning_cif_ceiling", opening_operational_cif),
                    "remaining_planning_cif": planning_metadata.get("remaining_waterfall_cif", remaining),
                    "opening_operational_cif": opening_operational_cif,
                    "actual_debited_cif": actual_debited_cif,
                    "new_plan_cif_ceiling": new_plan_cif_ceiling,
                    "remaining_operational_cif": planning_metadata.get("remaining_waterfall_cif", remaining),
                    "balance_cif_ignored_by_tolerance": raw_balance_cif != effective_balance_cif,
                    # Development/API-safe explanation of every persisted-rule
                    # stage, including matched sources skipped solely because
                    # an earlier priority exhausted operational capacity.
                    "waterfall_trace": planning_metadata.get("waterfall", []),
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
                    if planning_metadata.get("architecture") == "strategy":
                        result["write_result"] = CanonicalPlanningService.build_theoretical_strategy_plan(
                            license_id=license_obj.pk,
                            norm_class=sion.norm_class,
                            items=canonical_lines,
                            total_cif_ceiling=planning_metadata["total_cif"],
                            company_id=company_id,
                        )
                    else:
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
