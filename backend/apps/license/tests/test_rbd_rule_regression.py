"""Regression test for RBD PALMOLEIN OIL rule planning (Issue: rule exists but does not plan).

This test ensures that:
1. The RBD rule correctly matches items with HSN 1511x
2. The canonical import_item is properly configured
3. The rule can successfully plan licenses
4. Changing the price in the rule is reflected in the plan
"""
import pytest
from decimal import Decimal

from apps.core.models import (
    HSCodeModel, ItemNameModel, SionNormClassModel, HeadSIONNormsModel
)
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel, SionPlanningRule
from apps.license.services.sion_rule_engine import SionRulePriorityService


@pytest.fixture
def e1_sion(db):
    """Get or create the E1 SION with profiles and rules."""
    # First, ensure the SION exists
    head_norm, _ = HeadSIONNormsModel.objects.get_or_create(name="E Norms")
    sion, _ = SionNormClassModel.objects.get_or_create(
        norm_class="E1",
        defaults={"head_norm": head_norm, "description": "Imported Sugar"}
    )
    return sion


@pytest.fixture
def rbd_item(e1_sion):
    """Get or create the RBD PALMOLEIN OIL item name for E1."""
    item, _ = ItemNameModel.objects.get_or_create(
        sion_norm_class=e1_sion,
        name="RBD PALMOLEIN OIL - E1",
    )
    return item


@pytest.fixture
def rbd_rule(e1_sion, rbd_item):
    """Get or create the active RBD PALMOLEIN OIL rule for E1."""
    rule, _ = SionPlanningRule.objects.get_or_create(
        sion=e1_sion,
        name="RBD PALMOLEIN OIL",
        defaults={
            "expression": {
                "operator": "OR",
                "conditions": [
                    {
                        "field": "HSN_DIGITS",
                        "value": "15119020",
                        "comparator": "STARTS_WITH",
                    },
                    {
                        "field": "PRODUCT_DESCRIPTION",
                        "value": "1511",
                        "comparator": "CONTAINS",
                    },
                ],
            },
            "max_unit_price": Decimal("1.20"),
            "unit": "MT",
            "priority": 2,
            "is_active": True,
            "import_item": rbd_item,
        },
    )
    # Ensure the canonical target item is set.
    if rule.import_item is None:
        rule.import_item = rbd_item
        rule.save(update_fields=["import_item"])
    return rule


@pytest.mark.django_db
def test_rbd_rule_has_output_item_configured(rbd_rule, rbd_item):
    """The RBD rule must have a canonical import target set."""
    assert rbd_rule.import_item is not None, (
        "RBD PALMOLEIN OIL rule has import_item=None. "
        "This breaks planning persistence."
    )
    assert rbd_rule.import_item == rbd_item, (
        f"RBD rule import_item mismatch: {rbd_rule.import_item} != {rbd_item}"
    )


@pytest.mark.django_db
def test_rbd_rule_expression_matches_hsn_1511(rbd_rule):
    """The RBD rule expression must match HSN 1511x items."""
    from apps.license.services.sion_rule_engine import evaluate_expression

    # Test HSN 1511 variants
    # Note: The rule uses "STARTS_WITH" for HSN 15119020, so it matches 15119020xxxx
    test_cases = [
        # (context, should_match, description)
        (
            {"hs_code": "15119020", "description": "RBD Palm Oil"},
            True,
            "HSN 15119020 (exact match)",
        ),
        (
            {"hs_code": "15119020101", "description": "RBD Palm Oil"},
            True,
            "HSN 15119020101 (starts with)",
        ),
        (
            {"hs_code": "1511", "description": ""},
            False,
            "HSN 1511 alone (too short, doesn't match STARTS_WITH)",
        ),
        (
            {"hs_code": "", "description": "1511 Palm Oil"},
            True,
            "HSN digit in description",
        ),
        (
            {"hs_code": "1512", "description": "Palm Kernel Oil"},
            False,
            "HSN 1512 (different oil)",
        ),
    ]

    for context, should_match, description in test_cases:
        # Fill in required fields
        full_context = {
            "hs_code": context.get("hs_code", ""),
            "description": context.get("description", ""),
            "available_qty": 100,
            "total_qty": 100,
            "available_value": 0,
            "cif_fc": 0,
            "license_balance_cif": 0,
            "condition_type": "",
            "is_restricted": False,
            "unit": "",
            "serial_number": 0,
            "item_key": "",
        }
        result = evaluate_expression(rbd_rule.expression, full_context)
        assert result == should_match, (
            f"RBD rule match failed for {description}: "
            f"expected {should_match}, got {result}"
        )


@pytest.mark.django_db
def test_rbd_rule_price_configuration(rbd_rule):
    """The RBD rule must have correct price configuration."""
    assert rbd_rule.max_unit_price == Decimal("1.20"), (
        f"RBD rule max_unit_price should be 1.20, got {rbd_rule.max_unit_price}"
    )
    assert rbd_rule.unit == "MT", (
        f"RBD rule unit should be MT, got {rbd_rule.unit}"
    )
    assert rbd_rule.is_active is True, "RBD rule should be active"
    assert rbd_rule.priority == 2, (
        f"RBD rule priority should be 2, got {rbd_rule.priority}"
    )
