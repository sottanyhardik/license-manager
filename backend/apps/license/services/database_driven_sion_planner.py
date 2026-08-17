"""Declarative SION action-pipeline executor.

The executor intentionally knows action/algorithm vocabulary, never SION codes.
It accepts the normalized documents persisted by the profile importer as well
as the audited source documents used during shadow migration.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_EVEN
import re
from typing import Any, Iterable


ZERO = Decimal("0")
FOUR_DP = Decimal("0.0001")


def decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value in (None, ""):
        return ZERO
    return Decimal(str(value))


@dataclass
class PlanningRow:
    record_id: str
    category: str
    output_key: str
    quantity: Decimal
    unit_price: Decimal
    value: Decimal
    source_output: str | None = None
    sequence: int = 0


@dataclass
class DatabaseDrivenPlanResult:
    rows: list[PlanningRow]
    remaining_cif: Decimal
    metadata: dict[str, Any]


class InvalidPlannerConfiguration(ValueError):
    pass


class DatabaseDrivenSionPlanner:
    """Execute a validated profile using a closed set of generic primitives."""

    ACTION_TYPES = {"MATCH", "PRICE", "GROUP", "ALLOCATE", "SPLIT", "REBALANCE", "ROUND", "MAP_OUTPUT"}

    def execute_profile(self, profile, records, balance_cif, *, options=None, include_inactive_rules=False):
        """Load the pipeline from ORM rows and execute that immutable snapshot.

        Production callers use active rules. Shadow migration may explicitly
        include inactive imported rules while the profile is still gated.
        """
        from apps.license.models import SionPlanningRule

        actions = list(profile.actions.filter(is_active=True).order_by("priority", "pk"))
        mappings = list(profile.output_mappings.filter(is_active=True).select_related("source_rule").order_by("priority", "pk"))
        rule_query = SionPlanningRule.objects.filter(sion_id=profile.sion_id)
        if not include_inactive_rules:
            rule_query = rule_query.filter(is_active=True)
        output_by_rule = {
            str(mapping.source_rule.stable_key): mapping.config.get("source_key")
            for mapping in mappings if mapping.source_rule_id
        }
        for action in actions:
            output_by_rule.update(action.config.get("rule_outputs", {}))
        rules = [{
            "stable_key": rule.stable_key,
            "name": rule.name,
            "priority": rule.priority,
            "expression": rule.expression,
            "max_unit_price": str(rule.max_unit_price),
            "unit": rule.unit,
            "output_key": output_by_rule.get(rule.stable_key),
        } for rule in rule_query.order_by("priority", "pk") if output_by_rule.get(rule.stable_key)]
        definition = {
            "profile": {"stable_key": profile.stable_key, "config": profile.config, "version": profile.version},
            "rules": rules,
            "actions": [{"stable_key": row.stable_key, "action_type": row.action_type, "priority": row.priority, "config": row.config} for row in actions],
            "mappings": [{
                "stable_key": row.stable_key,
                "source_key": row.config.get("source_key"),
                "output_name": row.config.get("output_name"),
                "rate": str(row.rate) if row.rate is not None else None,
                "conversion_factor": str(row.conversion_factor),
                "unit": row.unit,
                "priority": row.priority,
            } for row in mappings],
        }
        return self.execute(definition, records, balance_cif, options=options)

    def execute(
        self,
        definition: dict[str, Any],
        records: Iterable[dict[str, Any]],
        balance_cif: Any,
        *,
        options: dict[str, Any] | None = None,
    ) -> DatabaseDrivenPlanResult:
        state = _State(definition, list(deepcopy(list(records))), decimal(balance_cif), options or {})
        self._validate(definition)
        for action in sorted(state.actions, key=lambda row: (row.get("priority", 0), row.get("stable_key", ""))):
            handler = getattr(self, f"_action_{action['action_type'].lower()}")
            handler(state, action.get("config", {}))
        return DatabaseDrivenPlanResult(state.rows, state.remaining, state.metadata)

    def _validate(self, definition: dict[str, Any]) -> None:
        actions = definition.get("actions", ())
        unknown = {row.get("action_type") for row in actions} - self.ACTION_TYPES
        if unknown:
            raise InvalidPlannerConfiguration(f"Unsupported action types: {sorted(unknown)}")
        priorities = [row.get("priority") for row in actions]
        if len(priorities) != len(set(priorities)):
            raise InvalidPlannerConfiguration("Action priorities must be unique.")

    def _action_match(self, state: "_State", config: dict[str, Any]) -> None:
        rules = config.get("rules") or state.rules
        for record in state.records:
            # Golden E1/E5 inputs and canonical callers may supply a trusted,
            # already-classified category. Raw inputs always use DB rules.
            if record.get("category"):
                record["matched_output"] = record["category"]
                continue
            for rule in sorted(rules, key=lambda row: row.get("priority", 0)):
                if _matches(rule.get("expression", {}), record):
                    record["matched_output"] = rule.get("output_key") or rule.get("category")
                    record["matched_rule"] = rule
                    break

    def _action_split(self, state: "_State", config: dict[str, Any]) -> None:
        algorithm = config.get("algorithm")
        if algorithm in {"MILK_0404_MAXIMISE_DWP", "ORDERED_MILK_0404_THEN_WPC_3502"}:
            self._execute_deferred_split(state, config)
            return
        source = config["source_output"]
        targets = config["targets"]
        expanded = []
        for record in state.records:
            if record.get("matched_output") != source:
                expanded.append(record)
                continue
            for target, ratio in targets.items():
                child = deepcopy(record)
                child["matched_output"] = target
                child["source_output"] = source
                child["quantity"] = _quantity(record) * decimal(ratio)
                child["available_quantity"] = child["quantity"]
                expanded.append(child)
        state.records = expanded

    def _action_group(self, state: "_State", config: dict[str, Any]) -> None:
        # E1/E5 deliberately preserve rows. Other profiles aggregate records
        # only when their configured physical/classification identity agrees.
        if config.get("preserve_input_order") or config.get("by") == "MATCH_CATEGORY":
            return
        grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
        for sequence, record in enumerate(state.records):
            output = record.get("matched_output")
            if not output:
                continue
            if config.get("mode") == "CLASSIFICATION_IDENTITY":
                identity = tuple(record.get(field) for field in config.get("identity_fields", ()))
            else:
                identity = (
                    _hsn(record), _description(record), record.get("unit"),
                    record.get("item_name") or record.get("item_key"),
                )
            key = (output, identity)
            if key not in grouped:
                grouped[key] = deepcopy(record)
                grouped[key]["_sequence"] = sequence
                grouped[key]["quantity"] = ZERO
            grouped[key]["quantity"] += _quantity(record)
            grouped[key]["available_quantity"] = grouped[key]["quantity"]
        state.records = sorted(grouped.values(), key=lambda row: row["_sequence"])

    def _action_price(self, state: "_State", config: dict[str, Any]) -> None:
        if config.get("mode") != "MAPPED_WITH_CONDITIONAL":
            raise InvalidPlannerConfiguration(f"Unsupported pricing mode: {config.get('mode')}")
        state.prices.update({key: decimal(value) for key, value in config.get("prices", {}).items()})
        conditional = config["conditional"]
        aggregate = conditional["aggregate"]
        numerator = sum((decimal(row.get(aggregate["numerator"])) for row in state.records if row.get("matched_output")), ZERO)
        denominator = sum((decimal(row.get(aggregate["denominator"])) for row in state.records if row.get("matched_output")), ZERO)
        value = numerator / denominator if denominator else ZERO
        for branch in conditional["branches"]:
            if _compare(value, branch["operator"], decimal(branch["value"])):
                state.prices[conditional["output"]] = decimal(branch["price"])
                break

    def _action_allocate(self, state: "_State", config: dict[str, Any]) -> None:
        algorithm = config.get("algorithm") or config.get("mode")
        if algorithm == "CONDITIONAL_BRANCH":
            triggered = _condition(config["condition"], state)
            branch = config["when_true"] if triggered else config["when_false"]
            state.pipeline = branch["pipeline"]
            state.branch_config = branch
            state.metadata["special_validation_triggered"] = triggered
            if triggered:
                self._allocate_categories(state, branch["milk_categories"], decimal(branch["milk_rate"]), "ITEM", config=branch, output="SWP")
            return
        memberships = config.get("pipeline_membership")
        if memberships and state.pipeline not in memberships:
            return
        if algorithm == "CAPPED_FIXED_RATE_WATERFALL":
            self._allocate_categories(state, [config["category"]], decimal(config["rate"]), config["granularity"], config=config)
        elif algorithm == "ORDERED_CATEGORY_FIXED_RATE":
            for category in config["categories"]:
                self._allocate_categories(state, [category["category"]], decimal(category["rate"]), config["granularity"], config=config)
        elif algorithm == "REMAINING_BALANCE_SHARED_RATE":
            records = state.for_outputs([config["category"]])
            total = sum((_quantity(row) for row in records), ZERO)
            if total > 0 and state.remaining > 0:
                self._allocate_categories(state, [config["category"]], state.remaining / total, config["granularity"], config=config)
        elif algorithm == "SEQUENTIAL_CIF_WATERFALL":
            self._allocate_waterfall(state, config)
        else:
            raise InvalidPlannerConfiguration(f"Unsupported allocation algorithm: {algorithm}")

    def _allocate_categories(self, state: "_State", categories: list[str], rate: Decimal, granularity: str, *, config: dict[str, Any], output: str | None = None) -> None:
        records = state.for_outputs(categories)
        floor = bool(state.options.get("floor_qty", False))
        minimum = decimal(state.options.get("min_plan_qty", 0))
        records = [row for row in records if _quantity(row) >= minimum]
        if granularity == "CATEGORY_SHARED_RATE":
            total = sum((_quantity(row) for row in records), ZERO)
            effective = min(rate, state.remaining / total) if total and state.remaining > 0 else ZERO
            for row in records:
                state.emit(row, output or row["matched_output"], _quantity(row), effective)
            state.remaining -= min(state.remaining, total * rate)
            return
        for row in records:
            if state.remaining <= 0:
                break
            quantity = _quantity(row)
            effective = rate
            if quantity * rate > state.remaining:
                policy = config.get("auto_insufficient_balance") if floor else config.get("reporting_insufficient_balance")
                if policy in {"KEEP_RATE_FLOOR_QUANTITY", "FLOOR_QUANTITY_KEEP_RATE"}:
                    quantity = (state.remaining / rate).to_integral_value(rounding=ROUND_FLOOR)
                else:
                    effective = state.remaining / quantity
            value = quantity * effective
            state.emit(row, output or row["matched_output"], quantity, effective)
            state.remaining -= value

    def _allocate_waterfall(self, state: "_State", config: dict[str, Any]) -> None:
        for output in config["order"]:
            rate = state.price_for(output)
            for record in state.for_outputs([output]):
                if state.remaining <= 0 or rate <= 0:
                    continue
                quantity = _quantity(record)
                if quantity * rate > state.remaining:
                    if config.get("partial_mode") == "REDUCE_QUANTITY":
                        quantity = (state.remaining / rate).to_integral_value(rounding=ROUND_FLOOR)
                    else:
                        rate = state.remaining / quantity
                state.emit(record, output, quantity, rate)
                state.remaining -= quantity * rate

    def _action_rebalance(self, state: "_State", config: dict[str, Any]) -> None:
        if config.get("mode") != "VALUE_GAIN_SHIFT" or state.remaining <= 0:
            return
        source, target = config["source"], config["target"]
        source_rate, target_rate = state.price_for(source), state.price_for(target)
        gain = target_rate - source_rate
        if gain <= 0:
            return
        for source_row in [row for row in state.rows if row.output_key == source and row.source_output == config["eligible_source"]]:
            shift = min(source_row.quantity, state.remaining / gain)
            if shift <= 0:
                continue
            source_row.quantity -= shift
            source_row.value = source_row.quantity * source_row.unit_price
            target_row = next((row for row in state.rows if row.record_id == source_row.record_id and row.output_key == target), None)
            if target_row is None:
                target_row = PlanningRow(source_row.record_id, source_row.category, target, ZERO, target_rate, ZERO, config["eligible_source"], source_row.sequence)
                state.rows.append(target_row)
            target_row.quantity += shift
            target_row.value = target_row.quantity * target_row.unit_price
            state.remaining -= shift * gain

    def _action_round(self, state: "_State", config: dict[str, Any]) -> None:
        if "fields" in config:
            quantum = Decimal(1).scaleb(-int(config["precision"]))
            for row in state.rows:
                row.unit_price = row.unit_price.quantize(quantum)
                row.value = row.value.quantize(quantum)
            return
        quantity_policy = config.get("quantity", {})
        value_policy = config.get("planned_cif", {})
        for row in state.rows:
            # REDUCE_QUANTITY profiles require final integer flooring. Split
            # profiles retain exact fractional quantities for value-gain shifts.
            if config.get("residual") == "CARRY_FORWARD" and quantity_policy:
                row.quantity = _quantize(row.quantity, quantity_policy)
                row.value = row.quantity * row.unit_price
            if value_policy:
                row.value = _quantize(row.value, value_policy)
        if config.get("residual") == "CARRY_FORWARD":
            state.remaining = state.starting_balance - sum((row.value for row in state.rows), ZERO)

    def _action_map_output(self, state: "_State", config: dict[str, Any]) -> None:
        if config.get("omit_zero_value"):
            state.rows = [row for row in state.rows if row.quantity > 0 and row.value > 0]

    def _action_group_unused(self, state: "_State", config: dict[str, Any]) -> None:  # pragma: no cover
        pass

    def _action_split_milk(self, state: "_State", config: dict[str, Any]) -> None:  # pragma: no cover
        pass

    def _execute_deferred_split(self, state: "_State", config: dict[str, Any]) -> None:
        memberships = config.get("pipeline_membership")
        if memberships and state.pipeline not in memberships:
            return
        categories = [config.get("category") or config.get("milk_category")]
        for record in state.for_outputs(categories):
            self._milk_split(state, record, config)
        wpc_category = config.get("wpc_category")
        if wpc_category:
            for record in state.for_outputs([wpc_category]):
                if state.remaining <= 0:
                    break
                rate = min(decimal(config["wpc_max_rate"]), state.remaining / _quantity(record))
                state.emit(record, "WPC", _quantity(record), rate)
                state.remaining -= _quantity(record) * rate

    @staticmethod
    def _milk_split(state: "_State", record: dict[str, Any], config: dict[str, Any]) -> None:
        qty = _quantity(record)
        max_rate, min_rate, swp_rate = map(decimal, (config["dwp_max_rate"], config["dwp_min_rate"], config["swp_rate"]))
        average = state.remaining / qty if qty else ZERO
        if average >= max_rate:
            dwp_qty, dwp_rate, swp_qty = qty, max_rate, ZERO
        elif average >= min_rate:
            dwp_qty, dwp_rate, swp_qty = qty, average, ZERO
        elif average >= swp_rate:
            dwp_qty = min(qty, max(ZERO, (state.remaining - swp_rate * qty) / (min_rate - swp_rate)))
            dwp_rate, swp_qty = min_rate, qty - dwp_qty
        else:
            dwp_qty, dwp_rate, swp_qty = ZERO, max_rate, state.remaining / swp_rate
        if dwp_qty > 0:
            state.emit(record, "DWP", dwp_qty, dwp_rate)
            state.remaining -= dwp_qty * dwp_rate
        if swp_qty > 0:
            state.emit(record, "SWP", swp_qty, swp_rate)
            state.remaining -= swp_qty * swp_rate


class _State:
    def __init__(self, definition, records, balance, options):
        self.definition = definition
        self.records = records
        self.starting_balance = balance
        self.remaining = balance
        self.options = options
        self.rows: list[PlanningRow] = []
        self.metadata: dict[str, Any] = {}
        self.pipeline: str | None = None
        self.branch_config: dict[str, Any] = {}
        self.deferred_splits: list[dict[str, Any]] = []
        self.sequence = 0
        self.rules = definition.get("rules", ())
        self.actions = definition.get("actions", ())
        self.mappings = definition.get("mappings", ())
        self.prices = {row.get("source_key"): decimal(row.get("rate")) for row in self.mappings if row.get("rate") is not None}
        self.prices.update({row.get("output_key"): decimal(row.get("max_unit_price")) for row in self.rules})

    def for_outputs(self, outputs):
        # Deferred milk split actions execute at their configured position,
        # just before the first following allocation needs those categories.
        return [row for row in self.records if row.get("matched_output") in outputs]

    def price_for(self, output):
        return self.prices.get(output, ZERO)

    def emit(self, record, output, quantity, rate):
        if quantity <= 0 or rate <= 0:
            return
        self.sequence += 1
        self.rows.append(PlanningRow(
            str(record.get("record_id") or record.get("key") or record.get("id") or self.sequence),
            str(record.get("category") or record.get("matched_output") or ""), output,
            quantity, rate, quantity * rate, record.get("source_output"), self.sequence,
        ))


def _quantity(record):
    return decimal(record.get("available_quantity", record.get("quantity", record.get("qty", 0))))


def _hsn(record):
    return "".join(character for character in str(record.get("hs_code") or record.get("hsn") or "") if character.isdigit())


def _description(record):
    return " ".join(str(record.get("description") or record.get("product_description") or "").casefold().split())


def _matches(expression, record):
    operator = expression.get("operator")
    children = expression.get("conditions")
    if children is not None:
        values = [_matches(child, record) for child in children]
        if operator == "AND": return bool(values) and all(values)
        if operator == "OR": return any(values)
        if operator == "NOT": return len(values) == 1 and not values[0]
        raise InvalidPlannerConfiguration(f"Unsupported boolean operator: {operator}")
    field = expression.get("field")
    if field in {"HSN", "HSN_DIGITS"}:
        haystack = _hsn(record)
    elif field == "ITEM_KEY":
        haystack = str(record.get("item_key") or record.get("item_name") or "").casefold().strip()
    else:
        haystack = _description(record)
    needle = str(expression.get("value", "")).casefold()
    if operator == "CONTAINS": return needle in haystack
    if operator == "NOT_CONTAINS": return needle not in haystack
    if operator == "STARTS_WITH": return haystack.startswith(needle)
    if operator == "NOT_STARTS_WITH": return not haystack.startswith(needle)
    if operator == "EQUALS": return haystack == needle
    if operator == "WORD_CONTAINS": return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack) is not None
    raise InvalidPlannerConfiguration(f"Unsupported match operator: {operator}")


def _compare(left, operator, right):
    return {"LT": left < right, "LTE": left <= right, "GT": left > right, "GTE": left >= right, "EQ": left == right}[operator]


def _operand(value, state):
    if "constant" in value: return decimal(value["constant"])
    if value.get("field") == "REMAINING_CIF": return state.remaining
    if value.get("aggregate") == "SUM_QUANTITY":
        return sum((_quantity(row) for row in state.records if row.get("matched_output") in value.get("categories", [value.get("category")])), ZERO)
    operation = value.get("operation")
    args = [_operand(arg, state) for arg in value.get("arguments", ())]
    if operation == "MULTIPLY": return args[0] * args[1]
    if operation == "DIVIDE": return args[0] / args[1] if args[1] else ZERO
    raise InvalidPlannerConfiguration(f"Unsupported safe formula: {operation}")


def _condition(expression, state):
    if "conditions" in expression:
        results = [_condition(child, state) for child in expression["conditions"]]
        return all(results) if expression["operator"] == "AND" else any(results)
    left = _operand(expression if "aggregate" in expression else {"field": expression.get("field")}, state) if "left" not in expression else _operand({"field": expression["left"]}, state)
    right = _operand(expression["right"], state) if isinstance(expression.get("right"), dict) else decimal(expression.get("value"))
    return _compare(left, expression["operator"], right)


def _quantize(value, policy):
    quantum = Decimal(1).scaleb(-int(policy["precision"]))
    rounding = {"FLOOR": ROUND_FLOOR, "ROUND_HALF_EVEN": ROUND_HALF_EVEN}.get(policy["rounding"])
    return value.quantize(quantum, rounding=rounding)
