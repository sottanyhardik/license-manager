# Parity Utilities Reference

Quick reference for using the parity testing utilities in your own tests.

## Import All Utilities

```python
from apps.license.tests.parity_utils import (
    APIDataExtractor,
    PDFDataExtractor,
    ExcelDataExtractor,
    ParityAssertions,
    ParityDataComparison,
)
```

---

## APIDataExtractor

### Extract Summary Block

```python
# Get all financial summary data in one call
summary = APIDataExtractor.extract_summary(api_response)

# Returns dict with keys:
# - 'purchase_bill': Decimal (INR)
# - 'sale_bill': Decimal (INR)
# - 'profit': Decimal (INR)
# - 'profit_state': str ("PROFIT", "LOSS", "BREAK_EVEN", "UNAVAILABLE")

assert summary['purchase_bill'] == Decimal('45000.00')
assert summary['profit_state'] == 'PROFIT'
```

### Extract Transactions

```python
# Get full transaction list
transactions = APIDataExtractor.extract_transactions(api_response)

# Each transaction has:
# - 'id': int
# - 'type': str ("PURCHASE", "SALE", "COMMISSION", "OPENING")
# - 'amount': Decimal (license value in USD)
# - 'bill_amount': Decimal (invoice in INR, or None for OPENING)
# - 'license_running_balance': Decimal (balance after this txn)
# - 'company_id': int (our company)
# - 'party_name': str (counterparty, or None)
# - 'is_commission': bool
# - 'affects_balance': bool

for txn in transactions:
    print(f"{txn['date']} {txn['type']} {txn['amount']} → {txn['license_running_balance']}")

# Count transactions
count = len(transactions)
assert count > 0, "Expected at least one transaction"
```

### Extract Company Utilizations

```python
# Get per-company balance breakdown
utilizations = APIDataExtractor.extract_company_utilizations(api_response)

# Returns dict: {
#   '123:Company A': Decimal('1000.00'),
#   '456:Company B': Decimal('2500.00'),
# }

for company_key, balance in utilizations.items():
    print(f"{company_key}: {balance}")

# Query specific company
company_a_balance = utilizations.get('123:Company A')
assert company_a_balance == Decimal('1000.00')
```

### Count Transactions

```python
# Count all transactions (including hidden OPENING)
all_count = APIDataExtractor.transaction_count(api_response)
assert all_count >= 3  # At least 3 transactions

# Count display transactions (respects display rule)
# PURCHASE + SALE only, OPENING shown only when no PURCHASE
display_count = APIDataExtractor.display_transaction_count(api_response)
assert display_count <= all_count  # Display <= all
```

---

## PDFDataExtractor

### Extract Text from PDF

```python
# Get all PDF text as normalized string
pdf_text = PDFDataExtractor.extract_text(pdf_bytes)

# Text is whitespace-normalized (multiple spaces → single space)
# Useful for searching for values
assert "Ledger Detail" in pdf_text
```

### Search for Numbers in PDF

```python
# Generate all reasonable formats for a number
value = Decimal('4583719.00')
formats = PDFDataExtractor.normalize_number_for_search(value)

# Returns:
# [
#   '4583719.00',      # plain
#   '4583719',         # no decimal
#   '458371900',       # no separator
#   '45,83,719.00',    # Indian format
#   '45,83,719',       # Indian without decimal
#   '45 83 719.00',    # Indian with spaces
# ]

# Search PDF for any of these formats
if any(fmt in pdf_text for fmt in formats):
    print("Found the number!")

# Or use the convenience method
if PDFDataExtractor.contains_value(pdf_text, Decimal('4583719.00')):
    print("Value found in PDF")
```

### Get Page Count

```python
pages = PDFDataExtractor.get_page_count(pdf_bytes)
assert pages > 0, "PDF should have at least one page"
print(f"PDF has {pages} pages")
```

---

## ExcelDataExtractor

### Load Workbook

```python
from openpyxl import load_workbook

# Load from bytes
workbook = ExcelDataExtractor.load_workbook(excel_bytes)

# Or load directly
workbook = load_workbook(BytesIO(excel_bytes))

# Get sheet names
sheet_names = workbook.sheetnames
# Returns: ['Ledger Detail', 'Summary', 'Company Breakdown']
```

### Find Value in Worksheet

```python
# Find cell containing a specific value
worksheet = workbook['Ledger Detail']
position = ExcelDataExtractor.find_value_in_worksheet(
    worksheet,
    target_value=Decimal('4583719.00'),
    search_cols=range(1, 10),  # Search columns A-J
    max_rows=50                 # Search first 50 rows
)

if position:
    row, col = position
    print(f"Found at cell {chr(64+col)}{row}")  # e.g., "D25"
else:
    print("Value not found")
```

