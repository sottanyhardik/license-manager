"""
Item Pivot Report - module-level helpers (pivot field/fill rules, item-summary
tables, notification summary, planning-split rows). Split out of
``item_pivot_report.py``; re-exported there unchanged.
"""

import logging


logger = logging.getLogger(__name__)

# Item-block fields in pivot order (mirrors ItemPivotReport.tsx). RUTILE blocks add UNIT PRICE after BALANCE QTY.
PIVOT_ITEM_FIELDS = [
    ("hsn_code", "HSN CODE"), ("description", "DESCRIPTION"), ("total_qty", "TOTAL QTY"),
    ("allotted_qty", "ALLOTTED QTY"), ("allotted_cif", "ALLOTTED CIF"), ("debited_qty", "DEBITED QTY"),
    ("boe_used_cif", "DEBITED CIF"), ("billed_qty", "BILLED QTY"), ("billed_cif", "BILLED CIF"),
    ("balance_qty", "BALANCE QTY"), ("restriction_percent", "RESTRICTION %"), ("restriction_value", "RESTRICTION VAL"),
    ("plan_qty", "PLAN QTY"), ("planned_cif", "PLANNED CIF"),
]
PIVOT_ALWAYS_SHOWN_FIELDS = {"hsn_code", "description"}

# Item tints cycled per item block, as ITEM_BG_COLORS in ItemPivotReport.tsx (rgba over white).
PIVOT_ITEM_TINTS = [
    ((59, 130, 246), 0.10), ((16, 185, 129), 0.10), ((249, 115, 22), 0.10), ((139, 92, 246), 0.10),
    ((236, 72, 153), 0.10), ((234, 179, 8), 0.12), ((6, 182, 212), 0.10), ((107, 114, 128), 0.10),
]


def _pivot_item_fill(item_index):
    """Solid fill for item block ``item_index``: the browser tint blended over white."""
    from openpyxl.styles import PatternFill

    (red, green, blue), alpha = PIVOT_ITEM_TINTS[item_index % len(PIVOT_ITEM_TINTS)]

    def blend(channel):
        return round(255 * (1 - alpha) + channel * alpha)

    colour = f"{blend(red):02X}{blend(green):02X}{blend(blue):02X}"
    return PatternFill(start_color=colour, end_color=colour, fill_type="solid")


def _pivot_has_value(value):
    if value is None or value == "":
        return False
    try:
        return float(value) != 0
    except (TypeError, ValueError):
        return True


def _pivot_item_fields(item, group):
    """(key, label) pairs shown for one item block. A field is dropped when every licence cell and the
    item total for it are null or 0; HSN CODE and DESCRIPTION always show."""
    fields = list(PIVOT_ITEM_FIELDS)
    if item.get("product_category") == "RUTILE":
        fields = fields[:10] + [("unit_price", "UNIT PRICE")] + fields[10:]
    total = group["totals"]["items"].get(item["key"]) or {}
    return [
        (key, label) for key, label in fields
        if key in PIVOT_ALWAYS_SHOWN_FIELDS
        or _pivot_has_value(total.get(key))
        or any(_pivot_has_value((license_row["items"].get(item["key"]) or {}).get(key)) for license_row in group["licenses"])
    ]


def _fit_sheet_columns(sheet, minimum=12, maximum=40):
    """Size each column to its longest value so headers and figures are not cut off.

    Merged labels (category headers, merged fixed headers) are skipped: a long label that spans
    several columns must not widen one of them.
    """
    from openpyxl.utils import get_column_letter

    merged_anchors = {merged.start_cell.coordinate for merged in sheet.merged_cells.ranges}
    longest = {}
    for row in sheet.iter_rows():
        for cell in row:
            if cell.value is None or cell.coordinate in merged_anchors:
                continue
            longest[cell.column] = max(longest.get(cell.column, 0), len(str(cell.value)))
    for column, length in longest.items():
        sheet.column_dimensions[get_column_letter(column)].width = min(max(length + 2, minimum), maximum)


