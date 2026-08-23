from decimal import Decimal

import pytest
from django.core.management import call_command

from apps.license.services.sion_shadow_comparison import (
    SUPPORTED_SHADOW_NORMS,
    compare_golden_norm,
    compare_results,
)


def test_comparison_detects_order_identity_and_exact_decimal_differences():
    legacy = [
        {"record_id": "1", "output_key": "A", "planned_quantity": "1.00", "unit_price": "2", "planned_cif_fc": "2"},
        {"record_id": "2", "output_key": "B", "planned_quantity": "3", "unit_price": "4", "planned_cif_fc": "12"},
    ]
    generic = [
        {"record_id": "2", "output_key": "B", "quantity": "3", "unit_price": "4", "value": "12"},
        {"record_id": "1", "output_key": "A", "quantity": "1.01", "unit_price": "2", "value": "2.02"},
    ]
    result = compare_results("case", legacy, "0.01", generic, Decimal("0.02"))
    assert not result.passed
    assert {difference.dimension for difference in result.differences} >= {
        "record_id", "output_key", "quantity", "value", "remaining_cif",
    }


@pytest.mark.parametrize("norm", SUPPORTED_SHADOW_NORMS)
def test_each_golden_planner_matches_exactly(norm):
    assert all(result.passed for result in compare_golden_norm(norm))


def test_management_commands_report_pass(capsys):
    call_command("compare_sion_planner", sion="E1", dataset="golden")
    call_command("compare_all_sion_planners")
    output = capsys.readouterr().out
    assert "E1: source=audited cases=" in output
    assert "A3627" in output
    assert "All SION planner golden comparisons passed exactly (source=audited)." in output
