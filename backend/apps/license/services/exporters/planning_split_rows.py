"""
Shared rendering for `LicenseItemPlan` "split" sub-rows in Excel exports.

A manually-authored utilization plan can split a single import item across
several planning item names — e.g. "20 units of Wheat Flour @ $5.00/unit"
and "10 units of Milk Powder @ $7.50/unit" both splitting one Milk Powder
import item. Multiple Excel exporters render each *visible* split (real
planned quantity or CIF) as an indented sub-row beneath the item's own
summary row:

  - `apps/license/services/exporters/license_balance_excel.py` — the
    single-license "Plan Utilization" sheet and the bulk multi-sheet variant
    (both used to carry their own copy of this filter/loop/style code).
  - `apps/license/views/item_report.py` — the Item Report export.
  - `apps/license/views/item_pivot_report.py` — a dedicated "Planning
    Splits" sheet (its pivot grid is a wide, one-row-per-license layout,
    some of it write-only/append-only, so it can't host indented child rows
    the way the other two reports do; it reuses `rows_for_splits()` only).

This module is the single source of truth for:
  - `rows_for_splits()` — the filter + label/format rules every caller must
    reproduce exactly (pure, no openpyxl dependency).
  - `write_split_sub_rows()` — a writer for standard (non-write-only)
    worksheets, parameterized by column indices so each report's own column
    layout can be expressed without duplicating the loop/style code.

Note the two pre-existing implementations styled the quantity/CIF sub-row
cells differently (license_balance_excel.py used a plain, non-italic font
and an explicit `#,##0.000`/`#,##0.00` number format; item_report.py reused
the italic "split" font and left the number format as General). Both are
preserved exactly via the `value_font`/`qty_num_fmt`/`cif_num_fmt`
parameters below — this module does not silently unify per-report styling.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence

# Shared "split sub-row" styling — EBF3FF fill + 2B5EA7 italic font, proven
# across every pre-existing implementation. Callers of `write_split_sub_rows`
# may override any of these via its `fill`/`font`/`badge_font` kwargs.
SPLIT_FILL_COLOR = "EBF3FF"
SPLIT_FONT_COLOR = "2B5EA7"


def _default_split_fill():
    from openpyxl.styles import PatternFill
    return PatternFill(start_color=SPLIT_FILL_COLOR, end_color=SPLIT_FILL_COLOR, fill_type="solid")


def _default_split_font():
    from openpyxl.styles import Font
    return Font(size=9, color=SPLIT_FONT_COLOR, italic=True)


def _default_split_badge_font():
    from openpyxl.styles import Font
    return Font(size=8, color=SPLIT_FONT_COLOR, italic=True)


def rows_for_splits(splits: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter + format raw `LicenseItemPlan` split dicts into row-ready records.

    `splits` is the per-item `splits` list as built by
    `apps.license.services.plan_reporting._build_map` (each entry a dict
    with `item_name`, `planned_quantity`, `unit_price`, `planned_cif_fc`).

    Only splits with a real planned quantity or CIF are "visible" — this is
    the exact filter every existing implementation applies. Returned dicts
    are in filtered order, `split_number` numbered 1-based *within that
    filtered list* (not the raw list), matching the current
    `enumerate(_valid_splits)` behaviour.
    """
    visible = [
        s for s in (splits or [])
        if float(s.get('planned_quantity') or 0) > 0
        or float(s.get('planned_cif_fc') or 0) > 0
    ]
    rows: List[Dict[str, Any]] = []
    for i, sp in enumerate(visible):
        unit_price = float(sp.get('unit_price') or 0)
        item_name_label = sp.get('item_name') or f'Split {i + 1}'
        rows.append({
            'split_number': i + 1,
            'split_badge': f'Split {i + 1}',
            'item_name_label': item_name_label,
            'indented_label': f'  └ {item_name_label}',
            'unit_price': unit_price,
            'unit_price_label': f'@ ${unit_price:,.2f}/unit' if unit_price else '',
            'planned_quantity': float(sp.get('planned_quantity') or 0),
            'planned_cif_fc': float(sp.get('planned_cif_fc') or 0),
        })
    return rows