TOTAL_SUMMARY_TITLE = "TOTAL SUMMARY — ALL NOTIFICATIONS"
# Metric columns of the Item Summary table, in order (matches the on-screen table).
ITEM_SUMMARY_EXCEL_METRICS = (
    ("TOTAL QTY", "total_qty"), ("ALLOTTED QTY", "allotted_qty"), ("ALLOTTED CIF", "allotted_cif"),
    ("DEBITED QTY", "boe_used_qty"), ("DEBITED CIF", "boe_used_cif"), ("BALANCE QTY", "balance_qty"),
    ("UNIT PRICE", "unit_price"), ("PLAN QTY", "planned_qty"), ("PLANNED CIF", "planned_cif"),
)


def _item_summary_name(category, item_name):
    """The product category name (RUTILE, ALUMINIUM OXIDE, ...); the item name only when there is none."""
    return category if category and category != "UNCLASSIFIED" else (item_name or "")


def _item_summary_rows_from_matrix(group):
    """One Item Summary row per matrix item, read from the same totals the matrix shows above it."""
    totals = (group.get("totals") or {}).get("items", {})
    rows = []
    for item in group.get("item_groups", []):
        total = totals.get(item["key"], {})
        cells = [lic["items"][item["key"]] for lic in group.get("licenses", []) if item["key"] in lic.get("items", {})]
        sion_suffix = f" - {item['sion']}"
        raw_name = item["name"][:-len(sion_suffix)] if item["name"].endswith(sion_suffix) else item["name"]
        rows.append({
            "item_name": _item_summary_name(item.get("product_category"), raw_name),
            "sion": item["sion"],
            "hsn_codes": list(dict.fromkeys(cell["hsn_code"] for cell in cells if cell.get("hsn_code"))),
            "license_count": len(cells),
            "total_qty": total.get("total_qty"), "allotted_qty": total.get("allotted_qty"), "allotted_cif": total.get("allotted_cif"),
            "boe_used_qty": total.get("debited_qty"), "boe_used_cif": total.get("boe_used_cif"), "balance_qty": total.get("balance_qty"),
            "unit_price": total.get("unit_price"), "planned_qty": total.get("plan_qty"), "planned_cif": total.get("planned_cif"),
        })
    return rows


def _item_summary_rows_from_projection(rows):
    """Backend projection rows (all-notification total), named as on screen, with the SION-rule priority prefix."""
    named = []
    for row in rows:
        name = _item_summary_name(row.get("product_category"), row.get("item_name"))
        priority = row.get("planning_priority")
        named.append({**row, "item_name": f"{priority} · {name}" if priority is not None else name})
    return named


def _item_summary_subtotal(rows):
    """SUBTOTAL of the Item Summary rows. Unit price is weighted by balance QTY over the rows that have one."""
    subtotal = {
        field: sum(float(row.get(field) or 0) for row in rows)
        for field in ("total_qty", "allotted_qty", "allotted_cif", "boe_used_qty", "boe_used_cif", "balance_qty", "planned_qty", "planned_cif")
    }
    priced = [row for row in rows if row.get("unit_price") is not None and float(row.get("balance_qty") or 0) > 0]
    weight = sum(float(row["balance_qty"]) for row in priced)
    subtotal["unit_price"] = sum(float(row["unit_price"]) * float(row["balance_qty"]) for row in priced) / weight if weight > 0 else None
    return subtotal


