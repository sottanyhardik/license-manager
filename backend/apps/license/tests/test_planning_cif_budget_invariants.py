"""Planner CIF budget invariants (2026-11-18): Auto Plan never plans more CIF
than the licence has available.

Characterization tests — they pin CURRENT engine behaviour across many
deterministic scenarios; no planner code is changed. For every registry norm
(E126 / E132 / A3627) and the E1 / E5 profiles, and for the generic DB-rule
waterfall:

* Σ planned value ≤ available balance CIF (to the cent, after rounding);
* remaining CIF is never negative and equals balance − Σ value;
* an exhausted budget plans nothing;
* repeated execution on the same input is identical (no duplicate debits).
"""
from __future__ import annotations

import random
from decimal import Decimal

import pytest

from apps.license.services.database_driven_sion_planner import DatabaseDrivenSionPlanner
from apps.license.services.sion_legacy_configurations import GOLDEN_CASES, LEGACY_PLANNER_CONFIGURATIONS
from apps.license.services.sion_planner_config.e1_e5 import E1_PROFILE, E5_PROFILE
from apps.license.services.sion_planner_config.golden_e1_e5 import E1_GOLDEN_CASES, E5_GOLDEN_CASES
from apps.license.tests.planning_contract_support import compute, rule

CENT = Decimal("0.01")
DEFINITIONS = {**LEGACY_PLANNER_CONFIGURATIONS, "E1": E1_PROFILE, "E5": E5_PROFILE}
GOLDEN = {**GOLDEN_CASES, "E1": E1_GOLDEN_CASES, "E5": E5_GOLDEN_CASES}
BALANCES = ["0", "0.01", "1", "37.37", "150", "399.99", "1000", "12345.67", "250000"]


def _record_pool(norm: str) -> list[dict]:
    """Every record shape the norm's own golden cases exercise (real classifications)."""
    pool = []
    for case in GOLDEN[norm]:
        if "records" in case:  # registry golden shape
            pool.extend({k: v for k, v in record.items() if k != "record_id"} for record in case["records"])
        else:  # E1 / E5 golden shape: (key, category, quantity)
            pool.extend({"category": category} for _key, category, _qty in case["items"])
    return pool


def _scenario(norm: str, seed: int) -> list[dict]:
    rng = random.Random(f"{norm}:{seed}")
    pool = _record_pool(norm)
    records = []
    for index in range(rng.randint(1, 6)):
        base = dict(rng.choice(pool))
        quantity = Decimal(rng.choice(["0.001", "1", "3.333", "10", "99.995", "1000", "25000.5"]))
        base["quantity"] = str(quantity)
        if "available_quantity" in base:
            base["available_quantity"] = str(quantity)
        base["record_id"] = f"r{index}"
        records.append(base)
    return records


def _assert_within_budget(result, balance: Decimal, label: str):
    planned = sum((Decimal(row.value) for row in result.rows), Decimal("0"))
    assert planned <= balance + CENT, f"{label}: planned {planned} exceeds available {balance}"
    assert result.remaining_cif >= -CENT, f"{label}: negative remaining {result.remaining_cif}"
    assert abs((balance - planned) - result.remaining_cif) <= CENT, f"{label}: remaining {result.remaining_cif} != {balance} - {planned}"
    for row in result.rows:
        assert Decimal(row.quantity) >= 0 and Decimal(row.value) >= 0, f"{label}: negative row {row}"


@pytest.mark.parametrize("norm", sorted(DEFINITIONS))
def test_registry_and_profile_plans_never_exceed_available_cif(norm):
    planner = DatabaseDrivenSionPlanner()
    definition = DEFINITIONS[norm]
    checked = 0
    for seed in range(40):
        records = _scenario(norm, seed)
        for balance in BALANCES:
            label = f"{norm} seed={seed} balance={balance}"
            result = planner.execute(definition, records, balance)
            _assert_within_budget(result, Decimal(balance), label)
            checked += 1
    assert checked == 40 * len(BALANCES)


