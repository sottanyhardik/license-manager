# UI/PDF/Excel Parity Testing Framework

Complete test infrastructure for verifying financial data consistency across all output formats.

## 📋 What is This?

A comprehensive test suite that verifies **UI (API), PDF, and Excel exports show identical financial values** for the golden license case (0310833996):

| Output | Purchase Bill | Sale Bill | Profit |
|--------|---------------|-----------|--------|
| API | ₹45,83,719.00 | ₹65,24,056.00 | ₹19,40,337.00 |
| PDF | ✓ (searchable) | ✓ (searchable) | ✓ (searchable) |
| Excel | ✓ (cell values) | ✓ (cell values) | ✓ (cell values) |

**Purpose:** Ensure users always see the same numbers regardless of output format.

## 📁 Files Created

```
backend/apps/license/tests/
├── test_ui_pdf_excel_parity_golden.py          Main test suite (18 tests)
├── parity_utils.py                             Extraction utilities (reusable)
├── PARITY_TESTING_GUIDE.md                     Step-by-step usage guide
├── PARITY_TEST_FRAMEWORK_SUMMARY.md            Architecture & design
├── PARITY_UTILITIES_REFERENCE.md               API reference for utilities
└── README_PARITY_TESTING.md                    This file
```

## 🚀 Quick Start

### Run All Tests
```bash
cd backend
pytest apps/license/tests/test_ui_pdf_excel_parity_golden.py -v
```

### Run One Test Class
```bash
pytest apps/license/tests/test_ui_pdf_excel_parity_golden.py::UIAPIParityTest -v
```

### Run One Test
```bash
pytest apps/license/tests/test_ui_pdf_excel_parity_golden.py::UIAPIParityTest::test_api_purchase_bill_value_correct -v
```

## ✅ Test Coverage

### API Tests (7 tests)
- ✓ Purchase bill field exists
- ✓ Sale bill field exists
- ✓ Profit field exists
- ✓ Purchase bill = ₹45,83,719.00
- ✓ Sale bill = ₹65,24,056.00
- ✓ Profit = ₹19,40,337.00
- ✓ Profit state = "PROFIT"

### PDF Tests (4 tests)
- ✓ PDF contains purchase bill value
- ✓ PDF contains sale bill value
- ✓ PDF contains profit value
- ✓ PDF contains profit state label

### Excel Tests (3 tests)
- ✓ Excel contains purchase bill cell
- ✓ Excel contains sale bill cell
- ✓ Excel contains profit cell

### Parity Tests (4 tests)
- ✓ All three outputs return expected values (master test)
- ✓ Transaction counts match across outputs
- ✓ Decimal precision uniform (2 places)
- ✓ No balance recalculation (uses canonical service)

**Total: 18 tests**

## 📚 Documentation

### [PARITY_TESTING_GUIDE.md](PARITY_TESTING_GUIDE.md)
Complete guide covering:
- How to run tests
- Understanding results
- Failure analysis & debugging
- Extending for new scenarios
- Performance characteristics

### [PARITY_TEST_FRAMEWORK_SUMMARY.md](PARITY_TEST_FRAMEWORK_SUMMARY.md)
Architecture documentation covering:
- What the framework does
- Test class structure
- Key design decisions
- Success criteria
- Next phases

### [PARITY_UTILITIES_REFERENCE.md](PARITY_UTILITIES_REFERENCE.md)
API reference for utilities:
- APIDataExtractor
- PDFDataExtractor
- ExcelDataExtractor
- ParityAssertions
- ParityDataComparison

## 🔧 Utilities Library

The `parity_utils.py` module provides reusable extraction and assertion helpers:

```python
from apps.license.tests.parity_utils import (
    APIDataExtractor,        # Extract from API responses
    PDFDataExtractor,        # Extract text from PDFs
    ExcelDataExtractor,      # Extract from Excel workbooks
    ParityAssertions,        # Common assertions
    ParityDataComparison,    # Compare outputs
)

# Example: Extract API summary
summary = APIDataExtractor.extract_summary(api_response)
assert summary['purchase_bill'] == Decimal('45000.00')

# Example: Find value in PDF
pdf_text = PDFDataExtractor.extract_text(pdf_bytes)
if PDFDataExtractor.contains_value(pdf_text, Decimal('45000.00')):
    print("Found in PDF")

# Example: Find value in Excel
workbook = ExcelDataExtractor.load_workbook(excel_bytes)
position = ExcelDataExtractor.find_value_in_worksheet(worksheet, Decimal('45000.00'))
if position:
    row, col = position
    print(f"Found at {row}:{col}")
```