def _write_item_summary_table(sheet, start_row, title, rows, subtotal, header_font, header_fill):
    """Write the Item Summary table: a header row, one row per item, then SUBTOTAL. Returns the next free row."""
    from openpyxl.styles import Alignment

    headers =[title, "SION", "HSN CODES", "LICENCES"] + [label for label, _field in ITEM_SUMMARY_EXCEL_METRICS]
    for col_idx, name in enumerate(headers, 1):
        cell = sheet.cell(row=start_row, column=col_idx, value=name)
        cell.font = header_font
        cell.fill = header_fill
    sheet.cell(row=start_row, column=1).alignment = Alignment(wrap_text=True, vertical='center')

    def metric(value):
        # Zero and missing values stay blank, as on screen.
        return float(value) if value not in (None, '') and float(value) != 0 else None

    row_number = start_row + 1
    for row in rows:
        sheet.cell(row=row_number, column=1, value=row["item_name"])
        sheet.cell(row=row_number, column=2, value=row["sion"])
        sheet.cell(row=row_number, column=3, value=", ".join(row["hsn_codes"]) or None)
        sheet.cell(row=row_number, column=4, value=row["license_count"])
        for col_idx, (_label, field) in enumerate(ITEM_SUMMARY_EXCEL_METRICS, 5):
            sheet.cell(row=row_number, column=col_idx, value=metric(row.get(field)))
        row_number += 1
    sheet.cell(row=row_number, column=1, value="SUBTOTAL").font = header_font
    for col_idx, (_label, field) in enumerate(ITEM_SUMMARY_EXCEL_METRICS, 5):
        sheet.cell(row=row_number, column=col_idx, value=metric(subtotal.get(field)))
    return row_number + 1


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _effective_planned_cif(plan_quantity, plan_cif, planned_cif):
    """The single manual-vs-norm-derived planned-CIF selection rule for one
    license x item cell: prefer the user-authored manual plan (`plan_quantity`/
    `plan_cif`, from `LicenseItemPlan`) when one exists, otherwise fall back
    to the norm-derived `planned_cif` (E1/E5/E132 waterfall). Computed once
    here and exposed per cell as `effective_planned_cif` — every consumer
    (JSON, React, Excel) reads that field instead of re-deriving this rule
    (Phase 2B.2A; see docs/architecture/ITEM_PIVOT_DISPLAY_DATASET_DESIGN.md).
    """
    pq = plan_quantity or 0
    pc = plan_cif or 0
    return pc if (pq or pc) else (planned_cif or 0)


def _effective_planned_quantity(plan_quantity, plan_cif, available_quantity):
    """Quantity counterpart to `_effective_planned_cif` — same manual-vs-norm
    branch (see that docstring), applied to quantity instead of CIF. The
    norm-derived branch falls back to `available_quantity` (not a
    `planned_quantity` field) because the E1/E5/E132 waterfall always plans
    against the full available balance; there is no separate norm-derived
    planned-quantity field to select instead. Computed once here and exposed
    per cell as `effective_planned_quantity` (Phase 2B.2B; see
    docs/architecture/ITEM_PIVOT_NOTIFICATION_SUMMARY_DESIGN.md §5).

    Note: the design doc's reference signature carries an extra unused
    `planned_quantity` parameter for symmetry with `_effective_planned_cif`;
    it is omitted here since it can never affect the return value — this is
    a signature-only deviation with zero output difference.
    """
    pq = plan_quantity or 0
    pc = plan_cif or 0
    return pq if (pq or pc) else (available_quantity or 0)


