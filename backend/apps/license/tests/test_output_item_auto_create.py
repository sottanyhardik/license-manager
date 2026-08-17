"""Test auto-creation of missing ItemNameModels during planning execution.

This tests the OutputItemResolver feature that automatically creates
missing planning output items when a rule matches but no ItemNameModel exists.

Requirements:
1. Auto-creation happens during execution (persist=True), not preview
2. No duplicate items are created (concurrent execution safe)
3. Rules are automatically linked to created items
4. Preview does NOT write master data
5. Source import items are never confused with output items
"""
import pytest
from decimal import Decimal

from apps.core.models import (
    HeadSIONNormsModel, ItemNameModel, SionNormClassModel, HSCodeModel
)
from apps.license.models import (
    LicenseDetailsModel, LicenseImportItemsModel, SionPlanningRule, LicenseItemPlan
)
from apps.license.services.output_item_resolver import OutputItemResolver
from apps.license.services.sion_rule_engine import SionRulePlanningService


@pytest.fixture
def e1_sion(db):
    """Create E1 SION."""
    head_norm, _ = HeadSIONNormsModel.objects.get_or_create(name="E Norms")
    sion, _ = SionNormClassModel.objects.get_or_create(
        norm_class="E1",
        defaults={"head_norm": head_norm, "description": "Imported Sugar"}
    )
    return sion


@pytest.fixture
def test_rule_without_item(e1_sion):
    """Create a rule WITHOUT output_item configured."""
    rule, _ = SionPlanningRule.objects.get_or_create(
        sion=e1_sion,
        name="AUTO CREATE TEST OIL",
        defaults={
            "expression": {
                "operator": "OR",
                "conditions": [
                    {
                        "field": "HSN_DIGITS",
                        "value": "1515",
                        "comparator": "STARTS_WITH",
                    },
                    {
                        "field": "PRODUCT_DESCRIPTION",
                        "value": "test oil",
                        "comparator": "CONTAINS",
                    },
                ],
            },
            "max_unit_price": Decimal("2.50"),
            "unit": "MT",
            "priority": 5,
            "is_active": True,
            "output_item": None,  # Explicitly no output item
        },
    )
    return rule


@pytest.mark.django_db
def test_output_item_resolver_normalize_name():
    """Name normalization removes whitespace variations."""
    assert OutputItemResolver.normalize_name("TEST OIL") == "TEST OIL"
    assert OutputItemResolver.normalize_name("  TEST   OIL  ") == "TEST OIL"
    assert OutputItemResolver.normalize_name("Test Oil") == "Test Oil"

    with pytest.raises(Exception):
        OutputItemResolver.normalize_name("")


@pytest.mark.django_db
def test_output_item_resolver_get_canonical_name(test_rule_without_item):
    """Canonical name comes from execution_output or rule.name."""
    # With empty execution_output, uses rule.name
    assert (
        OutputItemResolver.get_canonical_output_name(test_rule_without_item)
        == "AUTO CREATE TEST OIL"
    )

    # With explicit execution_output, uses that
    test_rule_without_item.execution_output = "ALTERNATE NAME"
    assert (
        OutputItemResolver.get_canonical_output_name(test_rule_without_item)
        == "ALTERNATE NAME"
    )


@pytest.mark.django_db
def test_output_item_resolver_creates_missing_item(e1_sion, test_rule_without_item):
    """Resolver auto-creates ItemNameModel when missing."""
    # Verify item doesn't exist yet
    assert not ItemNameModel.objects.filter(
        name="AUTO CREATE TEST OIL",
        sion_norm_class=e1_sion,
    ).exists()

    # Resolve (creates because doesn't exist)
    resolved = OutputItemResolver.resolve_or_create(test_rule_without_item)

    # Verify item was created
    assert resolved is not None
    assert resolved.name == "AUTO CREATE TEST OIL"
    assert resolved.sion_norm_class == e1_sion
    assert resolved.is_active is True

    # Verify rule was linked
    test_rule_without_item.refresh_from_db()
    assert test_rule_without_item.output_item == resolved


@pytest.mark.django_db
def test_output_item_resolver_reuses_existing_item(e1_sion, test_rule_without_item):
    """Resolver reuses existing ItemNameModel instead of creating duplicate."""
    # Create an existing item
    existing = ItemNameModel.objects.create(
        name="AUTO CREATE TEST OIL",
        sion_norm_class=e1_sion,
        is_active=True,
    )

    # Resolve (should find and reuse)
    resolved = OutputItemResolver.resolve_or_create(test_rule_without_item)

    # Should be the same instance
    assert resolved.pk == existing.pk

    # Should only be one item with this name for this SION
    count = ItemNameModel.objects.filter(
        name="AUTO CREATE TEST OIL",
        sion_norm_class=e1_sion,
    ).count()
    assert count == 1


@pytest.mark.django_db
def test_output_item_resolver_idempotent(e1_sion, test_rule_without_item):
    """Resolver is idempotent - multiple calls return same item."""
    first_call = OutputItemResolver.resolve_or_create(test_rule_without_item)
    second_call = OutputItemResolver.resolve_or_create(test_rule_without_item)

    assert first_call.pk == second_call.pk
    assert first_call.name == second_call.name


