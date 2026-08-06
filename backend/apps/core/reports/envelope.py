"""
Display Dataset envelope convention — Phase 2A of the export-consistency
initiative (see the "Export Consistency Policy" work that produced commit
`4438130`).

This is deliberately NOT a base class exporters inherit from. It is a
naming/shape convention plus one debug/test-only validation helper, matching
the plain-dict pattern already proven by
`apps.license.services.license_balance_ledger_builder.LicenseBalanceLedgerBuilder.build()`
— the one report in this app already confirmed to have "one builder function,
JSON view + PDF exporter + Excel exporter all consume its exact output, no
exporter recalculates anything."

Convention (all keys optional except `summary`):

    {
        "summary": dict,        # scalar totals/counts — REQUIRED. Rendered
                                 # as the Metric/Value table in Excel and PDF.
        "<rows>": list[dict],   # the report's own existing plural key name
                                 # (e.g. "licenses", "items") — NOT forcibly
                                 # renamed to a generic "rows" key. Every
                                 # report already has its own name for this;
                                 # changing it would be a breaking API change
                                 # for zero benefit.
        "meta": dict | None,    # generated_at / filters_applied / report_name
                                 # — for filename/header stamping, see
                                 # `export_naming.py`.
    }

`validate_envelope` is a cheap regression guard for tests (and optionally a
DEBUG-gated call site in a view, never in the hot request path for anyone
else) — it is NOT validation middleware and must never raise in production
for a real user request.
"""
from typing import Any, Dict, Iterable


def validate_envelope(
    data: Dict[str, Any],
    row_key: str,
    required_summary_keys: Iterable[str] = frozenset(),
) -> None:
    """Assert `data` matches the Display Dataset envelope convention.

    `row_key` is the report's own existing plural key (e.g. "licenses",
    "items") — this function does not impose a single universal name.
    """
    assert isinstance(data, dict), f"Display Dataset must be a dict, got {type(data)!r}"
    assert "summary" in data, "Display Dataset must have a 'summary' key"
    assert isinstance(data["summary"], dict), "'summary' must be a dict"
    assert row_key in data, f"Display Dataset must have a '{row_key}' key"

    missing = set(required_summary_keys) - set(data["summary"].keys())
    assert not missing, f"summary missing required keys: {sorted(missing)}"