@pytest.mark.parametrize("norm", sorted(DEFINITIONS))
def test_exhausted_budget_plans_no_cif(norm):
    planner = DatabaseDrivenSionPlanner()
    for seed in range(10):
        result = planner.execute(DEFINITIONS[norm], _scenario(norm, seed), "0")
        assert sum((Decimal(r.value) for r in result.rows), Decimal("0")) == 0
        assert result.remaining_cif == 0


@pytest.mark.parametrize("norm", sorted(DEFINITIONS))
def test_repeated_execution_is_identical(norm):
    planner = DatabaseDrivenSionPlanner()
    records = _scenario(norm, 7)
    first = planner.execute(DEFINITIONS[norm], records, "1000")
    second = planner.execute(DEFINITIONS[norm], records, "1000")
    assert [(r.output_key, r.quantity, r.value) for r in first.rows] == [(r.output_key, r.quantity, r.value) for r in second.rows]
    assert first.remaining_cif == second.remaining_cif


def test_e126_split_stays_inside_budget_at_every_boundary():
    """PKO/Olive split source: the combined split plan never exceeds the budget,
    including the exact-consumption and one-cent-short boundaries."""
    planner = DatabaseDrivenSionPlanner()
    records = [{"record_id": "split", "hs_code": "15132900", "description": "olive 1509 blend", "quantity": "100"}]
    full = planner.execute(LEGACY_PLANNER_CONFIGURATIONS["E126"], records, "1000000")
    full_cost = sum((Decimal(r.value) for r in full.rows), Decimal("0"))
    for balance in (full_cost, full_cost - CENT, full_cost / 2, Decimal("0.01")):
        result = planner.execute(LEGACY_PLANNER_CONFIGURATIONS["E126"], records, str(balance))
        _assert_within_budget(result, balance, f"E126 split balance={balance}")
        assert {r.output_key for r in result.rows} <= {"PKO", "OLIVE"}


@pytest.mark.parametrize("balance", ["0", "0.01", "99.99", "100", "150", "299.99", "300", "10000"])
def test_generic_db_rule_waterfall_shares_one_budget(monkeypatch, balance):
    """Multiple DB-rule items competing for one licence budget never exceed it."""
    result = compute(monkeypatch, rules=[
        rule(key="pko", output="PKO", price="2", priority=1),
        rule(key="olive", output="OLIVE OIL", price="4", priority=2),
    ], records=[
        {"record_id": "pko", "item_key": "pko", "quantity": 50, "available_quantity": 50},
        {"record_id": "olive", "item_key": "olive", "quantity": 50, "available_quantity": 50},
    ], balance_cif=balance)
    planned = sum((Decimal(line.value) for line in result.rows), Decimal("0"))
    assert planned <= Decimal(balance) + CENT
    assert result.remaining_cif >= -CENT


@pytest.mark.parametrize("balance,olive_rate", [("200", Decimal("2.20")), ("340", Decimal("5.00")), ("400", Decimal("5.00"))])
def test_e126_fixed_split_keeps_50_50_quantity_when_cif_is_short(balance, olive_rate):
    """Owner decision 2026-11-18: the split quantity never moves between PKO and Olive.
    When CIF is short the existing REDUCE_EFFECTIVE_RATE lowers the later rate; when
    CIF is spare it stays unplanned."""
    planner = DatabaseDrivenSionPlanner()
    records = [{"record_id": "split", "hs_code": "15132900", "description": "olive 1509 blend", "quantity": "100"}]
    result = planner.execute(LEGACY_PLANNER_CONFIGURATIONS["E126"], records, balance)
    rows = {row.output_key: row for row in result.rows}
    assert Decimal(rows["PKO"].quantity) == Decimal(rows["OLIVE"].quantity) == Decimal("50")
    assert Decimal(rows["PKO"].unit_price) == Decimal("1.80")
    assert Decimal(rows["OLIVE"].unit_price) == olive_rate
    _assert_within_budget(result, Decimal(balance), f"E126 fixed split balance={balance}")