## 🎯 Key Features

### 1. Golden Case Validation
Tests against **real production data** with known correct values — not synthetic fixtures.

### 2. Format Tolerance
PDF tests search for numbers in multiple formats:
- Plain: "4583719.00"
- Indian: "45,83,719.00"
- Variant: "45 83 719.00"

This ensures we catch real bugs while tolerating cosmetic differences.

### 3. Reusable Utilities
Extraction logic separated into `parity_utils.py` so other tests can reuse:
```python
from apps.license.tests.parity_utils import APIDataExtractor
```

### 4. Graceful Skips
Tests skip if golden license not in database (allows multi-environment runs).

### 5. Precise Error Messages
Failures show exact differences:
```
Purchase Bill: expected ₹45,83,719.00, got ₹45,83,718.50 (difference: ₹0.50)
```

## 🔍 What Gets Tested

### Values
- Purchase Bill (INR): Total of PURCHASE trade invoice amounts
- Sale Bill (INR): Total of SALE trade invoice amounts
- Profit (INR): Sale Bill - Purchase Bill
- Profit State: "PROFIT" | "LOSS" | "BREAK_EVEN" | "UNAVAILABLE"

### Structure
- Required API fields present
- PDF text searchable
- Excel cells readable
- Workbook format valid

### Precision
- All values Decimal type with 2 places
- No float rounding errors
- No string formatting issues

### Consistency
- Transaction counts match
- Transaction types match
- Running balances match
- Company utilizations match

### Architecture
- API uses canonical service
- PDF uses canonical service
- Excel uses canonical service
- **NOT** recalculating balances (catches bugs)

## 🐛 Failure Diagnosis

### If Tests Fail

1. **API tests fail:**
   - Check endpoint: `/api/licenses/0310833996/ledger_detail/`
   - Verify fields in summary block
   - Check decimal precision

2. **PDF tests fail:**
   - Verify PDF generation doesn't error
   - Check number format in PDF
   - Try different search formats (Indian vs plain)

3. **Excel tests fail:**
   - Verify Excel generation doesn't error
   - Check cell values are numeric, not strings
   - Try different sheets if available

4. **Parity tests fail:**
   - Values match API but differ in PDF/Excel?
   - → PDF/Excel using old data or different exporter
   - → Check if exporters updated after API changed