def _build_notification_summary(licenses, items):
    """Translates `ItemPivotReport.tsx:507-621` (`calculateNotificationSummary`)
    verbatim, including its quirks — see
    docs/architecture/ITEM_PIVOT_NOTIFICATION_SUMMARY_DESIGN.md §1 (spec),
    §3 (restriction-pool worked example), §4 (blended unit price), §9
    (quirks, preserved on purpose per the §12 business decision — do NOT
    "improve" this logic without a corresponding product decision).

    One exception, approved via the Calculation Ownership audit
    (`docs/architecture/CALCULATION_OWNERSHIP.md`, 2026-08-07): Pass 3's
    manual-vs-norm CIF/quantity selection reads the already-resolved
    `effective_planned_cif`/`effective_planned_quantity` fields instead of
    re-deriving the same branch inline. This is not a quirk or a business
    rule — it's plumbing — so consuming the canonical field instead of a
    second copy of the rule is a pure cleanup, not a behavior change.

    `licenses` — already-built license row dicts (as returned by
    `_build_license_row`) for this scope: either one notification group's
    license list, or every license under a norm flattened across its
    notification groups.
    `items` — the report's ordered item catalogue as `(item_id, item_name)`
    tuples, same order as `sorted_items` / the response's top-level `items`
    list.
    """
    # Pass 1 — opening balance. This is the same sum as
    # `notification_totals[norm][notification_key]['balance_cif']`
    # (Phase 2B.2A) for the per-notification scope, and intentionally kept
    # in sync rather than reused via a shared variable — see design doc
    # §9(c)/§12: consolidating *how* the sum is computed doesn't change the
    # displayed value, so no special-casing is needed here.
    opening_balance = sum(float(lic.get('balance_cif', 0) or 0) for lic in licenses)

    # Pass 2 — restriction pool dedup: a license's `restriction_value` is a
    # shared quota against its restriction percentage, not a per-item value.
    # Dedup key is license_number + percentage, NOT license + item — see
    # design doc §3 for the worked example this reproduces exactly.
    restricted_items_by_percentage = {}
    processed_restrictions = set()
    for lic in licenses:
        lic_number = lic.get('license_number')
        for item_id, item_name in items:
            item_data = (lic.get('items') or {}).get(item_name)
            if item_data and item_data.get('restriction') is not None:
                pct = float(item_data.get('restriction') or 0)
                key = f"{lic_number}_{pct}"
                if key not in processed_restrictions:
                    processed_restrictions.add(key)
                    bucket = restricted_items_by_percentage.setdefault(
                        pct, {'shared_restriction_value': 0.0, 'items': {}}
                    )
                    bucket['shared_restriction_value'] += float(
                        item_data.get('restriction_value', 0) or 0
                    )

    # Pass 3 — per-item aggregation across licenses, in report item order.
    regular_items = {}
    total_available = 0.0
    total_planned_cif = 0.0
    total_planned_qty = 0.0

    for item_id, item_name in items:
        item_available = 0.0
        item_planned = 0.0
        item_planned_qty = 0.0
        has_restriction = False
        restriction_percentage = 0.0

        for lic in licenses:
            item_data = (lic.get('items') or {}).get(item_name)
            if item_data:
                available_quantity = float(item_data.get('available_quantity', 0) or 0)
                item_available += available_quantity

                # Manual-vs-norm selection already resolved once, per cell,
                # by `_effective_planned_cif`/`_effective_planned_quantity`
                # in `_build_license_row` — read those fields directly
                # rather than re-deriving the same branch here. (This used
                # to recompute it inline; fixed 2026-08-07 per the
                # Calculation Ownership audit — see
                # docs/architecture/CALCULATION_OWNERSHIP.md. Behavior is
                # unchanged: same rule, one fewer copy of it.)
                item_planned += float(item_data.get('effective_planned_cif', 0) or 0)
                item_planned_qty += float(item_data.get('effective_planned_quantity', 0) or 0)

                if item_data.get('restriction') is not None:
                    has_restriction = True
                    # Last license wins if licenses in this scope disagree
                    # on the percentage for this item — deliberate quirk,
                    # preserve verbatim, do not dedupe/reconcile. See design
                    # doc §9(a).
                    restriction_percentage = float(item_data.get('restriction') or 0)

        if item_available > 0 or item_planned > 0:
            item_summary = {
                # Split-planned items with no import counterpart have
                # item_available == 0; fall back to planned qty so the row
                # shows the correct balance quantity instead of 0. See
                # design doc §9(b) — the grand total below intentionally
                # does NOT use this fallback-adjusted value.
                'available': item_available if item_available > 0 else item_planned_qty,
                'planned_cif': item_planned,
                'planned_qty': item_planned_qty,
                'unit_price': (
                    round(item_planned / item_planned_qty, 2) if item_planned_qty > 0 else 0.0
                ),
            }

            if has_restriction:
                bucket = restricted_items_by_percentage.setdefault(
                    restriction_percentage, {'shared_restriction_value': 0.0, 'items': {}}
                )
                bucket['items'][item_name] = item_summary
            else:
                regular_items[item_name] = item_summary

            # Quirk (design doc §9(b)): the grand total sums the RAW
            # per-license `item_available` contribution, NOT the
            # fallback-adjusted `item_summary['available']` value set just
            # above — preserved verbatim from the frontend; do not "fix".
            total_available += item_available
            total_planned_cif += item_planned
            total_planned_qty += item_planned_qty

    blended_unit_price = (
        round(total_planned_cif / total_planned_qty, 2) if total_planned_qty > 0 else 0.0
    )

    return {
        'opening_balance': opening_balance,
        'total_available': total_available,
        'total_planned_cif': total_planned_cif,
        'total_planned_qty': total_planned_qty,
        'blended_unit_price': blended_unit_price,
        'regular_items': regular_items,
        'restricted_items_by_percentage': {
            str(pct): bucket for pct, bucket in restricted_items_by_percentage.items()
        },
    }