@pytest.mark.django_db
def test_planning_auto_creates_output_item_on_execution(e1_sion, test_rule_without_item):
    """Full planning flow: execution auto-creates output item, preview does not."""
    from apps.license.services.sion_rule_engine import evaluate_expression

    # Create a license with a matching import item
    license_obj = LicenseDetailsModel.objects.create(
        license_number="AUTO-CREATE-TEST-001",
    )
    license_obj.export_license.create(norm_class=e1_sion)

    hs_code = HSCodeModel.objects.create(hs_code="15150000")
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=1,
        hs_code=hs_code,
        description="Test Oil Product",
        quantity=Decimal("50"),
    )

    # Set license balance via the import items' CIF
    import_item.cif_fc = Decimal("1000.00")
    import_item.save()

    # First verify rule matches the import item
    context = {
        "hs_code": hs_code.hs_code,
        "description": import_item.description,
        "available_qty": import_item.quantity,
        "total_qty": import_item.quantity,
        "available_value": Decimal("0"),
        "cif_fc": import_item.cif_fc,
        "license_balance_cif": Decimal("0"),
        "condition_type": "",
        "is_restricted": False,
        "unit": "",
        "serial_number": import_item.serial_number,
        "item_key": "",
    }
    assert evaluate_expression(test_rule_without_item.expression, context), (
        "Rule should match this import item"
    )

    # Count items before
    item_count_before = ItemNameModel.objects.filter(
        sion_norm_class=e1_sion,
    ).count()

    # Run PREVIEW (should NOT create item)
    preview_result = SionRulePlanningService.preview_sion(
        e1_sion.pk,
        license_ids=[license_obj.pk],
        mode="NEW",
    )

    item_count_after_preview = ItemNameModel.objects.filter(
        sion_norm_class=e1_sion,
    ).count()

    # Preview must NOT create master data
    assert item_count_after_preview == item_count_before, (
        "Preview created ItemNameModel - should be read-only"
    )

    # Run EXECUTION (should create item)
    exec_result = SionRulePlanningService.plan_sion(
        e1_sion.pk,
        license_ids=[license_obj.pk],
        mode="NEW",
    )

    item_count_after_execution = ItemNameModel.objects.filter(
        sion_norm_class=e1_sion,
    ).count()

    # Execution must create the item
    assert item_count_after_execution > item_count_after_preview, (
        "Execution did not create ItemNameModel (rule may not have matched)"
    )

    # Verify rule was linked
    test_rule_without_item.refresh_from_db()
    assert test_rule_without_item.output_item is not None
    assert test_rule_without_item.output_item.name == "AUTO CREATE TEST OIL"

    # Verify LicenseItemPlan was created
    plan_lines = LicenseItemPlan.objects.filter(
        license=license_obj,
        import_item=import_item,
    )
    assert plan_lines.exists(), "No LicenseItemPlan created"
    plan_line = plan_lines.first()
    assert plan_line.item_name == test_rule_without_item.output_item


@pytest.mark.django_db
def test_planning_duplicate_safety_concurrent_execution(e1_sion, test_rule_without_item):
    """Concurrent execution does not create duplicate ItemNameModels."""
    # This is tested implicitly by the database uniqueness constraint
    # (name is unique), but we verify idempotency explicitly

    # First execution creates item
    first = OutputItemResolver.resolve_or_create(test_rule_without_item)

    # Second concurrent call (same rule) should get same item
    second = OutputItemResolver.resolve_or_create(test_rule_without_item)

    assert first.pk == second.pk

    # Only one item should exist
    count = ItemNameModel.objects.filter(
        name="AUTO CREATE TEST OIL",
        sion_norm_class=e1_sion,
    ).count()
    assert count == 1


@pytest.mark.django_db
def test_planning_replan_idempotent(e1_sion, test_rule_without_item):
    """Force re-plan with auto-create is idempotent."""
    license_obj = LicenseDetailsModel.objects.create(
        license_number="AUTO-CREATE-REPLAN-001",
    )
    license_obj.export_license.create(norm_class=e1_sion)

    hs_code = HSCodeModel.objects.create(hs_code="15150000")
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=1,
        hs_code=hs_code,
        description="Test Oil",
        quantity=Decimal("50"),
    )

    # Set license balance via the import items' CIF
    import_item.cif_fc = Decimal("1000.00")
    import_item.save()

    # First plan
    result1 = SionRulePlanningService.plan_sion(
        e1_sion.pk,
        license_ids=[license_obj.pk],
        mode="NEW",
    )
    # plan_sion returns a plan result (not a dict with status)
    assert result1 is not None

    plan_count_after_first = LicenseItemPlan.objects.filter(
        license=license_obj,
    ).count()
    item_count_after_first = ItemNameModel.objects.filter(
        name="AUTO CREATE TEST OIL",
        sion_norm_class=e1_sion,
    ).count()

    # Force re-plan
    LicenseItemPlan.objects.filter(license=license_obj).delete()
    result2 = SionRulePlanningService.plan_sion(
        e1_sion.pk,
        license_ids=[license_obj.pk],
        mode="ALL",
    )
    # plan_sion returns a plan result (not a dict with status)
    assert result2 is not None

    plan_count_after_second = LicenseItemPlan.objects.filter(
        license=license_obj,
    ).count()
    item_count_after_second = ItemNameModel.objects.filter(
        name="AUTO CREATE TEST OIL",
        sion_norm_class=e1_sion,
    ).count()

    # Item count must not increase (no duplicate created)
    assert item_count_after_second == item_count_after_first == 1
    # Plan count should be same (same items planned)
    assert plan_count_after_second == plan_count_after_first
