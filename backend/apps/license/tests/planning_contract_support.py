"""Shared current-contract helpers for generic SION planning tests.

The production planner is profile/rule driven.  These helpers deliberately
construct only persisted-contract-shaped rules; tests must never depend on a
norm-specific adapter that is no longer a production authority.
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from apps.license.services.sion_planning_execution import (
    ResolvedPlannerConfiguration,
    SionPlanningExecutionService,
)


def rule(*, key: str, output: str, price: str, priority: int = 1):
    return SimpleNamespace(
        stable_key=f"TEST:{key}",
        expression={"field": "item_key", "operator": "eq", "value": key},
        execution_output=output,
        max_unit_price=Decimal(price),
        min_unit_price=Decimal("0"),
        preferred_unit_price=Decimal(price),
        priority=priority,
        pk=priority,
    )


def configuration(*rules):
    return ResolvedPlannerConfiguration("TEST", tuple(rules), {})


def compute(monkeypatch, *, rules, records, balance_cif, force_plan=False):
    config = configuration(*rules)
    monkeypatch.setattr(
        SionPlanningExecutionService,
        "resolve_configuration",
        classmethod(lambda cls, sion: config),
    )
    return SionPlanningExecutionService._compute_license_generic(
        license_obj=object(), sion=object(), records=records,
        balance_cif=Decimal(str(balance_cif)), preview=True,
        force_plan=force_plan,
    )
