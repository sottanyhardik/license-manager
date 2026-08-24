from decimal import Decimal
from types import SimpleNamespace

from apps.license.services.effective_cif_mode import (
    INDIVIDUAL_ITEM,
    LEGACY,
    effective_source_row_cif_available,
    project_effective_item_cif,
    resolve_effective_cif_mode,
)


def test_null_and_false_select_the_identical_legacy_mode():
    assert resolve_effective_cif_mode(SimpleNamespace(individual_item_cif_override=None)) == LEGACY
    assert resolve_effective_cif_mode(SimpleNamespace(individual_item_cif_override=False)) == LEGACY


def test_true_selects_the_individual_item_mode_only():
    assert resolve_effective_cif_mode(SimpleNamespace(individual_item_cif_override=True)) == INDIVIDUAL_ITEM


def test_truthy_non_boolean_values_remain_legacy_mode():
    """Only persisted literal True is allowed to select row-level CIF."""
    for raw_override in ("true", "1", 1, Decimal("1"), [], {}):
        assert resolve_effective_cif_mode(
            SimpleNamespace(individual_item_cif_override=raw_override)
        ) == LEGACY


def test_projection_preserves_the_supplied_legacy_value_for_null_and_false():
    """The mode selector must not substitute a different balance formula.

    Candidate reads deliberately pass the batched condition-pool balance and
    mutation callers pass their established live calculation.  Both NULL and
    False therefore retain that caller-owned shared-pool expression.
    """
    item = SimpleNamespace(balance_cif_fc=Decimal("11.25"))
    for raw_override in (None, False):
        licence = SimpleNamespace(individual_item_cif_override=raw_override, get_balance_cif=Decimal("47.50"))
        projection = project_effective_item_cif(
            licence=licence,
            item=item,
            legacy_row_balance=lambda: Decimal("-99.00"),
        )
        assert projection.effective_mode == LEGACY
        assert projection.effective_row_balance == Decimal("-99.00")
        assert projection.license_balance_cif == Decimal("47.50")
        assert projection.balance_source == "LICENSE"


def test_projection_uses_the_canonical_item_balance_only_when_enabled():
    projection = project_effective_item_cif(
        licence=SimpleNamespace(individual_item_cif_override=True, get_balance_cif=Decimal("47.50")),
        item=SimpleNamespace(balance_cif_fc=Decimal("-2.50")),
        legacy_row_balance=Decimal("47.50"),
    )
    assert projection.effective_row_balance == Decimal("-2.50")
    assert projection.diagnostics["executable_available_cif"] == Decimal("0")


def test_effective_available_cif_is_source_row_scoped_for_same_hsn():
    """A same-HSN sibling must never lend its CIF to another import row."""
    licence = SimpleNamespace(individual_item_cif_override=True, get_balance_cif=Decimal("999.00"))
    dietary_fibre = SimpleNamespace(pk=None, hsn="08023100", balance_cif_fc=Decimal("1.00"))
    sibling = SimpleNamespace(pk=None, hsn="08023100", balance_cif_fc=Decimal("10116.41"))

    assert effective_source_row_cif_available(
        licence=licence, item=dietary_fibre, legacy_available=Decimal("10116.41")
    ) == Decimal("1.00")
    assert effective_source_row_cif_available(
        licence=licence, item=sibling, legacy_available=Decimal("10116.41")
    ) == Decimal("10116.41")