def write_split_sub_rows(
    ws,
    start_row: int,
    splits: Iterable[Dict[str, Any]],
    *,
    name_col: int,
    badge_col: int,
    qty_col: int,
    cif_col: int,
    price_col: "int | None" = None,
    other_cols: Sequence[int] = (),
    fill=None,
    font=None,
    badge_font=None,
    value_font=None,
    border=None,
    qty_num_fmt: "str | None" = None,
    cif_num_fmt: "str | None" = None,
) -> int:
    """Write one row per *visible* split to a standard (non-write-only)
    worksheet, starting at `start_row`. Returns the number of rows written
    (0 if there are no visible splits) — callers use this to advance their
    own row cursor and for `row_span`/merge-cell math.

    Column layout is entirely caller-specified so each report's own columns
    can be reused as-is:
      - `name_col`: indented planning-item-name label.
      - `price_col` (optional): "@ $X.XX/unit" label, blank if price is 0.
      - `badge_col`: "Split N" badge.
      - `qty_col` / `cif_col`: planned quantity / planned CIF-FC values.
      - `other_cols`: any additional columns that should get the split's
        fill/border painted but no value (e.g. filler columns between the
        item's own columns in a fixed-width table row).

    Styling defaults to the shared EBF3FF fill / 2B5EA7 italic font. `font`
    is used for the name/price cells; `value_font` (defaulting to `font`)
    is used for the qty/cif cells — pass a plain `Font` there to reproduce
    license_balance_excel.py's original (non-italic) qty/cif styling.
    `border` defaults to None (no border touched), matching item_report.py's
    original behaviour; pass your own `Border`/`Side` instance to reproduce
    license_balance_excel.py's THIN_BORDER-everywhere behaviour — each file
    defines its own `Border` instance and they are not assumed interchangeable.
    """
    from openpyxl.styles import Alignment

    rows = rows_for_splits(splits)
    if not rows:
        return 0

    fill = fill or _default_split_fill()
    font = font or _default_split_font()
    badge_font = badge_font or _default_split_badge_font()
    value_font = value_font or font

    touched_cols = set(other_cols) | {name_col, badge_col, qty_col, cif_col}
    if price_col is not None:
        touched_cols.add(price_col)

    row = start_row
    for r in rows:
        # Paint fill(+border) across every touched column first, then
        # overwrite the specific value-bearing cells below — matching the
        # "paint the row, then overwrite specific cells" order every
        # pre-existing implementation used.
        for col in touched_cols:
            cell = ws.cell(row=row, column=col)
            cell.fill = fill
            if border is not None:
                cell.border = border

        name_cell = ws.cell(row=row, column=name_col, value=r['indented_label'])
        name_cell.fill = fill
        if border is not None:
            name_cell.border = border
        name_cell.font = font
        name_cell.alignment = Alignment(horizontal='left', vertical='center')

        if price_col is not None:
            price_cell = ws.cell(row=row, column=price_col, value=r['unit_price_label'])
            price_cell.fill = fill
            if border is not None:
                price_cell.border = border
            price_cell.font = font
            price_cell.alignment = Alignment(horizontal='left', vertical='center')

        badge_cell = ws.cell(row=row, column=badge_col, value=r['split_badge'])
        badge_cell.fill = fill
        if border is not None:
            badge_cell.border = border
        badge_cell.font = badge_font
        badge_cell.alignment = Alignment(horizontal='center', vertical='center')

        qty_cell = ws.cell(row=row, column=qty_col, value=r['planned_quantity'])
        qty_cell.fill = fill
        if border is not None:
            qty_cell.border = border
        qty_cell.font = value_font
        qty_cell.alignment = Alignment(horizontal='right', vertical='center', wrap_text=True)
        if qty_num_fmt:
            qty_cell.number_format = qty_num_fmt

        cif_cell = ws.cell(row=row, column=cif_col, value=r['planned_cif_fc'])
        cif_cell.fill = fill
        if border is not None:
            cif_cell.border = border
        cif_cell.font = value_font
        cif_cell.alignment = Alignment(horizontal='right', vertical='center', wrap_text=True)
        if cif_num_fmt:
            cif_cell.number_format = cif_num_fmt

        row += 1

    return len(rows)
