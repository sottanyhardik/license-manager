"""
Fast, no-DB tests for `rows_for_splits()` / `write_split_sub_rows()` — the
shared filter/label/format rules extracted from license_balance_excel.py's
duplicated split-row rendering (also reused by item_report.py and
item_pivot_report.py's "Planning Splits" sheet).
"""
from apps.license.services.exporters.planning_split_rows import (
    rows_for_splits,
    write_split_sub_rows,
)


def test_rows_for_splits_filters_out_zero_qty_and_zero_cif_splits():
    """A split with neither a planned quantity nor a planned CIF is not
    "visible" — matching every pre-existing implementation's filter."""
    splits = [
        {"item_name": "WHEAT", "planned_quantity": 20.0, "unit_price": 5.0, "planned_cif_fc": 100.0},
        {"item_name": "GHOST", "planned_quantity": 0, "unit_price": 0, "planned_cif_fc": 0},
        {"item_name": "MILK", "planned_quantity": 0, "unit_price": 7.5, "planned_cif_fc": 75.0},
    ]
    rows = rows_for_splits(splits)
    assert [r["item_name_label"] for r in rows] == ["WHEAT", "MILK"]


def test_rows_for_splits_numbers_within_the_filtered_list_not_the_raw_list():
    """split_number/split_badge are 1-based *within the visible list* — the
    filtered-out "GHOST" split must not consume a number."""
    splits = [
        {"item_name": "WHEAT", "planned_quantity": 20.0, "unit_price": 5.0, "planned_cif_fc": 100.0},
        {"item_name": "GHOST", "planned_quantity": 0, "unit_price": 0, "planned_cif_fc": 0},
        {"item_name": "MILK", "planned_quantity": 10.0, "unit_price": 7.5, "planned_cif_fc": 75.0},
    ]
    rows = rows_for_splits(splits)
    assert [r["split_number"] for r in rows] == [1, 2]
    assert [r["split_badge"] for r in rows] == ["Split 1", "Split 2"]


def test_rows_for_splits_label_and_price_formatting():
    splits = [
        {"item_name": "WHEAT", "planned_quantity": 20.0, "unit_price": 5.0, "planned_cif_fc": 100.0},
        {"item_name": None, "planned_quantity": 10.0, "unit_price": 0, "planned_cif_fc": 75.0},
    ]
    rows = rows_for_splits(splits)

    assert rows[0]["item_name_label"] == "WHEAT"
    assert rows[0]["indented_label"] == "  └ WHEAT"
    assert rows[0]["unit_price"] == 5.0
    assert rows[0]["unit_price_label"] == "@ $5.00/unit"
    assert rows[0]["planned_quantity"] == 20.0
    assert rows[0]["planned_cif_fc"] == 100.0

    # Untagged split (item_name is None) falls back to "Split N"; a zero
    # unit_price renders as a blank label, not "@ $0.00/unit".
    assert rows[1]["item_name_label"] == "Split 2"
    assert rows[1]["indented_label"] == "  └ Split 2"
    assert rows[1]["unit_price_label"] == ""


def test_rows_for_splits_handles_none_and_missing_fields():
    """Splits with missing/None numeric fields don't raise and are treated
    as zero (matching `float(s.get(...) or 0)` in every original impl)."""
    splits = [{"item_name": "X"}]
    assert rows_for_splits(splits) == []
    assert rows_for_splits(None) == []
    assert rows_for_splits([]) == []


class _FakeCell:
    def __init__(self):
        self.value = None
        self.fill = None
        self.font = None
        self.border = None
        self.alignment = None
        self.number_format = None


class _FakeWorksheet:
    """Minimal stand-in for an openpyxl Worksheet — just enough for
    write_split_sub_rows to address cells by (row, column)."""

    def __init__(self):
        self._cells = {}

    def cell(self, row, column, value=None):
        key = (row, column)
        c = self._cells.setdefault(key, _FakeCell())
        if value is not None:
            c.value = value
        return c


def test_write_split_sub_rows_returns_count_and_writes_expected_cells():
    ws = _FakeWorksheet()
    splits = [
        {"item_name": "WHEAT", "planned_quantity": 20.0, "unit_price": 5.0, "planned_cif_fc": 100.0},
        {"item_name": "MILK", "planned_quantity": 10.0, "unit_price": 7.5, "planned_cif_fc": 75.0},
    ]
    written = write_split_sub_rows(
        ws, start_row=5, splits=splits,
        name_col=1, price_col=2, badge_col=3, qty_col=5, cif_col=7,
        other_cols=(4, 6, 8),
    )
    assert written == 2

    assert ws.cell(row=5, column=1).value == "  └ WHEAT"
    assert ws.cell(row=5, column=3).value == "Split 1"
    assert ws.cell(row=5, column=5).value == 20.0
    assert ws.cell(row=5, column=7).value == 100.0
    assert ws.cell(row=6, column=1).value == "  └ MILK"
    assert ws.cell(row=6, column=3).value == "Split 2"

    # "other_cols" cells get the fill painted but carry no value.
    assert ws.cell(row=5, column=4).value is None
    assert ws.cell(row=5, column=4).fill is not None


def test_write_split_sub_rows_returns_zero_for_no_visible_splits():
    ws = _FakeWorksheet()
    written = write_split_sub_rows(
        ws, start_row=5, splits=[{"item_name": "X", "planned_quantity": 0, "planned_cif_fc": 0}],
        name_col=1, price_col=2, badge_col=3, qty_col=5, cif_col=7,
    )
    assert written == 0
