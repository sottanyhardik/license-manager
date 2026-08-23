# UI/PDF/Excel Parity Testing Guide

## Overview

The parity testing framework verifies that **financial data is identical across all three outputs**:
1. **API (Screen)** — `/api/licenses/{id}/ledger_detail/` response
2. **PDF Export** — Ledger PDF document
3. **Excel Export** — Ledger spreadsheet

This ensures users see the same numbers whether they view the UI, download a PDF, or export to Excel.

## Golden Case: License 0310833996

The test suite validates against a golden (reference) license with known correct values:

| Field | Value | Currency |
|-------|-------|----------|
| Purchase Bill | ₹45,83,719.00 | INR |
| Sale Bill | ₹65,24,056.00 | INR |
| Profit | ₹19,40,337.00 | INR |
| Profit State | PROFIT | — |

**Note:** Bill amounts are always in INR (bill_currency). Balance amounts are in USD for DFIA licenses.

## Test Files

### 1. `test_ui_pdf_excel_parity_golden.py` (Main Test Suite)

**Purpose:** Verify golden case values are returned by all three outputs.

**Test Classes:**

#### `UIAPIParityTest`
Tests that the API endpoint returns correct values:
- `test_api_endpoint_returns_purchase_bill_field` — Field exists
- `test_api_endpoint_returns_sale_bill_field` — Field exists
- `test_api_endpoint_returns_profit_field` — Field exists
- `test_api_purchase_bill_value_correct` — Value matches ₹45,83,719.00
- `test_api_sale_bill_value_correct` — Value matches ₹65,24,056.00
- `test_api_profit_value_correct` — Value matches ₹19,40,337.00
- `test_api_profit_state_is_profit` — State is "PROFIT"

**Run:**
```bash
pytest apps/license/tests/test_ui_pdf_excel_parity_golden.py::UIAPIParityTest -v
```

#### `PDFParityTest`
Tests that PDF export contains correct values:
- `test_pdf_contains_purchase_bill_value` — ₹45,83,719.00 appears in PDF text
- `test_pdf_contains_sale_bill_value` — ₹65,24,056.00 appears in PDF text
- `test_pdf_contains_profit_value` — ₹19,40,337.00 appears in PDF text
- `test_pdf_profit_state_label_visible` — "PROFIT" label visible

**Note:** PDF extraction is text-based, so it searches for the number in multiple formats:
- Plain: "4583719.00"
- Indian format: "45,83,719.00"
- With spaces: "45 83 719.00"

**Run:**
```bash
pytest apps/license/tests/test_ui_pdf_excel_parity_golden.py::PDFParityTest -v
```

#### `ExcelParityTest`
Tests that Excel export contains correct values:
- `test_excel_contains_purchase_bill_cell` — Value found in a cell
- `test_excel_contains_sale_bill_cell` — Value found in a cell
- `test_excel_contains_profit_cell` — Value found in a cell

**Run:**
```bash
pytest apps/license/tests/test_ui_pdf_excel_parity_golden.py::ExcelParityTest -v
```

#### `CrossOutputParityTest`
Tests parity across all three outputs simultaneously:
- `test_all_three_outputs_return_expected_values` — Master test
- `test_transaction_count_consistency` — Same count across outputs
- `test_decimal_precision_uniform` — All use 2 decimal places
- `test_no_balance_recalculation_across_outputs` — All use canonical service

**Run:**
```bash
pytest apps/license/tests/test_ui_pdf_excel_parity_golden.py::CrossOutputParityTest -v
```

### 2. `parity_utils.py` (Shared Utilities)

**Purpose:** Provide reusable extraction and assertion utilities.

**Classes:**

#### `APIDataExtractor`
Extract structured data from API responses:
- `extract_summary()` — Get purchase_bill, sale_bill, profit, profit_state
- `extract_transactions()` — Get transaction list
- `extract_company_utilizations()` — Get per-company balances
- `transaction_count()` — Count all transactions
- `display_transaction_count()` — Count display transactions (respects display rule)

#### `PDFDataExtractor`
Extract data from PDF exports:
- `extract_text()` — Get all text from PDF
- `normalize_number_for_search()` — Generate search formats (plain, Indian, etc.)
- `contains_value()` — Search for a number in PDF
- `get_page_count()` — Count pages

#### `ExcelDataExtractor`
Extract data from Excel exports:
- `load_workbook()` — Load from bytes
- `find_value_in_worksheet()` — Search for Decimal in cells, return (row, col)
- `find_sheet_by_name_pattern()` — Find sheet by substring match
- `get_cell_value()` — Get value from cell
- `get_row_values()` — Get all values in row

#### `ParityAssertions`
Common assertion helpers:
- `assert_values_equal()` — Decimal comparison with tolerance
- `assert_precision_2_places()` — Verify 2 decimal places
- `assert_all_values_present()` — Check dictionary keys

#### `ParityDataComparison`
Compare outputs:
- `compare_summary_blocks()` — Compare expected vs. actual
- `all_match()` — Check if all values matched
- `mismatch_report()` — Generate readable diff

## Running Tests

### Run All Parity Tests
```bash
pytest apps/license/tests/test_ui_pdf_excel_parity_golden.py -v
```

### Run Specific Test Class
```bash
pytest apps/license/tests/test_ui_pdf_excel_parity_golden.py::UIAPIParityTest -v
```

### Run Specific Test
```bash
pytest apps/license/tests/test_ui_pdf_excel_parity_golden.py::UIAPIParityTest::test_api_purchase_bill_value_correct -v
```

### Run with Output
```bash
pytest apps/license/tests/test_ui_pdf_excel_parity_golden.py -v -s
```

