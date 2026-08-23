from decimal import Decimal
from types import SimpleNamespace

from apps.license.services.sion_planning_execution import (
    ResolvedPlannerConfiguration,
    SionPlanningExecutionService,
)


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
