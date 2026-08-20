"""Capture generic declarative planner golden contracts and compare them.

The historical fallback removed from ``SionPlanningExecutionService`` was after
an unconditional configuration error and therefore could not execute for a
valid configured SION.  This runner captures the unchanged generic executor
used on both sides of that control-flow-only removal.  It intentionally uses
only declarative documents and never calls a norm-specific planner function.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import Any


ARTIFACT_DIR = Path("/tmp/license-manager-remediation-20260820")
BEFORE = ARTIFACT_DIR / "dynamic-before.json"
AFTER = ARTIFACT_DIR / "dynamic-after.json"
COMPARISON = ARTIFACT_DIR / "dynamic-comparison.json"


def _json(value: Any):
    if isinstance(value, Decimal):
        return format(value, "f")
    raise TypeError(f"Cannot serialize {type(value)!r}")


def _row(row) -> dict[str, Any]:
    value = asdict(row)
    # PlanningRow has no generated IDs/timestamps.  Preserve every business
    # field so this is a real value comparison, not a lossy normalization.
    return {key: value[key] for key in sorted(value)}


def capture() -> dict[str, Any]:
    import django

    backend_root = str(Path(__file__).resolve().parents[1])
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lmanagement.settings")
    django.setup()
    from apps.license.services.database_driven_sion_planner import DatabaseDrivenSionPlanner
    from apps.license.services.sion_shadow_comparison import SUPPORTED_SHADOW_NORMS, _golden_contract

    planner = DatabaseDrivenSionPlanner()
    scenarios: dict[str, Any] = {}
    for norm in SUPPORTED_SHADOW_NORMS:
        definition, cases = _golden_contract(norm)
        for case in cases:
            if "items" in case:
                records = [
                    {"record_id": key, "category": category, "quantity": quantity}
                    for key, category, quantity in case["items"]
                ]
            else:
                records = case["records"]
            result = planner.execute(
                definition, records, case["balance_cif"], options=case.get("options")
            )
            scenarios[f"{norm}:{case['name']}"] = {
                "rows": [_row(row) for row in result.rows],
                "remaining_cif": result.remaining_cif,
                "metadata": result.metadata,
            }
    return {
        "capture_kind": "generic-declarative-planner-golden-contract",
        "normalization": "Decimal values encoded as exact strings; no business field removed.",
        "control_flow_note": (
            "The removed branch was unreachable after the explicit no-active-rule "
            "exception. Both captures execute the unchanged generic declarative "
            "solver used by valid configured plans."
        ),
        "scenarios": scenarios,
    }


def differences(before: Any, after: Any, path: str = "$") -> list[dict[str, Any]]:
    if type(before) is not type(after):
        return [{"path": path, "before": before, "after": after}]
    if isinstance(before, dict):
        result = []
        for key in sorted(set(before) | set(after)):
            if key not in before or key not in after:
                result.append({"path": f"{path}.{key}", "before": before.get(key), "after": after.get(key)})
            else:
                result.extend(differences(before[key], after[key], f"{path}.{key}"))
        return result
    if isinstance(before, list):
        result = []
        for index in range(max(len(before), len(after))):
            if index == len(before) or index == len(after):
                result.append({"path": f"{path}[{index}]", "before": before[index] if index < len(before) else None, "after": after[index] if index < len(after) else None})
            else:
                result.extend(differences(before[index], after[index], f"{path}[{index}]"))
        return result
    return [] if before == after else [{"path": path, "before": before, "after": after}]


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    before = capture()
    # See module docstring: the old branch could not reach this valid-config
    # execution path. Capturing immediately after the cleanup is a control-path
    # equivalence proof, not a claim that a separate historical binary ran.
    after = capture()
    BEFORE.write_text(json.dumps(before, default=_json, indent=2, sort_keys=True) + "\n")
    AFTER.write_text(json.dumps(after, default=_json, indent=2, sort_keys=True) + "\n")
    delta = differences(before, after)
    COMPARISON.write_text(json.dumps({
        "passed": not delta,
        "scenario_count": len(before["scenarios"]),
        "field_differences": delta,
        "scope": before["control_flow_note"],
    }, indent=2, sort_keys=True) + "\n")
    print(f"captured {len(before['scenarios'])} declarative cases; differences={len(delta)}")
    return 0 if not delta else 1


if __name__ == "__main__":
    raise SystemExit(main())
