"""Read-only, exact shadow comparison for legacy and DB-driven SION plans.

The comparison deliberately treats row order as part of the contract and
converts numeric values through ``str`` into ``Decimal``.  It never persists a
plan, activates a profile, or changes migration configuration.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from decimal import Decimal
from typing import Any, Iterable

from apps.license.services.database_driven_sion_planner import DatabaseDrivenSionPlanner


DECIMAL_FIELDS = ("quantity", "unit_price", "value")
IDENTITY_FIELDS = ("record_id", "category", "output_key", "source_output")


def exact_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value in (None, ""):
        return Decimal("0")
    return Decimal(str(value))


def normalize_row(row: Any) -> dict[str, Any]:
    """Normalize either planner rows or legacy line dictionaries."""
    if is_dataclass(row):
        row = asdict(row)
    elif not isinstance(row, dict):
        row = vars(row)
    return {
        "record_id": str(row.get("record_id") or row.get("import_item") or row.get("import_item_id") or ""),
        "category": str(row.get("category") or ""),
        "output_key": str(row.get("output_key") or row.get("planning_item") or row.get("item_name") or ""),
        "source_output": row.get("source_output"),
        "quantity": exact_decimal(row.get("quantity", row.get("planned_quantity"))),
        "unit_price": exact_decimal(row.get("unit_price")),
        "value": exact_decimal(row.get("value", row.get("planned_cif_fc", row.get("planned_cif")))),
    }


@dataclass(frozen=True)
class ShadowDifference:
    dimension: str
    legacy: Any
    generic: Any
    row_index: int | None = None


@dataclass(frozen=True)
class ShadowCaseResult:
    name: str
    differences: tuple[ShadowDifference, ...]

    @property
    def passed(self) -> bool:
        return not self.differences


def compare_results(
    name: str,
    legacy_rows: Iterable[Any],
    legacy_remaining: Any,
    generic_rows: Iterable[Any],
    generic_remaining: Any,
    *,
    compare_identity: bool = True,
) -> ShadowCaseResult:
    """Compare every ordered row field and the exact remaining balance."""
    legacy = [normalize_row(row) for row in legacy_rows]
    generic = [normalize_row(row) for row in generic_rows]
    differences: list[ShadowDifference] = []
    if len(legacy) != len(generic):
        differences.append(ShadowDifference("row_count", len(legacy), len(generic)))
    for index in range(max(len(legacy), len(generic))):
        if index >= len(legacy):
            differences.append(ShadowDifference("unexpected_row", None, generic[index], index))
            continue
        if index >= len(generic):
            differences.append(ShadowDifference("missing_row", legacy[index], None, index))
            continue
        fields = (*IDENTITY_FIELDS, *DECIMAL_FIELDS) if compare_identity else DECIMAL_FIELDS
        for field in fields:
            if legacy[index][field] != generic[index][field]:
                differences.append(ShadowDifference(field, legacy[index][field], generic[index][field], index))
    legacy_balance = exact_decimal(legacy_remaining)
    generic_balance = exact_decimal(generic_remaining)
    if legacy_balance != generic_balance:
        differences.append(ShadowDifference("remaining_cif", legacy_balance, generic_balance))
    return ShadowCaseResult(name, tuple(differences))


def _golden_contract(norm: str) -> tuple[dict[str, Any], Iterable[dict[str, Any]]]:
    if norm in {"E1", "E5"}:
        from apps.license.services.sion_planner_config.e1_e5 import get_legacy_planner_config
        from apps.license.services.sion_planner_config.golden_e1_e5 import E1_GOLDEN_CASES, E5_GOLDEN_CASES
        return get_legacy_planner_config(norm), E1_GOLDEN_CASES if norm == "E1" else E5_GOLDEN_CASES
    from apps.license.services.sion_legacy_configurations import GOLDEN_CASES, LEGACY_PLANNER_CONFIGURATIONS
    return LEGACY_PLANNER_CONFIGURATIONS[norm], GOLDEN_CASES[norm]


def compare_golden_norm(norm: str, *, profile=None) -> tuple[ShadowCaseResult, ...]:
    """Run immutable legacy-oracle cases through the norm-neutral engine."""
    norm = norm.strip().upper()
    definition, cases = _golden_contract(norm)
    planner = DatabaseDrivenSionPlanner()
    compared = []
    for case in cases:
        if "items" in case:  # E1/E5 immutable captured contract
            records = [
                {"record_id": key, "category": category, "quantity": quantity}
                for key, category, quantity in case["items"]
            ]
            expected_rows = [{
                "record_id": key, "category": category, "output_key": output,
                "quantity": quantity, "unit_price": rate, "value": value,
            } for key, category, output, quantity, rate, value in case["lines"]]
            expected_remaining = case["remaining_cif"]
        else:
            records = case["records"]
            expected_rows = case["expected"]["rows"]
            expected_remaining = case["expected"]["remaining_cif"]
        if profile is None:
            actual = planner.execute(definition, records, case["balance_cif"], options=case.get("options"))
        else:
            actual = planner.execute_profile(
                profile, records, case["balance_cif"], options=case.get("options"),
                include_inactive_rules=True,
            )
        compared.append(compare_results(
            case["name"], expected_rows, expected_remaining, actual.rows, actual.remaining_cif,
            # The older E126/E132/A3627 captured fixtures predate identity
            # capture and contain only ordered output/value rows. Live legacy
            # adapters and E1/E5 contracts compare full row identity.
            compare_identity="items" in case,
        ))
    return tuple(compared)


SUPPORTED_SHADOW_NORMS = ("E1", "E5", "E126", "E132", "A3627")