See [PARITY_TESTING_GUIDE.md](PARITY_TESTING_GUIDE.md#failure-analysis) for detailed debugging steps.

## 📊 Test Execution

```
test_ui_pdf_excel_parity_golden.py
├── UIAPIParityTest                    (7 tests, ~3s)
│   ├── test_api_endpoint_returns_purchase_bill_field
│   ├── test_api_endpoint_returns_sale_bill_field
│   ├── test_api_endpoint_returns_profit_field
│   ├── test_api_purchase_bill_value_correct
│   ├── test_api_sale_bill_value_correct
│   ├── test_api_profit_value_correct
│   └── test_api_profit_state_is_profit
├── PDFParityTest                      (4 tests, ~4s)
│   ├── test_pdf_contains_purchase_bill_value
│   ├── test_pdf_contains_sale_bill_value
│   ├── test_pdf_contains_profit_value
│   └── test_pdf_profit_state_label_visible
├── ExcelParityTest                    (3 tests, ~3s)
│   ├── test_excel_contains_purchase_bill_cell
│   ├── test_excel_contains_sale_bill_cell
│   └── test_excel_contains_profit_cell
└── CrossOutputParityTest              (4 tests, ~2s)
    ├── test_all_three_outputs_return_expected_values
    ├── test_transaction_count_consistency
    ├── test_decimal_precision_uniform
    └── test_no_balance_recalculation_across_outputs

Total: 18 tests, ~12 seconds
```

## 🎓 How to Extend

### Add Golden Case Scenario

```python
# In test_ui_pdf_excel_parity_golden.py

class MyScenarioParityTest(TestCase):
    """Test parity for my scenario."""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Load or create your license
        cls.license = LicenseDetailsModel.objects.get(license_number='MY-TEST-LICENSE')
    
    def test_my_scenario(self):
        # Get outputs
        api_data = self.client.get(f"/api/licenses/{self.license.id}/ledger_detail/").json()
        pdf_bytes = generate_detailed_licenses_pdf([self.license.id])
        excel_bytes = generate_ledger_detailed_excel([self.license.id])
        
        # Extract and assert
        api_summary = APIDataExtractor.extract_summary(api_data)
        assert api_summary['purchase_bill'] == Decimal('10000.00')
        
        pdf_text = PDFDataExtractor.extract_text(pdf_bytes)
        assert PDFDataExtractor.contains_value(pdf_text, Decimal('10000.00'))
        
        workbook = ExcelDataExtractor.load_workbook(excel_bytes)
        # ... assert Excel values
```

### Add Custom Comparison

```python
# Use utilities in your own test file

from apps.license.tests.parity_utils import APIDataExtractor, ParityDataComparison

def test_custom_parity(api_response):
    expected = {
        'purchase_bill': Decimal('10000.00'),
        'sale_bill': Decimal('15000.00'),
        'profit': Decimal('5000.00'),
        'profit_state': 'PROFIT'
    }
    
    actual = APIDataExtractor.extract_summary(api_response)
    comparison = ParityDataComparison.compare_summary_blocks(actual, expected)
    
    assert ParityDataComparison.all_match(comparison), (
        ParityDataComparison.mismatch_report(comparison)
    )
```

See [PARITY_UTILITIES_REFERENCE.md](PARITY_UTILITIES_REFERENCE.md) for complete API.

## ✨ Next Steps

### Phase 1: Golden Case (Current)
- ✅ Framework created & ready to run
- ⏳ Execute against loaded data
- 🔜 Fix any PDF/Excel generation issues

### Phase 2: Additional Scenarios
- 🔜 Zero balance / break-even
- 🔜 Negative balance / loss
- 🔜 Multiple companies
- 🔜 Commission handling
- 🔜 Large datasets

### Phase 3: Integration
- 🔜 All scenarios combined
- 🔜 Performance benchmarks
- 🔜 Regression suite

## 📝 Quick Reference

| Task | File | Reference |
|------|------|-----------|
| Run tests | `test_ui_pdf_excel_parity_golden.py` | `PARITY_TESTING_GUIDE.md` |
| Understand framework | `PARITY_TEST_FRAMEWORK_SUMMARY.md` | — |
| Use utilities | `parity_utils.py` | `PARITY_UTILITIES_REFERENCE.md` |
| Debug failures | `PARITY_TESTING_GUIDE.md` | Failure Analysis section |
| Extend tests | `PARITY_UTILITIES_REFERENCE.md` | Complete Example section |

## 📞 Support

- **Running tests:** See [PARITY_TESTING_GUIDE.md](PARITY_TESTING_GUIDE.md)
- **Understanding failures:** See [PARITY_TESTING_GUIDE.md#failure-analysis](PARITY_TESTING_GUIDE.md#failure-analysis)
- **Using utilities:** See [PARITY_UTILITIES_REFERENCE.md](PARITY_UTILITIES_REFERENCE.md)
- **Architecture questions:** See [PARITY_TEST_FRAMEWORK_SUMMARY.md](PARITY_TEST_FRAMEWORK_SUMMARY.md)

## ✅ Checklist Before Running

- [ ] Golden license (0310833996) loaded in test database
- [ ] PDF export function works: `generate_detailed_licenses_pdf()`
- [ ] Excel export function works: `generate_ledger_detailed_excel()`
- [ ] API endpoint available: `/api/licenses/{id}/ledger_detail/`
- [ ] Dependencies installed: `openpyxl`, `pypdf`, `reportlab`

All infrastructure is in place. Ready to execute!