### Find Sheet by Name

```python
# Find sheet by substring pattern (case-insensitive)
sheet = ExcelDataExtractor.find_sheet_by_name_pattern(workbook, 'ledger')
# Returns: 'Ledger Detail' (if it exists)

if sheet:
    worksheet = workbook[sheet]
else:
    raise ValueError("No sheet matching 'ledger' found")
```

### Get Cell Value

```python
# Read single cell
value = ExcelDataExtractor.get_cell_value(worksheet, row=10, col=2)
# Gets cell B10 (1-indexed)

assert value == Decimal('1234.56')
```

### Get Row Values

```python
# Read entire row
values = ExcelDataExtractor.get_row_values(worksheet, row=5)
# Returns: [header1, value1, value2, ...]

for i, value in enumerate(values, 1):
    print(f"Column {i}: {value}")
```

---

## ParityAssertions

### Assert Values Equal

```python
# Compare two values with tolerance
ParityAssertions.assert_values_equal(
    actual=Decimal('4583719.00'),
    expected=Decimal('4583719.01'),
    label='Purchase Bill',
    tolerance=Decimal('0.01')  # Default
)

# Raises AssertionError if difference > tolerance
# Message: "Purchase Bill: expected 4583719.01, got 4583719.00 (difference: 0.01)"
```

### Assert Precision

```python
# Ensure value has exactly 2 decimal places
ParityAssertions.assert_precision_2_places(
    value=Decimal('1234.56'),
    label='Purchase Amount'
)

# Fails if value is:
# - Decimal('1234.567') → too many places
# - Decimal('1234.5') → too few places
# - Decimal('1234') → no decimal places
```

### Assert Keys Present

```python
# Check that all required keys exist in dict
required = ['purchase_bill', 'sale_bill', 'profit']
ParityAssertions.assert_all_values_present(
    actual_dict=api_response['summary'],
    required_keys=required,
    context='API summary block'
)

# Raises AssertionError if any key missing
# Message includes: "missing required keys ['profit'], Present: ['purchase_bill', 'sale_bill']"
```

---

## ParityDataComparison

### Compare Summary Blocks

```python
# Build expected values
expected = {
    'purchase_bill': Decimal('45000.00'),
    'sale_bill': Decimal('65000.00'),
    'profit': Decimal('20000.00'),
    'profit_state': 'PROFIT'
}

# Extract actual from API
actual = APIDataExtractor.extract_summary(api_response)

# Compare
comparison = ParityDataComparison.compare_summary_blocks(actual, expected)

# Returns:
# {
#   'purchase_bill': {'expected': 45000.00, 'actual': 45000.00, 'match': True},
#   'sale_bill': {'expected': 65000.00, 'actual': 65000.00, 'match': True},
#   'profit': {'expected': 20000.00, 'actual': 20000.00, 'match': True},
#   'profit_state': {'expected': 'PROFIT', 'actual': 'PROFIT', 'match': True}
# }
```

### Check All Match

```python
# Quick check if all values matched
if ParityDataComparison.all_match(comparison):
    print("All values match!")
else:
    # Something didn't match, get details
    report = ParityDataComparison.mismatch_report(comparison)
    print(report)
    # Output:
    # Mismatches:
    #   profit: expected 20000.00, got 19999.50
```

### Get Mismatch Report

```python
# Generate human-readable report of differences
report = ParityDataComparison.mismatch_report(comparison)

if "Mismatches:" in report:
    print("Found differences:")
    print(report)
else:
    print("All values match")
```

---

## Complete Example: Custom Parity Test