### Run with Detailed Failures
```bash
pytest apps/license/tests/test_ui_pdf_excel_parity_golden.py -v --tb=long
```

## Expected Results

All tests should **PASS** when:
1. ✅ API returns correct purchase_bill, sale_bill, profit fields
2. ✅ API values match golden case: ₹45,83,719.00 / ₹65,24,056.00 / ₹19,40,337.00
3. ✅ PDF text contains these values in searchable format
4. ✅ Excel workbook cells contain these values
5. ✅ Transaction counts match across outputs
6. ✅ Decimal precision is uniform (2 places everywhere)
7. ✅ All outputs use canonical service, not recalculation

## Failure Analysis

### If API test fails:
Check `/api/licenses/0310833996/ledger_detail/` response:
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/licenses/[ID]/ledger_detail/" | jq .summary
```

Expected structure:
```json
{
  "summary": {
    "total_purchase_bill_inr": "4583719.00",
    "total_sale_bill_inr": "6524056.00",
    "total_profit_loss": "1940337.00",
    "profit_state": "PROFIT"
  }
}
```

### If PDF test fails:
1. Check PDF is generated: `generate_detailed_licenses_pdf([license_id])`
2. Extract text and search for values
3. Verify values format (Indian format: "45,83,719.00" vs plain "4583719.00")

### If Excel test fails:
1. Load workbook: `load_workbook(BytesIO(excel_bytes))`
2. Check sheet names: `workbook.sheetnames`
3. Search for values starting from row 1
4. Verify cell format (values should be numeric, not strings)

## Extending the Tests

To add a new test case:

1. **Create golden case in database** (or load existing license)
2. **Add test method to appropriate class:**

```python
def test_my_new_scenario(self):
    """Test description."""
    response = self.client.get(f"/api/licenses/{self.license.id}/ledger_detail/")
    data = response.json()
    
    # Use utilities
    summary = APIDataExtractor.extract_summary(data)
    
    # Assert
    self.assertEqual(summary['purchase_bill'], expected_value)
```

3. **Use utilities for consistency:**

```python
from apps.license.tests.parity_utils import (
    APIDataExtractor,
    PDFDataExtractor,
    ExcelDataExtractor,
    ParityAssertions,
    ParityDataComparison,
)

# Extract API data
summary = APIDataExtractor.extract_summary(api_response)
transactions = APIDataExtractor.extract_transactions(api_response)

# Extract PDF data
pdf_text = PDFDataExtractor.extract_text(pdf_bytes)
contains_value = PDFDataExtractor.contains_value(pdf_text, Decimal('123.45'))

# Extract Excel data
workbook = ExcelDataExtractor.load_workbook(excel_bytes)
cell = ExcelDataExtractor.find_value_in_worksheet(
    workbook['Ledger Detail'],
    Decimal('123.45')
)

# Assert
ParityAssertions.assert_values_equal(actual, expected, "Purchase Bill")
ParityAssertions.assert_precision_2_places(value, "Sale Bill")
```

## Key Concepts

### Bill Currency vs. Balance Currency
- **Bill amounts (INR):** Always in Indian Rupees
  - `total_purchase_bill_inr`, `total_sale_bill_inr`
  - Sum of invoice amounts from trades
- **Balance amounts (USD for DFIA):** Currency depends on license type
  - `license_running_balance`, `current_balance`
  - Sum of license value changes (CIF FC)
- **Profit (INR):** Always in Indian Rupees
  - `total_profit_loss`
  - Difference between sale bill and purchase bill (not related to balance)

### Display Rule
Not all transactions are displayed:
- **Display transactions:** PURCHASE + SALE rows only, in chronological order
- **Hidden:** OPENING row shown only when no PURCHASE exists
- All tests check that PDF/Excel show same transactions as API display rule

### Canonical Service
All three outputs must consume the same backend data:
```
CanonicalLedgerService.build_canonical_ledger_dataset(license_id)
↓
APILedgerSerializer (for HTTP response)
APILedgerPDFExporter (for PDF export)
APILedgerExcelExporter (for Excel export)
```

If any output recalculates balance, it's a bug — the test will catch it.

## Troubleshooting

### Test skipped: "Golden license not found"
The test assumes license 0310833996 exists in the test database. Either:
1. Load production data into test database
2. Modify test to use a different license ID
3. Create the golden case in `setUp()` or a fixture

### PDF text extraction finds nothing
1. Check PDF generation doesn't error
2. Try `pypdf` library directly:
```python
from pypdf import PdfReader
reader = PdfReader(BytesIO(pdf_bytes))
text = reader.pages[0].extract_text()
print(text)
```
3. Verify numbers appear in expected format in PDF

### Excel cell lookup returns None
1. Check workbook has sheets
2. Print worksheet cell values:
```python
ws = workbook.active
for row in ws.iter_rows():
    for cell in row:
        print(f"{cell.coordinate}: {cell.value}")
```
3. Verify values are numeric, not strings

## Performance

- API tests: ~0.5s each (one HTTP call)
- PDF tests: ~1s each (PDF generation + text extraction)
- Excel tests: ~1s each (Excel generation + workbook load)
- Total suite: ~10-15s for all tests

## Next Steps

Once all tests pass:
1. ✅ Golden case parity verified
2. ✅ Framework ready for additional scenarios
3. 🔜 Add tests for edge cases (zero balance, negative profit, etc.)
4. 🔜 Add tests for multi-company balances
5. 🔜 Add tests for commission handling (excluded from balance)
6. 🔜 Add integration test combining all scenarios
