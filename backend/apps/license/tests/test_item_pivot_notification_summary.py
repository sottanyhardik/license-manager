"""
Regression tests for Phase 2B.2B: the Item Pivot Report's Notification/Norm
Summary panel (`_build_notification_summary`) and its new
`_effective_planned_quantity` per-cell field, both moved to the backend as a
verbatim translation of the frontend's `calculateNotificationSummary`
(`ItemPivotReport.tsx:507-621`). See
docs/architecture/ITEM_PIVOT_NOTIFICATION_SUMMARY_DESIGN.md.

These are pure-function unit tests against hand-built fixtures (no DB, no
HTTP) per the design doc's §7 step 1 guidance — `_build_notification_summary`
and `_effective_planned_quantity` take plain dicts/numbers and are fully
testable in isolation. They intentionally pin the three documented quirks
(§9) as *expected*, not bugs: last-license-wins restriction percentage,
the footer `total_available` vs. fallback-adjusted row `available`, and the
restriction-pool dedup-by-license-and-percentage rule.
"""
import pytest

from apps.license.views.item_pivot_report import (
    _build_notification_summary,
    _effective_planned_quantity,
)

# Item catalogue used across these tests, mirroring `sorted_items`
# ((item_id, item_name) tuples) in report-iteration order.
ITEMS_XY = [(1, "X"), (2, "Y")]
ITEMS_SINGLE = [(1, "ITEM A")]


def _license(number, balance_cif=0, items=None):
    return {
        "license_number": number,
        "balance_cif": balance_cif,
        "items": items or {},
    }


def _item_cell(**overrides):
    cell = {
        "available_quantity": 0,
        "plan_cif": 0,
        "plan_quantity": 0,
        "planned_cif": 0,
        "restriction": None,
        "restriction_value": 0,
    }
    cell.update(overrides)
    return cell


# ---------------------------------------------------------------------------
# Design doc §3 — restriction pool dedup worked example
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_restriction_pool_dedup_shares_value_per_license_not_per_item():
    """Two licenses, LIC-A carrying items X and Y both at 5% (restriction_value
    1000 each), LIC-B carrying item X at 5% (restriction_value 800). The
    5% pool must be 1800 (LIC-A's 1000 counted once + LIC-B's 800), NOT 2800
    (which would double-count LIC-A's shared quota across its two items)."""
    lic_a = _license(
        "LIC-A",
        items={
            "X": _item_cell(available_quantity=10, restriction=5.0, restriction_value=1000.0),
            "Y": _item_cell(available_quantity=5, restriction=5.0, restriction_value=1000.0),
        },
    )
    lic_b = _license(
        "LIC-B",
        items={
            "X": _item_cell(available_quantity=10, restriction=5.0, restriction_value=800.0),
        },
    )

    summary = _build_notification_summary([lic_a, lic_b], ITEMS_XY)

    pct_group = summary["restricted_items_by_percentage"]["5.0"]
    assert pct_group["shared_restriction_value"] == pytest.approx(1800.0)
    # Both items appear under the group, each with their own per-item figures.
    assert set(pct_group["items"].keys()) == {"X", "Y"}
    assert pct_group["items"]["X"]["available"] == pytest.approx(20.0)
    assert pct_group["items"]["Y"]["available"] == pytest.approx(5.0)
    # No regular items — both X and Y are restricted.
    assert summary["regular_items"] == {}


