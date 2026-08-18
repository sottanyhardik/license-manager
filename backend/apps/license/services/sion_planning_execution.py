"""Database-driven SION planning orchestration.

All planning is driven by persisted SION rules and profiles stored in the
database. Classification and allocation logic is centralized in the generic
planning engine, eliminating norm-specific dispatch.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Any

from django.db import transaction

from apps.license.services.sion_rule_engine import evaluate_expression
from apps.license.services.output_item_resolver import OutputItemResolver


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


class SionPlanningExecutionService:
    """Generic database-driven planning orchestration for all SIONs."""

    @classmethod
    def resolve_configuration(cls, sion) -> ResolvedPlannerConfiguration:
        from apps.license.models import SionPlanningProfile, SionPlanningRule

        rules = tuple(SionPlanningRule.objects.filter(
            sion=sion, is_active=True,
        ).order_by("priority", "pk"))
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
        # When force_plan=True, don't filter out licenses with zero balance_cif
        # They can still be planned; balance_cif becomes informational
        if not force_plan:
            from apps.license.services.planning_tolerances import effective_planning_balance_cif
            licenses = [
                row for row in licenses
                if effective_planning_balance_cif(live_balances.get(row.pk, Decimal("0"))) > 0
            ]
        return licenses, live_balances

    @classmethod
    def _compute_license_new_architecture(cls, license_obj, sion, strategy_rules, *, preview, force_plan=False):
        """Build the full theoretical plan directly from strategy configuration."""
        from apps.license.models import LicenseImportItemsModel, LicenseExportItemModel
        from apps.license.services.canonical_planning_service import (
            SplitPercentIncompleteError,
            SplitPercentQuantityMismatchError,
        )

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

        def matching_group(item_name_id):
            matched = [item for item in import_items if item_name_id in item_name_ids[item.pk]]
            # A single physical entitlement row is unambiguous even when an
            # older import did not populate its item-name M2M classification.
            return matched or (import_items if len(import_items) == 1 else [])

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
                return matched
            # Compatibility for pre-redesign strategy records created with an
            # empty expression. Newly edited rules use explicit match logic.
            return matching_group(fallback_item_name_id) if fallback_item_name_id else []

        def original_group_quantity(group):
            # Entitlements are recorded at 3dp, while this SION plans whole kg.
            return sum((Decimal(str(item.quantity or 0)) for item in group), Decimal("0")).quantize(
                Decimal("1"), rounding=ROUND_DOWN,
            )

        def add_line(rule, item_name, group, quantity, price, provenance):
            if not group or quantity <= 0:
                return False
            all_lines.append({
                "import_item": group[0].pk,
                "item_name": item_name.pk,
                "planned_quantity": quantity,
                "unit_price": price,
                "planned_cif": quantity * price,
                "planning_rule_id": rule.pk,
                "planning_rule_version": rule.version,
                "planning_rule_priority": rule.priority,
                "allocation_provenance": provenance,
            })
            return True

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
        for rule in strategy_rules:
            if rule.strategy == "STANDARD":
                group = source_group(rule, rule.import_item_id) if rule.import_item_id else []
                quantity = original_group_quantity(group)
                add_line(rule, rule.import_item, group, quantity, rule.max_unit_price, {
                    "strategy": "STANDARD", "quantity_source": "original_import_group_quantity",
                })
                continue

            if rule.strategy == "SPLIT_BY_UNIT_VALUE":
                for row in rule.unit_value_rows.all().order_by("priority", "pk"):
                    group = source_group(rule, row.import_item_id)
                    quantity = original_group_quantity(group)
                    add_line(rule, row.import_item, group, quantity, row.preferred_unit_price, {
                        "strategy": "SPLIT_BY_UNIT_VALUE",
                        "quantity_source": "original_import_group_quantity",
                        "min_unit_price": str(row.min_unit_price),
                        "max_unit_price": str(row.max_unit_price),
                    })
                continue

            if rule.strategy == "SPLIT_BY_PERCENT":
                configured = list(rule.percentage_rows.all().order_by("priority", "pk"))
                # All rows in one percentage rule describe alternate labels for the
                # same entitlement group. Count each physical import row once.
                matched_source = source_group(rule, configured[0].import_item_id if configured else None)
                matched_by_row = {row.pk: matched_source for row in configured}
                total_planning_quantity = original_group_quantity(matched_source)
                generated = 0
                assigned_nominal = Decimal("0")
                generated_quantity_total = Decimal("0")
                rule_percent_total = sum((row.percentage for row in configured), Decimal("0"))
                use_global_split = rule_percent_total != Decimal("100") and global_percent_total == Decimal("100")
                for row_index, row in enumerate(configured):
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
                    final_quantity = nominal
                    generated_quantity_total += final_quantity
                    generated += int(add_line(rule, row.import_item, matched_by_row[row.pk], final_quantity,
                                              row.unit_price, {
                        "strategy": "SPLIT_BY_PERCENT",
                        "percentage": str(row.percentage),
                        "total_planning_quantity": str(total_planning_quantity),
                        "raw_nominal_quantity": str(raw_nominal),
                        "nominal_quantity": str(nominal),
                        "legacy_max_quantity_ignored": (
                            str(row.max_quantity) if row.max_quantity is not None else None
                        ),
                        "quantity_source": "original_import_group_quantity",
                    }))
                    diagnostics.append({
                        "rule_id": rule.pk, "row_id": row.pk, "item_name": row.import_item.name,
                        "raw_nominal_quantity": str(raw_nominal),
                        "nominal_quantity": str(nominal), "max_quantity": str(row.max_quantity),
                        "generated": bool(matched_by_row[row.pk] and final_quantity > 0),
                    })
                if configured and total_planning_quantity > 0 and generated != len(configured):
                    raise SplitPercentIncompleteError(
                        "Not every configured SPLIT_BY_PERCENT row produced a plan line.",
                        rule_id=rule.pk, configured_rows=len(configured), generated_rows=generated,
                        rows=diagnostics,
                    )
                if (
                    configured
                    and total_planning_quantity > 0
                    and rule_percent_total == Decimal("100")
                    and abs(generated_quantity_total - total_planning_quantity) > Decimal("0.001")
                ):
                    raise SplitPercentQuantityMismatchError(
                        "A 100% SPLIT_BY_PERCENT rule did not allocate the full source quantity.",
                        rule_id=rule.pk,
                        source_quantity=str(total_planning_quantity),
                        generated_quantity=str(generated_quantity_total),
                        percentage_total=str(rule_percent_total),
                    )

        planned_cif = sum((line["planned_cif"] for line in all_lines), Decimal("0"))
        return all_lines, total_cif - planned_cif, {
            "architecture": "strategy", "total_cif": total_cif,
            "total_planned_cif": planned_cif, "percentage_rows": diagnostics,
        }

    @classmethod
    def _compute_license_split_by_percentage_new(cls, license_obj, sion, percent_rules, *, total_qty, total_cif, preview):
        """Split by percentage using per-row unit price for CIF calculation.

        Args:
            percent_rules: List of SionPlanningRule with strategy="SPLIT_BY_PERCENT"
            total_qty: Total license quantity
            total_cif: Total license CIF
        """
        from apps.license.services.database_driven_sion_planner import DatabaseDrivenPlanResult, PlanningRow

        rows = []
        for rule in percent_rules:
            for row in rule.percentage_rows.all().order_by("priority"):
                planned_qty = total_qty * (row.percentage / Decimal("100"))
                planned_cif = planned_qty * row.unit_price

                rows.append(PlanningRow(
                    record_id=None,
                    category=row.import_item.name.upper(),
                    output_key=row.import_item.name.upper(),
                    quantity=planned_qty,
                    unit_price=row.unit_price,
                    value=planned_cif,
                ))

        result = DatabaseDrivenPlanResult(
            rows=rows,
            remaining_cif=total_cif,  # Percentage rules don't consume balance
            metadata={"strategy": "SPLIT_BY_PERCENT"}
        )
        return result

    @classmethod
    def _compute_license(cls, license_obj, sion, *, preview, force_plan=False):
        """Compute planned lines using database-driven rules and generic planner.

        Args:
            license_obj: LicenseDetailsModel instance
            sion: SionNormClassModel instance
            preview: If True, don't persist ItemNameModel creation
            force_plan: If True, bypass availability constraints
        """
        from apps.license.services.database_driven_sion_planner import DatabaseDrivenSionPlanner
        from apps.license.models import LicenseImportItemsModel, SionPlanningProfile, SionPlanningRule

        # NEW ARCHITECTURE: Check for rules with strategy set (new dispatch path)
        active_rules = list(SionPlanningRule.objects.filter(sion=sion, is_active=True).order_by("priority"))
        strategy_rules = [r for r in active_rules if r.strategy]

        if strategy_rules:
            # New architecture: dispatch by strategy
            return cls._compute_license_new_architecture(
                license_obj, sion, strategy_rules, preview=preview, force_plan=force_plan
            )

        # LEGACY ARCHITECTURE: fallback to old dispatch path (strategy=None rules)
        # Check if all active rules use SPLIT_BY_PERCENTAGE strategy
        if active_rules and all(r.rule_type == 'SPLIT_BY_PERCENTAGE' for r in active_rules):
            split_result = cls._compute_license_split_by_percentage(license_obj, sion, active_rules, preview=preview)
            # Convert SPLIT_BY_PERCENTAGE result to canonical format
            lines = []
            for row in split_result.rows:
                lines.append({
                    "import_item": row.record_id,
                    "planned_quantity": row.quantity,
                    "unit_price": row.unit_price,
                    "planning_rule_id": None,
                    "planning_rule_version": None,
                    "planning_rule_priority": None,
                    "allocation_provenance": {"strategy": "SPLIT_BY_PERCENTAGE"},
                })
            return lines, split_result.remaining_cif, split_result.metadata

        # Collect import items as records for the generic planner
        import_items = list(
            LicenseImportItemsModel.objects.filter(license=license_obj)
            .select_related("hs_code").prefetch_related("items")
            .order_by("pk")
        )
        records = []
        for item in import_items:
            item_names = [row.name for row in item.items.all()]
            records.append({
                "record_id": item.pk,
                "item_key": ", ".join(sorted(item_names)) if item_names else (item.description or "-"),
                "hs_code": item.hs_code.hs_code if item.hs_code_id else "",
                "description": item.description or "",
                "available_quantity": item.available_quantity,
                "quantity": item.quantity,
                "unit": item.unit or "",
                "serial_number": item.serial_number,
            })

        # Get the balance for planning
        balance_cif = Decimal(str(license_obj.get_balance_cif or 0))

        # Load the profile if it exists; use generic execution
        profile = SionPlanningProfile.objects.filter(sion=sion).order_by(
            "-is_active", "-version", "-pk",
        ).prefetch_related("actions", "output_mappings").first()

        planner = DatabaseDrivenSionPlanner()
        # A profile with no active actions is equivalent to no profile.
        # Fall back to generic rules-based planning in this case.
        has_active_actions = (
            profile and profile.actions.filter(is_active=True).exists()
        )
        if profile and has_active_actions:
            result = planner.execute_profile(profile, records, balance_cif)
        else:
            # Generic rules-based planning when no profile exists or profile
            # has no active actions. Uses database rules directly without
            # legacy profile machinery.
            result = cls._compute_license_generic(
                license_obj, sion, records, balance_cif, preview=preview, force_plan=force_plan
            )

        # Convert planner output to canonical format expected by plan_sion()
        lines = []
        for row in result.rows:
            lines.append({
                "import_item": row.record_id,
                "planned_quantity": row.quantity,
                "unit_price": row.unit_price,
                "planning_rule_id": None,  # Will be populated by rule matching
                "planning_rule_version": None,
                "planning_rule_priority": None,
                "allocation_provenance": result.metadata.get("strategy") == "SPLIT_BY_PERCENTAGE" and {
                    "strategy": "SPLIT_BY_PERCENTAGE"
                } or {},
            })

        return lines, result.remaining_cif, result.metadata

    @classmethod
    def _compute_license_split_by_percentage(cls, license_obj, sion, rules, *, preview: bool):
        """Calculate plan for SPLIT_BY_PERCENTAGE strategy without matching import items.

        Each rule with a percentage_constraint generates one planned line:
        - planned_quantity = total_quantity × percentage_constraint / 100
        - planned_cif = total_cif × percentage_constraint / 100

        This bypasses import-item matching and uses SION rule percentages directly.
        """
        from apps.license.services.database_driven_sion_planner import DatabaseDrivenPlanResult, PlanningRow
        from apps.license.models import LicenseExportItemModel

        # Calculate total quantity and CIF from all import items
        from apps.license.models import LicenseImportItemsModel
        first_import_item = LicenseImportItemsModel.objects.filter(
            license=license_obj,
        ).order_by("pk").first()
        total_qty = Decimal('0')
        for item in LicenseImportItemsModel.objects.filter(license=license_obj):
            total_qty += Decimal(str(item.quantity or 0))

        # Calculate total CIF from export items for the SION
        total_cif = Decimal('0')
        for export_item in LicenseExportItemModel.objects.filter(license=license_obj, norm_class=sion):
            total_cif += Decimal(str(export_item.cif_fc or 0))

        rows = []
        for rule in rules:
            if not rule.percentage_constraint:
                continue

            percentage = Decimal(str(rule.percentage_constraint))
            planned_qty = total_qty * (percentage / Decimal('100'))
            planned_cif = total_cif * (percentage / Decimal('100'))

            if first_import_item is None:
                continue
            row = PlanningRow(
                record_id=first_import_item.pk,
                category=(rule.execution_output or rule.name).strip(),
                output_key=(rule.import_item.name if rule.import_item else rule.name).upper(),
                quantity=planned_qty,
                unit_price=(planned_cif / planned_qty) if planned_qty else Decimal("0"),
                value=planned_cif,
            )
            rows.append(row)

        # Return result with no remaining CIF constraint for SPLIT_BY_PERCENTAGE
        result = DatabaseDrivenPlanResult(
            rows=rows,
            remaining_cif=total_cif,  # Don't deduct; percentage rules don't consume balance
            metadata={
                "strategy": "SPLIT_BY_PERCENTAGE",
                "total_quantity": str(total_qty),
                "total_cif": str(total_cif),
            }
        )
        return result

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
            force_plan: If True, bypass availability and balance_cif constraints

        Returns:
            DatabaseDrivenPlanResult with planned rows and remaining CIF
        """
        from apps.license.services.database_driven_sion_planner import (
            DatabaseDrivenPlanResult, PlanningRow, InvalidPlannerConfiguration
        )
        from apps.license.models import SionPlanningRule

        # Get the configuration (rules)
        configuration = cls.resolve_configuration(sion)

        # Match and plan each record
        rows = []
        remaining_cif = balance_cif
        skip_reasons = []  # Track why items were skipped for diagnostics

        for record in records:
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

            # For force_plan, use the total imported quantity; otherwise use available_qty
            if force_plan:
                total_qty = total_imported_qty
            else:
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

            # Calculate quantity that fits within balance (or planned quantity if force_plan)
            unit_price = rule.max_unit_price or Decimal("0")

            if force_plan:
                # Force plan: use the full required quantity, treat balance as warning only
                planned_qty = total_qty
            elif unit_price > 0:
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
                sion, license_ids, company_id=company_id, force_plan=force_plan,
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
                from apps.license.services.planning_tolerances import effective_planning_balance_cif
                raw_balance_cif = cls._decimal(live_balances[license_obj.pk])
                effective_balance_cif = effective_planning_balance_cif(raw_balance_cif)
                if (
                    # Only skip ALREADY_PLANNED check when force_plan is True
                    # force_plan means rebuild everything, not "add only new"
                    not force_plan
                    and mode == PLAN_MODE_NEW
                    and planned_cif_by_license.get(license_obj.pk, Decimal("0")) > 0
                    and planned_cif_by_license[license_obj.pk] >= (
                        effective_balance_cif * ALREADY_PLANNED_THRESHOLD
                    )
                ):
                    results.append({
                        "license_id": license_obj.pk,
                        "license_number": license_obj.license_number,
                        "lines": [],
                        "status": "SKIPPED_ALREADY_PLANNED",
                        "raw_balance_cif": raw_balance_cif,
                        "effective_balance_cif": effective_balance_cif,
                        "balance_cif_ignored_by_tolerance": raw_balance_cif != effective_balance_cif,
                        **({
                            "write_result": {
                                "license_id": license_obj.pk,
                                "status": "SKIPPED_ALREADY_PLANNED",
                            },
                        } if persist else {}),
                    })
                    continue
                lines, remaining, planning_metadata = cls._compute_license(
                    license_obj, sion, preview=not persist, force_plan=force_plan,
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
                    "balance_cif_ignored_by_tolerance": raw_balance_cif != effective_balance_cif,
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
