from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from apps.core.models import HSCodeModel, HeadSIONNormsModel, ItemNameModel, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel, SionPlanningRule

from apps.license.services.sion_planning_execution import (
    ResolvedPlannerConfiguration,
    SionPlanningExecutionService,
)


pytestmark = pytest.mark.django_db


def _configuration(price: str):
    rule = SimpleNamespace(
        expression={"field": "item_key", "operator": "eq", "value": "source-1"},
        execution_output="INPUT",
        max_unit_price=Decimal(price),
        # ``priority`` is a persisted SionPlanningRule contract and controls
        # the required deterministic CIF waterfall.  Omitting it made this
        # fixture impossible in production, where every rule has the field
        # (default 100 and an active-rule uniqueness constraint).
        priority=1,
        pk=1,
    )
    return ResolvedPlannerConfiguration("TEST", (rule,), {})


def test_force_plan_does_not_bypass_available_quantity_or_cif(monkeypatch):
    """Force All is a selection mode, not permission to over-plan."""
    monkeypatch.setattr(
        SionPlanningExecutionService,
        "resolve_configuration",
        classmethod(lambda cls, sion: _configuration("10")),
    )

    result = SionPlanningExecutionService._compute_license_generic(
        license_obj=object(),
        sion=object(),
        records=[{
            "record_id": "source-1",
            "item_key": "source-1",
            "quantity": Decimal("100"),
            "available_quantity": Decimal("7"),
        }],
        balance_cif=Decimal("50"),
        preview=True,
        force_plan=True,
    )

    assert len(result.rows) == 1
    assert result.rows[0].quantity == Decimal("5")
    assert result.rows[0].value == Decimal("50")
    assert result.remaining_cif == Decimal("0")


def test_zero_cif_budget_creates_no_positive_value_plan(monkeypatch):
    monkeypatch.setattr(
        SionPlanningExecutionService,
        "resolve_configuration",
        classmethod(lambda cls, sion: _configuration("10")),
    )

    result = SionPlanningExecutionService._compute_license_generic(
        license_obj=object(), sion=object(),
        records=[{"record_id": "source-1", "item_key": "source-1", "quantity": 10, "available_quantity": 10}],
        balance_cif=Decimal("0"), preview=True, force_plan=True,
    )

    assert result.rows == []
    assert result.remaining_cif == Decimal("0")


@pytest.mark.parametrize("override", [None, False])
def test_null_and_false_skip_the_individual_item_snapshot(monkeypatch, override):
    """Legacy modes must not enter a second availability approximation."""
    head = HeadSIONNormsModel.objects.create(name=f"Legacy {override}")
    sion = SionNormClassModel.objects.create(head_norm=head, norm_class=f"L{int(override or 0)}{head.pk}")
    licence = LicenseDetailsModel.objects.create(
        license_number=f"LEGACY-CIF-{head.pk}", individual_item_cif_override=override,
    )
    SionPlanningRule.objects.create(
        sion=sion, name="legacy", expression={}, max_unit_price=Decimal("1.00"), priority=1,
    )
    LicenseImportItemsModel.objects.create(
        license=licence, quantity=Decimal("1.000"), available_quantity=Decimal("1.000"),
    )
    captured = []

    def compute(cls, *_args, **kwargs):
        captured.append(kwargs.get("individual_item_cif_ceiling"))
        return [], Decimal("0"), {"planning_cif_ceiling": Decimal("0"), "remaining_waterfall_cif": Decimal("0")}

    monkeypatch.setattr(
        SionPlanningExecutionService, "_eligible_licenses",
        classmethod(lambda cls, *_args, **_kwargs: ([licence], {licence.pk: Decimal("10.00")})),
    )
    monkeypatch.setattr(SionPlanningExecutionService, "_compute_license", classmethod(compute))
    with patch("apps.license.services.balance_snapshot.get_snapshot_bulk") as snapshot:
        SionPlanningExecutionService.plan_sion(sion, license_ids=[licence.pk], persist=False, mode="ALL", force_plan=True)
    snapshot.assert_not_called()
    assert captured == [None]