def _xlsx_safe_row(row):
    """Strip XML-illegal control characters from string cells before writing.

    Condition-sheet / description text extracted from DGFT PDFs can contain
    control chars (e.g. form-feed) that openpyxl rejects with IllegalCharacterError,
    which would 500 the whole Excel export. Cleans plain string values and the
    value of WriteOnlyCell objects in place; passes numbers/None through.
    """
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

    cleaned = []
    for cell in row:
        val = getattr(cell, "value", cell)  # WriteOnlyCell -> its value; else the cell itself
        if isinstance(val, str):
            safe = ILLEGAL_CHARACTERS_RE.sub("", val)
            if val is not cell:  # it's a WriteOnlyCell — clean in place, keep styling
                cell.value = safe
                cleaned.append(cell)
            else:
                cleaned.append(safe)
        else:
            cleaned.append(cell)
    return cleaned


def _planning_split_sheet_rows(licenses_by_norm_notification, item_names):
    """Flat (license, pivot-item-column, split) rows for a "Planning Splits"
    sheet — one row per *visible* LicenseItemPlan split, for every license /
    item-name-column combination that actually has one.

    The main pivot grid is one row per license with a wide, fixed set of
    item-name columns (some of it write-only/append-only), so it can't host
    indented child rows the way license_balance_excel.py / item_report.py do.
    This sheet is additive detail alongside that grid, not a replacement for
    its per-item-name Plan Qty / Plan CIF cells.

    Reuses `rows_for_splits()` (the shared filter/label rules) rather than
    re-deriving the visibility filter here.
    """
    from apps.license.services.exporters.planning_split_rows import rows_for_splits

    rows = []
    for norm_class in sorted(licenses_by_norm_notification.keys()):
        notifications_dict = licenses_by_norm_notification[norm_class]
        for notification, licenses_list in sorted(notifications_dict.items()):
            for lic in licenses_list:
                for item_name in item_names:
                    item_data = lic['items'].get(item_name) or {}
                    for split_row in rows_for_splits(item_data.get('splits') or []):
                        rows.append((
                            lic['license_number'],
                            item_name,
                            split_row['item_name_label'],
                            split_row['split_badge'],
                            split_row['unit_price'],
                            split_row['planned_quantity'],
                            split_row['planned_cif_fc'],
                        ))
    return rows


