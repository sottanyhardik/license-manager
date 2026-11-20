"""Cross-surface reconciliation audit — comparison logic (pure, no DB)."""
from decimal import Decimal

from apps.license.services.cross_surface_reconciliation import (
    ReconciliationResult,
    _compare,
    _walk_pivot_licence_rows,
)

Z = Decimal("0")


def _surfaces(**over):
    canonical = {
        "total_cif": Decimal("1000.00"), "boe_raw_cif": Decimal("300.00"), "debited_cif": Decimal("300.00"),
        "allotted_cif": Decimal("100.00"), "billed_cif": Decimal("50.00"), "balance_cif": Decimal("550.00"),
        "planned_qty": Decimal("10.000"), "planned_cif": Decimal("200.00"), "total_qty": Decimal("100.000"),
        "debited_qty": Decimal("30.000"), "allotted_qty": Decimal("10.000"), "balance_qty_live": Decimal("60.000"),
        "balance_qty_snapshot": Decimal("60.000"),
    }
    overview = {"total_cif": Decimal("1000.00"), "debited_cif": Decimal("300.00"), "allotted_cif": Decimal("100.00"),
                "balance_cif": Decimal("550.00"), "planned_cif": Decimal("200.00")}
    items_tab = {"total_cif": Decimal("1000.00"), "debited_cif": Decimal("300.00"), "allotted_cif": Decimal("100.00"),
                 "balance_cif": Decimal("550.00"), "total_qty": Decimal("100.000"), "debited_qty": Decimal("30.000"),
                 "allotted_qty": Decimal("10.000"), "balance_qty": Decimal("60.000")}
    surfaces = {"canonical": canonical, "overview": overview, "items_tab": items_tab}
    for path, value in over.items():
        surface, metric = path.split("__")
        surfaces[surface][metric] = value
    return surfaces


def _run(surfaces):
    res = ReconciliationResult(surface_values={1: surfaces})
    _compare(res, {1: "LIC1"}, include_pivot=False, include_item_report=False)
    return res


def test_consistent_licence_has_only_the_billed_card_gap():
    # Overview cards omit billed-without-BOE: 1000 − 300 − 100 = 600 ≠ balance 550 (RC2), nothing else differs.
    res = _run(_surfaces())
    assert [(d.metric, d.root_cause) for d in res.discrepancies] == [("balance_cif(cards)", "RC2_OVERVIEW_BILLED_NOT_SHOWN")]
    assert res.discrepancies[0].difference == Decimal("-50.00")


def test_engine_identity_residual_is_reported_not_hidden():
    res = _run(_surfaces(canonical__balance_cif=Decimal("540.00"), overview__balance_cif=Decimal("540.00"),
                         items_tab__balance_cif=Decimal("540.00")))
    identity = [d for d in res.discrepancies if d.root_cause == "RC8_ENGINE_IDENTITY"]
    assert len(identity) == 1 and identity[0].difference == Decimal("-10.00")


def test_negative_balance_compared_signed():
    res = _run(_surfaces(canonical__balance_cif=Decimal("-25.00"), overview__balance_cif=Decimal("0.00")))
    hit = [d for d in res.discrepancies if d.metric == "balance_cif" and d.report == "overview"]
    assert hit and hit[0].source_value == Decimal("-25.00")  # never floored before comparing


def test_licence_level_cif_classified_separately_from_mismatch():
    zero = _run(_surfaces(items_tab__total_cif=Z))
    other = _run(_surfaces(items_tab__total_cif=Decimal("900.00")))
    assert {d.root_cause for d in zero.discrepancies if d.metric == "total_cif"} == {"RC11_LICENCE_LEVEL_CIF"}
    assert {d.root_cause for d in other.discrepancies if d.metric == "total_cif"} == {"RC12_IMPORT_VS_EXPORT_CIF"}


def test_stale_stored_allotted_qty_flags_items_tab():
    res = _run(_surfaces(items_tab__allotted_qty=Decimal("15.000"), items_tab__balance_qty=Decimal("55.000")))
    causes = {(d.metric, d.root_cause) for d in res.discrepancies}
    assert ("allotted_qty", "RC3_ITEMS_TAB_STORED_COLUMNS") in causes
    assert ("balance_qty", "RC3_ITEMS_TAB_STORED_COLUMNS") in causes


def test_tolerances_are_decimal_and_exclusive():
    res = _run(_surfaces(items_tab__debited_qty=Decimal("30.0009"), overview__planned_cif=Decimal("200.009")))
    assert not [d for d in res.discrepancies if d.metric in ("debited_qty", "planned_cif")]


def test_by_cause_ranks_by_cif_impact():
    res = _run(_surfaces(items_tab__total_cif=Z, items_tab__allotted_qty=Decimal("99.000")))
    ranked = list(res.by_cause())
    assert ranked[0] == "RC11_LICENCE_LEVEL_CIF"


def test_walk_pivot_rows_finds_nested_licence_rows_once():
    report = {"groups": [{"licenses": [{"license_id": 1, "items": {}, "total_cif": "1"}]},
                         {"children": [{"licenses": [{"license_id": 2, "items": {"a": {"license_id": 9, "items": {}, "total_cif": "x"}}, "total_cif": "2"}]}]}]}
    assert [r["license_id"] for r in _walk_pivot_licence_rows(report)] == [1, 2]