def test_individual_item_snapshot_is_keyed_by_import_row_not_shared_hsn(monkeypatch):
    """Two rows sharing HSN retain their own live CIF ceilings.

    This is the regression shape behind licence 430: a high-CIF sibling must
    not make the Dietary Fibre row (CIF 1.00) appear fundable for 10k+.
    """
    head = HeadSIONNormsModel.objects.create(name="Same HSN source identity")
    sion = SionNormClassModel.objects.create(head_norm=head, norm_class=f"I{head.pk}")
    licence = LicenseDetailsModel.objects.create(
        license_number=f"SOURCE-PK-CIF-{head.pk}", individual_item_cif_override=True,
    )
    SionPlanningRule.objects.create(
        sion=sion, name="source identity", expression={}, max_unit_price=Decimal("1.00"), priority=1,
    )
    hsn = HSCodeModel.objects.create(hs_code="08023100", product_description="Shared HSN")
    dietary_fibre = LicenseImportItemsModel.objects.create(
        license=licence, serial_number=1, hs_code=hsn, description="Dietary Fibre",
        quantity=Decimal("4080.880"), available_quantity=Decimal("4080.880"),
        cif_fc=Decimal("1.00"),
    )
    sibling = LicenseImportItemsModel.objects.create(
        license=licence, serial_number=2, hs_code=hsn, description="Different physical row",
        quantity=Decimal("2.000"), available_quantity=Decimal("2.000"),
        cif_fc=Decimal("10127.53"),
    )
    captured = []

    def compute(cls, *_args, **kwargs):
        captured.append(kwargs["individual_item_cif_ceiling"])
        return [], Decimal("0"), {"planning_cif_ceiling": Decimal("0"), "remaining_waterfall_cif": Decimal("0")}

    monkeypatch.setattr(
        SionPlanningExecutionService, "_eligible_licenses",
        classmethod(lambda cls, *_args, **_kwargs: ([licence], {licence.pk: Decimal("10128.53")})),
    )
    monkeypatch.setattr(SionPlanningExecutionService, "_compute_license", classmethod(compute))
    SionPlanningExecutionService.plan_sion(
        sion, license_ids=[licence.pk], persist=False, mode="ALL", force_plan=True,
    )

    assert captured == [{
        dietary_fibre.pk: Decimal("1.00"),
        sibling.pk: Decimal("10127.53"),
    }]


def test_same_hsn_sources_cannot_borrow_individual_cif_in_standard_planning():
    """A HSN-matched rule emits and caps each physical source row separately."""
    head = HeadSIONNormsModel.objects.create(name="Same HSN standard planning")
    sion = SionNormClassModel.objects.create(head_norm=head, norm_class=f"P{head.pk}")
    licence = LicenseDetailsModel.objects.create(
        license_number=f"SOURCE-PK-PLAN-{head.pk}", individual_item_cif_override=True,
    )
    hsn = HSCodeModel.objects.create(hs_code="08023100", product_description="Shared HSN planning")
    dietary_fibre = LicenseImportItemsModel.objects.create(
        license=licence, serial_number=1, hs_code=hsn, description="Dietary Fibre",
        quantity=Decimal("4080.880"), available_quantity=Decimal("4080.880"), cif_fc=Decimal("1.00"),
    )
    sibling = LicenseImportItemsModel.objects.create(
        license=licence, serial_number=2, hs_code=hsn, description="Sibling source",
        quantity=Decimal("2.000"), available_quantity=Decimal("2.000"), cif_fc=Decimal("10127.53"),
    )
    target = ItemNameModel.objects.create(name=f"Auto plan target {head.pk}")
    SionPlanningRule.objects.create(
        sion=sion, name="shared HSN", import_item=target, priority=1,
        expression={"field": "HSN", "comparator": "CONTAINS", "value": "08023100"},
        max_unit_price=Decimal("1.00"),
    )

    lines, _remaining, _metadata = SionPlanningExecutionService._compute_license(
        licence, sion, preview=True, force_plan=True,
        operational_balance_cif=Decimal("10128.53"),
        individual_item_cif_ceiling={
            dietary_fibre.pk: Decimal("1.00"), sibling.pk: Decimal("10127.53"),
        },
    )

    by_source = {line["import_item"]: line for line in lines}
    assert by_source[dietary_fibre.pk]["planned_cif"] == Decimal("1.00")
    assert by_source[dietary_fibre.pk]["planned_quantity"] == Decimal("1.000")
    assert by_source[sibling.pk]["planned_cif"] == Decimal("2.00")
    assert all(line["planned_cif"] <= Decimal("1.00") for line in [by_source[dietary_fibre.pk]])
