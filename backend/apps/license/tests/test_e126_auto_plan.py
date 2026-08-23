"""E126 generic execution contracts (50/50 target rules are database data)."""
from decimal import Decimal

from apps.license.services.percentage_group_solver import reduce_high_rate_first
from apps.license.tests.planning_contract_support import compute, rule


def test_e126_targets_share_the_generic_cif_waterfall(monkeypatch):
    result = compute(monkeypatch, rules=[
        rule(key="pko", output="PKO", price="2", priority=1),
        rule(key="olive", output="OLIVE OIL", price="4", priority=2),
    ], records=[
        {"record_id": "pko", "item_key": "pko", "quantity": 50, "available_quantity": 50},
        {"record_id": "olive", "item_key": "olive", "quantity": 50, "available_quantity": 50},
    ], balance_cif="150")
    assert [(line.output_key, line.quantity, line.value) for line in result.rows] == [
        ("PKO", Decimal("50"), Decimal("100")), ("OLIVE OIL", Decimal("12.5"), Decimal("50")),
    ]


def test_e126_cif_reduction_moves_high_rate_effective_price_without_losing_quantity():
    result = reduce_high_rate_first(prior_sequence_cif=Decimal("0"), actual_balance_cif=Decimal("150"), members=[
        {"plan_id": 1, "unit_rate": Decimal("2"), "new_planned_qty": Decimal("50"), "new_planned_cif": Decimal("100"), "member_sequence": 1},
        {"plan_id": 2, "unit_rate": Decimal("4"), "new_planned_qty": Decimal("50"), "new_planned_cif": Decimal("200"), "member_sequence": 2},
    ])
    assert sum(row["new_planned_qty"] for row in result["members"]) == Decimal("100")
    assert sum(row["new_planned_cif"] for row in result["members"]) == Decimal("150")
