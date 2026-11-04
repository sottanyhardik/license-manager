"""
Regression tests for SION planning rule edits (PATCH/PUT on sion-planning-rules).

Defects covered:
1. ``update()`` copied only eight fields into the new version, so every edit reset
   ``percentage_constraint``, ``rule_type`` and ``cif_restriction_percentage``
   to model defaults.  Percentage and unit-value row CIF restrictions were also
   dropped when the request omitted the rows.
2. A partial update that omitted ``strategy`` skipped the strategy validation
   (sum-to-100, overlaps, same-SION) but still stored any rows it sent.
3. Reactivating a retired rule whose priority slot was reassigned raised an
   unhandled IntegrityError (HTTP 500) instead of a conflict.
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps.core.models import CompanyModel, HeadSIONNormsModel, ItemNameModel, SionNormClassModel
from apps.license.models import SionPlanningPercentageRow, SionPlanningRule

pytestmark = pytest.mark.django_db

RULE_URL = "/api/sion-planning-rules/{}/"


@pytest.fixture
def world(db):
    company = CompanyModel.objects.create(iec="RULEEDIT01", name="Rule Edit Co")
    head = HeadSIONNormsModel.objects.create(name="Rule Edit Head")
    sion = SionNormClassModel.objects.create(head_norm=head, norm_class="E126", is_active=True)
    pko = ItemNameModel.objects.create(name="PKO-EDIT", sion_norm_class=sion, is_active=True)
    olive = ItemNameModel.objects.create(name="OLIVE-EDIT", sion_norm_class=sion, is_active=True)
    user = get_user_model().objects.create_user(username="rule-edit-manager")
    user.groups.add(Group.objects.get_or_create(name="LICENSE_MANAGER")[0])
    client = APIClient()
    client.force_authenticate(user)
    return {"company": company, "sion": sion, "pko": pko, "olive": olive, "client": client}


def _standard_rule(world, **overrides):
    values = dict(
        sion=world["sion"], name="PKO standard", unit="kg", max_unit_price=Decimal("10.00"),
        priority=1, strategy="STANDARD", import_item=world["pko"],
        expression={"operator": "AND", "conditions": []}, is_active=True,
        percentage_constraint=Decimal("40.00"), rule_type="SPLIT_BY_PERCENTAGE",
        cif_restriction_percentage=Decimal("5.00"),
    )
    values.update(overrides)
    return SionPlanningRule.objects.create(**values)


def _split_rule(world):
    rule = SionPlanningRule.objects.create(
        sion=world["sion"], name="Split edit", unit="kg", max_unit_price=Decimal("10.00"),
        priority=2, strategy="SPLIT_BY_PERCENT",
        expression={"operator": "AND", "conditions": []}, is_active=True,
    )
    SionPlanningPercentageRow.objects.create(
        rule=rule, import_item=world["pko"], percentage=Decimal("50.00"),
        unit_price=Decimal("2.70"), cif_restriction_percentage=Decimal("3.00"), priority=1,
    )
    SionPlanningPercentageRow.objects.create(
        rule=rule, import_item=world["olive"], percentage=Decimal("50.00"),
        unit_price=Decimal("4.00"), cif_restriction_percentage=Decimal("3.00"), priority=2,
    )
    return rule


def _active_version(world, name):
    return SionPlanningRule.objects.get(sion=world["sion"], name=name, is_active=True)


class TestEditPreservesWritableFields:
    def test_name_only_patch_keeps_constraint_type_and_cif_restriction(self, world):
        rule = _standard_rule(world)

        response = world["client"].patch(RULE_URL.format(rule.pk), {"name": "Renamed"}, format="json")

        assert response.status_code == 200, response.data
        latest = _active_version(world, "Renamed")
        assert latest.percentage_constraint == Decimal("40.00")
        assert latest.rule_type == "SPLIT_BY_PERCENTAGE"
        assert latest.cif_restriction_percentage == Decimal("5.00")
        assert latest.version == rule.version + 1

    def test_omitted_percentage_rows_keep_their_cif_restriction(self, world):
        rule = _split_rule(world)

        response = world["client"].patch(RULE_URL.format(rule.pk), {"name": "Split renamed"}, format="json")

        assert response.status_code == 200, response.data
        latest = _active_version(world, "Split renamed")
        restrictions = sorted(
            row.cif_restriction_percentage for row in latest.percentage_rows.all()
        )
        assert restrictions == [Decimal("3.00"), Decimal("3.00")]

    def test_omitted_unit_value_rows_keep_their_cif_restriction(self, world):
        from apps.license.models import SionPlanningUnitValueRow

        rule = SionPlanningRule.objects.create(
            sion=world["sion"], name="Band edit", unit="kg", max_unit_price=Decimal("10.00"),
            priority=3, strategy="SPLIT_BY_UNIT_VALUE",
            expression={"operator": "AND", "conditions": []}, is_active=True,
        )
        SionPlanningUnitValueRow.objects.create(
            rule=rule, import_item=world["pko"], min_unit_price=Decimal("0.00"),
            max_unit_price=Decimal("5.00"), preferred_unit_price=Decimal("2.00"),
            cif_restriction_percentage=Decimal("10.00"), priority=1,
        )
        SionPlanningUnitValueRow.objects.create(
            rule=rule, import_item=world["olive"], min_unit_price=Decimal("5.00"),
            max_unit_price=Decimal("9.00"), preferred_unit_price=Decimal("7.00"),
            cif_restriction_percentage=Decimal("2.00"), priority=2,
        )

        response = world["client"].patch(RULE_URL.format(rule.pk), {"name": "Band renamed"}, format="json")

        assert response.status_code == 200, response.data
        latest = _active_version(world, "Band renamed")
        restrictions = sorted(row.cif_restriction_percentage for row in latest.unit_value_rows.all())
        assert restrictions == [Decimal("2.00"), Decimal("10.00")]


class TestPartialUpdateIsValidated:
    def test_partial_patch_with_unbalanced_percentage_rows_is_rejected(self, world):
        rule = _split_rule(world)

        response = world["client"].patch(
            RULE_URL.format(rule.pk),
            {"percentage_rows": [
                {"import_item": world["pko"].pk, "percentage": "60", "unit_price": "2.70"},
                {"import_item": world["olive"].pk, "percentage": "30", "unit_price": "4.00"},
            ]},
            format="json",
        )

        assert response.status_code == 400, response.data
        assert "percentage_rows" in response.data
        # Nothing was versioned: the original active row is still the only active one.
        assert SionPlanningRule.objects.filter(sion=world["sion"], name="Split edit", is_active=True).count() == 1

    def test_strategy_change_without_rows_is_rejected(self, world):
        rule = _standard_rule(world)

        response = world["client"].patch(
            RULE_URL.format(rule.pk), {"strategy": "SPLIT_BY_PERCENT"}, format="json",
        )

        assert response.status_code == 400, response.data

    def test_rename_of_valid_standard_rule_still_succeeds(self, world):
        """Guard against the effective-state validation rejecting a plain rename."""
        rule = _standard_rule(world)

        response = world["client"].patch(RULE_URL.format(rule.pk), {"name": "Still valid"}, format="json")

        assert response.status_code == 200, response.data


class TestReactivationConflict:
    def test_reactivating_rule_whose_priority_slot_was_reassigned_is_409(self, world):
        retired = _standard_rule(world, name="Retired rule", priority=1)
        client = world["client"]
        assert client.delete(RULE_URL.format(retired.pk)).status_code == 204
        # A different active rule now holds priority 1.
        _standard_rule(world, name="Replacement", priority=1, import_item=world["olive"])
        rules_before = SionPlanningRule.objects.filter(sion=world["sion"]).count()

        response = client.patch(RULE_URL.format(retired.pk), {"is_active": True}, format="json")

        assert response.status_code == 409, response.data
        assert response.data["code"] == "RULE_VERSION_CONFLICT"
        # The failed reactivation rolled back completely: no new version row.
        assert SionPlanningRule.objects.filter(sion=world["sion"]).count() == rules_before