```python
import pytest
from decimal import Decimal
from io import BytesIO
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.license.models import LicenseDetailsModel
from apps.license.services.exporters.ledger_pdf import generate_detailed_licenses_pdf
from apps.license.services.exporters.ledger_excel import generate_ledger_detailed_excel
from apps.license.tests.parity_utils import (
    APIDataExtractor,
    PDFDataExtractor,
    ExcelDataExtractor,
    ParityAssertions,
    ParityDataComparison,
)


@pytest.mark.django_db
def test_custom_license_parity(authenticated_client, license):
    """Test parity for a custom license case."""
    
    # Expected values
    expected = {
        'purchase_bill': Decimal('10000.00'),
        'sale_bill': Decimal('15000.00'),
        'profit': Decimal('5000.00'),
        'profit_state': 'PROFIT'
    }
    
    # 1. GET API DATA
    response = authenticated_client.get(
        f"/api/licenses/{license.id}/ledger_detail/"
    )
    assert response.status_code == 200
    api_data = response.json()
    
    # Extract structured API summary
    api_summary = APIDataExtractor.extract_summary(api_data)
    api_txns = APIDataExtractor.extract_transactions(api_data)
    api_count = APIDataExtractor.transaction_count(api_data)
    
    # 2. GET PDF DATA
    pdf_bytes = generate_detailed_licenses_pdf([license.id])
    pdf_text = PDFDataExtractor.extract_text(pdf_bytes)
    pdf_pages = PDFDataExtractor.get_page_count(pdf_bytes)
    
    # 3. GET EXCEL DATA
    excel_bytes = generate_ledger_detailed_excel([license.id])
    workbook = ExcelDataExtractor.load_workbook(excel_bytes)
    ledger_sheet = ExcelDataExtractor.find_sheet_by_name_pattern(workbook, 'ledger')
    worksheet = workbook[ledger_sheet]
    
    # 4. ASSERT API AGAINST EXPECTED
    api_comparison = ParityDataComparison.compare_summary_blocks(api_summary, expected)
    assert ParityDataComparison.all_match(api_comparison), (
        f"API values don't match expected:\n"
        f"{ParityDataComparison.mismatch_report(api_comparison)}"
    )
    
    # 5. ASSERT PRECISION
    for field in ['purchase_bill', 'sale_bill', 'profit']:
        ParityAssertions.assert_precision_2_places(
            api_summary[field],
            label=f"API {field}"
        )
    
    # 6. ASSERT PDF CONTAINS VALUES
    assert PDFDataExtractor.contains_value(pdf_text, expected['purchase_bill']), \
        "Purchase bill not in PDF text"
    assert PDFDataExtractor.contains_value(pdf_text, expected['sale_bill']), \
        "Sale bill not in PDF text"
    assert PDFDataExtractor.contains_value(pdf_text, expected['profit']), \
        "Profit not in PDF text"
    
    # 7. ASSERT EXCEL CONTAINS VALUES
    for value in [expected['purchase_bill'], expected['sale_bill'], expected['profit']]:
        position = ExcelDataExtractor.find_value_in_worksheet(worksheet, value)
        assert position is not None, f"Value {value} not found in Excel"
    
    # 8. ASSERT COUNTS
    assert api_count > 0, "API should have at least one transaction"
    assert pdf_pages > 0, "PDF should have at least one page"
    assert len(workbook.sheetnames) > 0, "Excel should have at least one sheet"
    
    print(f"✓ Parity verified: API/PDF/Excel all match expected values")
    print(f"  - API summary: {api_summary}")
    print(f"  - PDF pages: {pdf_pages}")
    print(f"  - Excel sheets: {workbook.sheetnames}")
    print(f"  - Transaction count: {api_count}")
```

---

## Tips & Tricks

### Debugging PDF Issues

```python
# Extract and save PDF text for inspection
pdf_text = PDFDataExtractor.extract_text(pdf_bytes)
with open('/tmp/pdf_debug.txt', 'w') as f:
    f.write(pdf_text)

# Search PDF manually
import re
if re.search(r'45\s*,?\s*83\s*,?\s*719', pdf_text):
    print("Found with flexible spacing")
```

### Debugging Excel Issues

```python
# Print all worksheet values
worksheet = workbook['Ledger Detail']
for row in range(1, 20):  # First 20 rows
    for col in range(1, 10):  # First 10 columns
        cell = worksheet.cell(row=row, column=col)
        if cell.value:
            print(f"{cell.coordinate}: {cell.value} (type: {type(cell.value).__name__})")
```

### Asserting on Multiple Outputs

```python
# Check values across all three outputs
outputs = {
    'api': api_summary['purchase_bill'],
    'pdf': pdf_text,  # Would need to parse
    'excel': workbook  # Would need to extract
}

# Ensure all non-None
assert all(v for v in outputs.values()), "Missing output data"

# Parity check
assert outputs['api'] == expected_value, f"API mismatch: {outputs['api']}"
```

---

## Best Practices

✅ **Do:**
- Use utilities for consistent extraction logic
- Test against multiple output formats
- Check both value and precision
- Assert all required fields present
- Skip tests gracefully if data unavailable

❌ **Don't:**
- Hardcode cell references (use `find_value_in_worksheet`)
- Assume PDF format (search with multiple formats)
- Compare floats directly (use Decimal)
- Ignore decimal precision differences
- Assume fields exist without asserting first

---

## Further Reading

- `PARITY_TESTING_GUIDE.md` — How to run and extend tests
- `PARITY_TEST_FRAMEWORK_SUMMARY.md` — Architecture and design
- `test_ui_pdf_excel_parity_golden.py` — Complete working example