def _write_notification_summary_block(worksheet, summary, title):
    """Append the Notification/Norm Summary block (Phase 2B.2B, §7 step 6 —
    docs/architecture/ITEM_PIVOT_NOTIFICATION_SUMMARY_DESIGN.md §8) to
    `worksheet`, directly transcribing `summary` — the exact
    `_build_notification_summary` DTO (design doc §2), the same object the
    JSON response and React already render. Pure formatting: every value
    written is a direct dict read off `summary`; no aggregation happens
    here (do not add sum()/reduce() to this function).

    `summary` — one `notification_summary[norm][notification]` or
    `norm_summary[norm]` dict. `title` — the section header text.
    """
    from openpyxl.styles import Font, PatternFill
    from openpyxl.cell import WriteOnlyCell

    worksheet.append([])  # blank separator row

    section_header_cell = WriteOnlyCell(worksheet, value=title)
    section_header_cell.font = Font(bold=True, color='FFFFFF')
    section_header_cell.fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    worksheet.append(_xlsx_safe_row([section_header_cell]))

    column_header_row = []
    for header in ('Item', 'Available', 'Remaining Qty', 'Unit Price', 'Remaining CIF'):
        cell = WriteOnlyCell(worksheet, value=header)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
        column_header_row.append(cell)
    worksheet.append(_xlsx_safe_row(column_header_row))

    opening_label_cell = WriteOnlyCell(worksheet, value='Opening Balance')
    opening_label_cell.font = Font(bold=True)
    worksheet.append(_xlsx_safe_row(
        [opening_label_cell, summary.get('opening_balance', 0), None, None, None]
    ))

    for item_name, item_summary in summary.get('regular_items', {}).items():
        worksheet.append(_xlsx_safe_row([
            item_name,
            item_summary.get('available', 0),
            item_summary.get('planned_qty', 0),
            item_summary.get('unit_price', 0),
            item_summary.get('planned_cif', 0),
        ]))

    for pct_str, bucket in summary.get('restricted_items_by_percentage', {}).items():
        # Display-only fix (design doc §13): the dict key is `str(float)`
        # ("10.0"); format without the trailing ".0" for the sheet label.
        # This is string formatting, not a calculation.
        pct_display = f"{float(pct_str):g}"

        group_header_cell = WriteOnlyCell(worksheet, value=f"RESTRICTED ITEMS - {pct_display}%")
        group_header_cell.font = Font(bold=True)
        worksheet.append(_xlsx_safe_row([group_header_cell]))

        for item_name, item_summary in bucket.get('items', {}).items():
            worksheet.append(_xlsx_safe_row([
                item_name,
                item_summary.get('available', 0),
                item_summary.get('planned_qty', 0),
                item_summary.get('unit_price', 0),
                item_summary.get('planned_cif', 0),
            ]))

        balance_label_cell = WriteOnlyCell(worksheet, value=f"Balance {pct_display}%")
        balance_label_cell.font = Font(bold=True)
        worksheet.append(_xlsx_safe_row([
            balance_label_cell, bucket.get('shared_restriction_value', 0), None, None, None
        ]))

    grand_total_label_cell = WriteOnlyCell(worksheet, value='GRAND TOTAL')
    grand_total_label_cell.font = Font(bold=True)
    grand_total_available_cell = WriteOnlyCell(worksheet, value=summary.get('total_available', 0))
    grand_total_available_cell.font = Font(bold=True)
    grand_total_qty_cell = WriteOnlyCell(worksheet, value=summary.get('total_planned_qty', 0))
    grand_total_qty_cell.font = Font(bold=True)
    grand_total_price_cell = WriteOnlyCell(worksheet, value=summary.get('blended_unit_price', 0))
    grand_total_price_cell.font = Font(bold=True)
    grand_total_cif_cell = WriteOnlyCell(worksheet, value=summary.get('total_planned_cif', 0))
    grand_total_cif_cell.font = Font(bold=True)
    worksheet.append(_xlsx_safe_row([
        grand_total_label_cell,
        grand_total_available_cell,
        grand_total_qty_cell,
        grand_total_price_cell,
        grand_total_cif_cell,
    ]))
