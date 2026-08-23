from decimal import Decimal

from apps.license.services.item_pivot_item_summary import determine_planning_status, project_item_summary


def test_item_summary_is_populated_and_merges_only_same_canonical_item_and_sion():
    licenses = [
        {"license_id": 1, "items": {"10:E1": {"canonical_item_id": 10, "item_name": "PALM KERNEL OIL", "sion": "E1", "adjusted_total_qty": "388495", "allotted_qty": "388495", "debited_qty": 0, "available_qty": 0, "plan_qty": 0, "available_cif": 0, "planned_cif": 0}}},
        {"license_id": 2, "items": {"10:E1": {"canonical_item_id": 10, "item_name": "PALM KERNEL OIL", "sion": "E1", "adjusted_total_qty": 1, "allotted_qty": 0, "debited_qty": 0, "available_qty": 1, "plan_qty": 1, "available_cif": 5, "planned_cif": 5}, "10:E5": {"canonical_item_id": 10, "item_name": "PALM KERNEL OIL", "sion": "E5", "adjusted_total_qty": 2, "available_qty": 2, "plan_qty": 0, "available_cif": 4, "planned_cif": 0}}},
    ]
    result = project_item_summary(licenses)
    assert result["item_summary"]
    assert len(result["item_summary"]) == 2
    e1 = next(row for row in result["item_summary"] if row["sion"] == "E1")
    assert e1["license_count"] == 2
    assert e1["total_qty"] == "388496.000"
    assert e1["allotted_qty"] == "388495.000"
    assert e1["planned_qty"] == "1.000"
    assert result["item_summary_totals"]["planned_cif"] == "5.00"
    assert result["item_summary_totals"]["weighted_average_unit_price"] == "5.00"


def test_projection_does_not_duplicate_same_value_source_rows():
    row = {"canonical_item_id": 1, "item_name": "OLIVE OIL", "sion": "E1", "adjusted_total_qty": 100, "debited_qty": 10, "allotted_qty": 0, "available_qty": 90, "plan_qty": 90, "available_cif": 900, "planned_cif": 900}
    result = project_item_summary([{"license_id": 1, "items": {"1:E1": row}}])
    assert result["item_summary"][0]["boe_used_qty"] == "10.000"
    assert result["item_summary"][0]["actual_used_qty"] == "10.000"


def test_negative_positions_are_clamped_and_exceptions_are_positive():
    result = project_item_summary([{"license_id": 1, "items": {"1:E1": {
        "canonical_item_id": 1, "item_name": "OLIVE OIL", "sion": "E1",
        "adjusted_total_qty": 10, "debited_qty": 12, "allotted_qty": 0,
        "boe_used_cif": 120, "allotted_cif": 0, "has_item_cif_cap": True,
        "item_cif_cap": 100, "over_utilized_cif": 20, "over_planned_cif": 150,
        "available_qty": -2, "available_cif": -20, "plan_qty": 15, "planned_cif": 150,
    }}}])
    row = result["item_summary"][0]
    assert row["available_qty"] == row["balance_qty"] == "0.000"
    assert row["available_cif"] == row["balance_cif"] == "0.00"
    assert row["over_utilized_qty"] == "2.000"
    assert row["over_utilized_cif"] == "20.00"
    assert row["over_planned_qty"] == "15.000"
    assert row["over_planned_cif"] == "150.00"
    assert row["status"] == "over_utilized"
    for value in result["item_summary_totals"].values():
        if isinstance(value, str):
            assert Decimal(value) >= 0


def test_common_cif_item_has_no_item_cif_position_or_cif_exception():
    result = project_item_summary([{"license_id": 891, "items": {"181:E1": {
        "canonical_item_id": 181, "item_name": "FRUIT JUICE", "sion": "E1",
        "adjusted_total_qty": "613.180", "debited_qty": 0, "allotted_qty": 0,
        "available_qty": "613.180", "plan_qty": "613.180", "boe_used_cif": 30,
        "allotted_cif": 0, "planned_cif": 20, "available_cif": None,
        "has_item_cif_cap": False, "over_utilized_cif": "0.00", "over_planned_cif": "0.00",
    }}}])
    row = result["item_summary"][0]
    assert row["available_cif"] is None
    assert row["balance_cif"] is None
    assert row["over_utilized_cif"] == row["over_planned_cif"] == "0.00"
    assert row["exception_count"] == 0


def test_status_uses_decimal_zero_and_ten_unit_completion_tolerance():
    zero = Decimal("0.000")
    common = {"over_utilized_qty": zero, "over_utilized_cif": Decimal("0.00"), "over_planned_qty": zero, "over_planned_cif": Decimal("0.00")}
    assert determine_planning_status(planned_qty=Decimal("613.180"), available_qty=Decimal("613.180"), **common) == "planned"
    assert determine_planning_status(planned_qty=Decimal("2847.000"), available_qty=Decimal("2847.920"), **common) == "planned"
    assert determine_planning_status(planned_qty=Decimal("90.000"), available_qty=Decimal("100.000"), **common) == "planned"
    assert determine_planning_status(planned_qty=Decimal("89.999"), available_qty=Decimal("100.000"), **common) == "partially_planned"
    assert determine_planning_status(planned_qty=Decimal("101.000"), available_qty=Decimal("100.000"), **{**common, "over_planned_qty": Decimal("1.000")}) == "over_planned"


def test_item_summary_uses_rule_priority_and_split_member_order_not_name():
    def cell(item_id, name, priority=None, order=None):
        return {
            "canonical_item_id": item_id, "item_name": name, "sion": "E1",
            "adjusted_total_qty": 1, "available_qty": 1, "plan_qty": 1,
            "planning_priority": priority, "priority_item_order": order,
            "planning_rule_id": 9 if priority else None,
            "planning_rule_name": "Milk split" if priority == 2 else None,
            "planning_strategy": "split_by_unit_value" if priority == 2 else None,
            "priority_source": "active_sion_rule" if priority else "unmatched",
        }

    result = project_item_summary([{"license_id": 1, "items": {
        "z:E1": cell(1, "ZETA", 2, 1),
        "a:E1": cell(2, "ALPHA", 1, 0),
        "b:E1": cell(3, "BETA", 2, 0),
        "u:E1": cell(4, "UNMATCHED"),
    }}])

    assert [row["item_name"] for row in result["item_summary"]] == ["ALPHA", "BETA", "ZETA", "UNMATCHED"]
    assert [row["planning_priority"] for row in result["item_summary"]] == [1, 2, 2, None]
    assert result["item_summary"][1]["planning_rule_name"] == "Milk split"