# ---------------------------------------------------------------------------
# Design doc §4 — blended unit price test table
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "plan_cif, plan_quantity, expected",
    [
        pytest.param(1000.00, 50, 20.00, id="normal_case"),
        pytest.param(0, 0, 0.00, id="no_plan_at_all_not_nan"),
        pytest.param(500.00, 0, 0.00, id="qty_zero_guard_fires_even_with_nonzero_cif"),
        pytest.param(333.33, 3, 111.11, id="rounding_boundary"),
    ],
)
@pytest.mark.django_db
def test_blended_unit_price_table(plan_cif, plan_quantity, expected):
    lic = _license(
        "LIC-BLEND",
        items={
            "ITEM A": _item_cell(plan_cif=plan_cif, plan_quantity=plan_quantity),
        },
    )
    summary = _build_notification_summary([lic], ITEMS_SINGLE)
    assert summary["blended_unit_price"] == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Regular item — available balance, no plan at all
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_regular_item_with_available_quantity_and_no_plan_has_zero_unit_price():
    lic = _license(
        "LIC-REG",
        items={"ITEM A": _item_cell(available_quantity=100)},
    )
    summary = _build_notification_summary([lic], ITEMS_SINGLE)

    item = summary["regular_items"]["ITEM A"]
    assert item["available"] == pytest.approx(100.0)
    assert item["planned_cif"] == pytest.approx(0.0)
    # No manual plan -> falls back to available_quantity for planned_qty,
    # per the reverse-engineered Pass 3 rule (not a bug: an unplanned item's
    # "planned quantity" is its full available balance).
    assert item["planned_qty"] == pytest.approx(100.0)
    assert item["unit_price"] == pytest.approx(0.0)
    assert summary["total_available"] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Design doc §9(b) — manually-split item, available_quantity == 0
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_manual_split_item_available_falls_back_to_planned_qty_but_total_uses_raw_zero():
    """A split-planned item (e.g. a "DWP - E1" line) with no import
    counterpart: available_quantity is 0, but a manual plan exists. The
    item's own `available` must fall back to planned_qty (40), while the
    scope's `total_available` must still sum the RAW pre-fallback
    contribution (0) — this is quirk §9(b), preserved verbatim, not fixed."""
    lic = _license(
        "LIC-SPLIT",
        items={
            "ITEM A": _item_cell(available_quantity=0, plan_cif=400.0, plan_quantity=40.0),
        },
    )
    summary = _build_notification_summary([lic], ITEMS_SINGLE)

    item = summary["regular_items"]["ITEM A"]
    assert item["available"] == pytest.approx(40.0)
    assert item["planned_cif"] == pytest.approx(400.0)
    assert item["planned_qty"] == pytest.approx(40.0)
    assert item["unit_price"] == pytest.approx(10.0)
    # Quirk: total_available is 0, not 40, even though the row above shows 40.
    assert summary["total_available"] == pytest.approx(0.0)
    assert summary["total_planned_cif"] == pytest.approx(400.0)
    assert summary["total_planned_qty"] == pytest.approx(40.0)


# ---------------------------------------------------------------------------
# Design doc §9(a) — last-license-wins restriction percentage
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_last_license_wins_when_licenses_disagree_on_restriction_percentage():
    lic_a = _license(
        "LIC-A",
        items={"X": _item_cell(available_quantity=10, restriction=5.0, restriction_value=1000.0)},
    )
    lic_b = _license(
        "LIC-B",
        items={"X": _item_cell(available_quantity=10, restriction=8.0, restriction_value=500.0)},
    )
    summary = _build_notification_summary([lic_a, lic_b], [(1, "X")])

    # LIC-B iterated last -> its 8% wins for the item's routing, with no
    # error/reconciliation against LIC-A's disagreeing 5%.
    assert "8.0" in summary["restricted_items_by_percentage"]
    assert "X" in summary["restricted_items_by_percentage"]["8.0"]["items"]
    assert "5.0" not in summary["restricted_items_by_percentage"] or (
        "X" not in summary["restricted_items_by_percentage"].get("5.0", {}).get("items", {})
    )


# ---------------------------------------------------------------------------
# Opening balance (Pass 1)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_opening_balance_sums_license_balance_cif():
    lic_a = _license("LIC-A", balance_cif=1000.0)
    lic_b = _license("LIC-B", balance_cif=250.5)
    summary = _build_notification_summary([lic_a, lic_b], ITEMS_SINGLE)
    assert summary["opening_balance"] == pytest.approx(1250.5)


# ---------------------------------------------------------------------------
# _effective_planned_quantity — mirrors the existing _effective_planned_cif
# test pattern (test_item_pivot_totals_and_selection_rule.py).
# ---------------------------------------------------------------------------

def test_effective_planned_quantity_uses_manual_plan_when_present():
    # Manual plan present (plan_quantity=40) -> selects the manual quantity,
    # not available_quantity, even though available_quantity is nonzero.
    assert _effective_planned_quantity(40.0, 400.0, 999.0) == 40.0


def test_effective_planned_quantity_falls_back_to_available_quantity_when_no_manual_plan():
    # No manual plan at all -> falls back to available_quantity.
    assert _effective_planned_quantity(0, 0, 50.0) == 50.0


def test_effective_planned_quantity_manual_cif_only_still_selects_manual_branch():
    # plan_cif alone (no plan_quantity) is enough to select the manual
    # branch -> returns plan_quantity (0), not available_quantity, mirroring
    # _effective_planned_cif's `pq or pc` truthy check.
    assert _effective_planned_quantity(0, 400.0, 999.0) == 0
