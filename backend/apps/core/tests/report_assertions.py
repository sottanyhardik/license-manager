"""
Shared JSON-vs-export regression assertions — Phase 2A of the
export-consistency initiative.

Generalizes the hand-rolled pattern already proven in
`apps.license.tests.test_license_purchase_profit_report` (fetch JSON, fetch
Excel/PDF, load the workbook, assert cell values equal JSON fields) so other
report test files don't each reinvent the same workbook-loading/cell-reading
boilerplate. These are plain functions, not fixtures — callers still do
their own `client.get(json_url)` / `client.get(export_url)` /
`load_workbook(BytesIO(response.content))`; these helpers only encapsulate
the *comparison*, matching this codebase's existing convention of
file-local fixtures with no `conftest.py`/fixture-discovery magic.
"""
from decimal import Decimal
from typing import Any, Dict, Iterable, Optional


def assert_excel_matches_json(
    workbook,
    json_summary: Dict[str, Any],
    sheet_name: str,
    label_to_summary_key: Dict[str, str],
    *,
    metric_label_col: int = 1,
    metric_value_col: int = 2,
    header_search_rows: int = 15,
    header_labels=("Metric", "Value"),
) -> None:
    """Generalizes
    `test_view_excel_summary_metric_table_matches_json_summary`'s pattern:
    locate the Metric/Value header row in `sheet_name`, read the rows below
    it, assert each labeled row equals `json_summary[label_to_summary_key[label]]`.

    Raises AssertionError with the specific label/expected/actual values on
    mismatch — a financial system's export tests must produce a legible
    diff, not a bare `!=`.
    """
    worksheet = workbook[sheet_name]

    header_row = next(
        (
            r for r in range(1, header_search_rows + 1)
            if worksheet.cell(row=r, column=metric_label_col).value == header_labels[0]
            and worksheet.cell(row=r, column=metric_value_col).value == header_labels[1]
        ),
        None,
    )
    assert header_row is not None, (
        f"Could not find a {header_labels[0]!r}/{header_labels[1]!r} header row "
        f"in sheet {sheet_name!r} within the first {header_search_rows} rows."
    )

    values_by_label = {}
    row = header_row + 1
    while worksheet.cell(row=row, column=metric_label_col).value in label_to_summary_key:
        label = worksheet.cell(row=row, column=metric_label_col).value
        values_by_label[label] = worksheet.cell(row=row, column=metric_value_col).value
        row += 1

    for label, summary_key in label_to_summary_key.items():
        assert label in values_by_label, (
            f"Sheet {sheet_name!r}: expected a row labeled {label!r} under the "
            f"{header_labels[0]!r}/{header_labels[1]!r} table, found none."
        )
        expected = json_summary[summary_key]
        actual = values_by_label[label]
        assert actual == expected, (
            f"Sheet {sheet_name!r}, metric {label!r}: Excel value {actual!r} "
            f"!= JSON summary[{summary_key!r}] value {expected!r}"
        )


def assert_excel_rows_match_json_rows(
    workbook,
    json_rows: Iterable[Dict[str, Any]],
    sheet_name: str,
    column_map: Dict[str, int],
    header_row: int,
    *,
    key_field: str,
    key_column: Optional[int] = None,
    tolerance: Decimal = Decimal("0.01"),
) -> None:
    """Row-by-row: for each row in `json_rows`, find the matching Excel row
    (by `key_field`, e.g. "license_number"/"item_name") below `header_row`
    in `sheet_name`, and assert every column in `column_map` matches within
    `tolerance` for numeric values (Decimal rounding display differences,
    not real drift) or exactly for non-numeric values.

    `key_column` defaults to `column_map[key_field]`.
    """
    worksheet = workbook[sheet_name]
    key_col = key_column if key_column is not None else column_map[key_field]

    excel_rows_by_key = {}
    row = header_row + 1
    while True:
        key_value = worksheet.cell(row=row, column=key_col).value
        if key_value is None:
            break
        excel_rows_by_key[key_value] = row
        row += 1

    for json_row in json_rows:
        key_value = json_row[key_field]
        assert key_value in excel_rows_by_key, (
            f"Sheet {sheet_name!r}: no Excel row found with "
            f"{key_field}={key_value!r} below header row {header_row}."
        )
        excel_row = excel_rows_by_key[key_value]
        for field, col in column_map.items():
            expected = json_row[field]
            actual = worksheet.cell(row=excel_row, column=col).value
            if isinstance(expected, (int, float, Decimal)) and isinstance(actual, (int, float, Decimal)):
                assert abs(Decimal(str(actual)) - Decimal(str(expected))) <= tolerance, (
                    f"Sheet {sheet_name!r} row {excel_row} ({key_field}={key_value!r}), "
                    f"field {field!r}: Excel value {actual!r} != JSON value {expected!r} "
                    f"(tolerance {tolerance})"
                )
            else:
                assert actual == expected, (
                    f"Sheet {sheet_name!r} row {excel_row} ({key_field}={key_value!r}), "
                    f"field {field!r}: Excel value {actual!r} != JSON value {expected!r}"
                )


def assert_pdf_text_contains_values(pdf_bytes: bytes, expected_values: Iterable[str]) -> None:
    """Substring-presence check only — NOT row-structure verification. PDF
    isn't cell-addressable and reportlab table text can reflow/reorder on
    extraction, so this only asserts every pre-formatted value in
    `expected_values` (e.g. an f"{value:,.2f}" string, formatted exactly as
    the report renders it) appears somewhere in the extracted, whitespace-
    normalized page text. Prefer `assert_excel_matches_json`/
    `assert_excel_rows_match_json_rows` as the primary regression net;
    use this only as a secondary/spot check for PDF.
    """
    from pypdf import PdfReader
    from io import BytesIO

    reader = PdfReader(BytesIO(pdf_bytes))
    full_text = " ".join(
        " ".join(page.extract_text().split())
        for page in reader.pages
    )

    for expected in expected_values:
        normalized = " ".join(str(expected).split())
        assert normalized in full_text, (
            f"Expected value {normalized!r} not found in extracted PDF text."
        )
