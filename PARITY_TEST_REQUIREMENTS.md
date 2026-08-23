# Parity Test Requirements — License Manager

**Objective:** Verify transaction-level and financial parity across three outputs:
- **UI** — CanonicalLedgerService (API response)
- **PDF** — Backend PDF exporter
- **Excel** — Balance Excel exporter

---

## SECTION 1: GOLDEN LICENSE CASE

### 1.1 Golden Case Identity
- **License Number:** 0310833996
- **Status:** Production license with confirmed transaction history
- **Purpose:** Baseline verification that all outputs reconcile for a real license

### 1.2 Golden Expected Totals (₹ INR)

| Metric | Expected Value |
|--------|----------------|
| **Total Purchase** | ₹45,83,719.00 |
| **Total Sale** | ₹65,24,056.00 |
| **Profit (Sale - Purchase)** | ₹19,40,337.00 |

### 1.3 Measurement Method

1. **Load UI API response** for license 0310833996
   - Endpoint: `GET /api/licenses/0310833996/ledger/`
   - Extract `summary.total_credit_bill` (Purchase INR)
   - Extract `summary.total_debit_bill` (Sale INR)
   - Extract `summary.total_profit_loss` (Profit)
   - Count transactions in `display_transactions[]`

2. **Generate PDF export** for license 0310833996
   - Endpoint: `GET /api/licenses/0310833996/ledger-pdf/`
   - Extract transaction list from PDF
   - Sum all purchase amounts (INR)
   - Sum all sale amounts (INR)
   - Calculate final balance (Profit)

3. **Generate Excel export** for license 0310833996
   - Endpoint: `GET /api/licenses/0310833996/balance-excel/`
   - Read "Financial Ledger" sheet
   - Extract all transaction rows
   - Sum totals from summary row
   - Verify all transactions appear

---

## SECTION 2: TRANSACTION-LEVEL PARITY

### 2.1 Transaction Table Parity

**Requirement:** Every transaction must appear identically in all three outputs.

#### Parity Matrix (for each transaction)
| Field | UI | PDF | Excel | Match? |
|-------|----|----|-------|--------|
| Transaction ID (SR Number) | ✓ | ✓ | ✓ | YES |
| Transaction Date | ✓ | ✓ | ✓ | YES |
| Type (PURCHASE / SALE) | ✓ | ✓ | ✓ | YES |
| Company Name | ✓ | ✓ | ✓ | YES |
| Amount (INR) | ✓ | ✓ | ✓ | YES |
| Is Commission | ✓ | ✓ | ✓ | YES |
| Running Balance | ✓ | ✓ | ✓ | YES |

### 2.2 Transaction Count Parity
```
UI transaction_count == PDF transaction_count == Excel transaction_count
```

For license 0310833996:
- All three sources must show the same number of non-commission transactions
- Commission transactions must be consistently excluded or flagged

### 2.3 Transaction Ordering Parity
```
UI order == PDF order == Excel order
```
- Transactions sorted by `invoice_date` ascending
- Same-date transactions ordered by `sr_number` ascending
- First transaction must be the same in all three outputs

---

## SECTION 3: FINANCIAL TOTALS PARITY

### 3.1 Purchase Total Parity
```
UI.purchase_inr == PDF.purchase_inr == Excel.purchase_inr == ₹45,83,719.00
```

**Definition:** Sum of all PURCHASE transactions (non-commission, non-linked)

### 3.2 Sale Total Parity
```
UI.sale_inr == PDF.sale_inr == Excel.sale_inr == ₹65,24,056.00
```

**Definition:** Sum of all SALE transactions (non-commission, non-linked)

### 3.3 Profit Total Parity
```
UI.profit_inr == PDF.profit_inr == Excel.profit_inr == ₹19,40,337.00
```

**Formula:** `Profit = Sale - Purchase`

### 3.4 Decimal Precision Parity
```
All amounts display with exactly 2 decimal places.
UI: "45,83,719.00"
PDF: "45,83,719.00"
Excel: "45,83,719.00"
```

---

## SECTION 4: FORBIDDEN VALUES

**Critical:** These USD values must NEVER appear in INR outputs.

| Forbidden USD Value | Reason |
|-------------------|--------|
| 1,92,806.27 | USD conversion artifact |
| 76,320.50 | USD conversion artifact |
| 55,809.00 | USD conversion artifact |
| 60,648.00 | USD conversion artifact |

**Assertion:**
```python
assert "1,92,806.27" not in pdf_text
assert "76,320.50" not in pdf_text
assert "55,809.00" not in pdf_text
assert "60,648.00" not in pdf_text

assert "1,92,806.27" not in excel_values
assert "76,320.50" not in excel_values
assert "55,809.00" not in excel_values
assert "60,648.00" not in excel_values
```

**If found:** Report as CRITICAL DEFECT — currency conversion bug.

---

## SECTION 5: TEST STRUCTURE & IMPLEMENTATION

### 5.1 Test File Location
```
backend/apps/license/tests/test_golden_parity_0310833996.py
```

### 5.2 Test Class Structure
```python
class TestGoldenParityLicense0310833996(TestCase):
    """Golden case parity verification."""
    
    def setUp(self):
        """Load license and prepare test data."""
        self.license = LicenseDetailsModel.objects.get(license_number='0310833996')
        self.license_id = self.license.id
    
    def test_golden_ui_totals(self):
        """Verify UI returns correct totals."""
        data = CanonicalLedgerService.build_canonical_ledger_dataset(self.license_id, 'DFIA')
        summary = data['summary']
        
        assert_decimal_equal(summary['total_credit_bill'], Decimal('4583719.00'), 'Purchase')
        assert_decimal_equal(summary['total_debit_bill'], Decimal('6524056.00'), 'Sale')
        assert_decimal_equal(summary['total_profit_loss'], Decimal('1940337.00'), 'Profit')
    
    def test_golden_pdf_totals(self):
        """Verify PDF exporter returns correct totals."""
        pdf_data = extract_pdf_totals(self.license_id)
        
        assert_decimal_equal(pdf_data['purchase_inr'], Decimal('4583719.00'), 'PDF Purchase')
        assert_decimal_equal(pdf_data['sale_inr'], Decimal('6524056.00'), 'PDF Sale')
        assert_decimal_equal(pdf_data['profit_inr'], Decimal('1940337.00'), 'PDF Profit')
    
    def test_golden_excel_totals(self):
        """Verify Excel exporter returns correct totals."""
        excel_data = extract_excel_totals(self.license_id)
        
        assert_decimal_equal(excel_data['purchase_inr'], Decimal('4583719.00'), 'Excel Purchase')
        assert_decimal_equal(excel_data['sale_inr'], Decimal('6524056.00'), 'Excel Sale')
        assert_decimal_equal(excel_data['profit_inr'], Decimal('1940337.00'), 'Excel Profit')
    
    def test_golden_transaction_count_parity(self):
        """Verify all outputs show same transaction count."""
        ui_count = len(CanonicalLedgerService.build_canonical_ledger_dataset(
            self.license_id, 'DFIA')['display_transactions'])
        pdf_count = count_pdf_transactions(self.license_id)
        excel_count = count_excel_transactions(self.license_id)
        
        self.assertEqual(ui_count, pdf_count, 
            f"Transaction count mismatch: UI={ui_count}, PDF={pdf_count}")
        self.assertEqual(ui_count, excel_count, 
            f"Transaction count mismatch: UI={ui_count}, Excel={excel_count}")
    
    def test_golden_transaction_ids_match(self):
        """Verify transaction IDs are identical across outputs."""
        ui_ids = get_ui_transaction_ids(self.license_id)
        pdf_ids = get_pdf_transaction_ids(self.license_id)
        excel_ids = get_excel_transaction_ids(self.license_id)
        
        self.assertEqual(set(ui_ids), set(pdf_ids), 
            f"Transaction ID mismatch: UI={len(ui_ids)}, PDF={len(pdf_ids)}")
        self.assertEqual(set(ui_ids), set(excel_ids), 
            f"Transaction ID mismatch: UI={len(ui_ids)}, Excel={len(excel_ids)}")
    
    def test_forbidden_usd_values_not_in_pdf(self):
        """Verify USD conversion artifacts do not appear in PDF."""
        pdf_text = generate_and_read_pdf(self.license_id)
        
        forbidden = ['1,92,806.27', '76,320.50', '55,809.00', '60,648.00']
        for value in forbidden:
            self.assertNotIn(value, pdf_text, 
                f"Forbidden USD value {value} found in PDF")
    
    def test_forbidden_usd_values_not_in_excel(self):
        """Verify USD conversion artifacts do not appear in Excel."""
        excel_workbook = generate_and_read_excel(self.license_id)
        excel_text = str(excel_workbook.values)
        
        forbidden = ['1,92,806.27', '76,320.50', '55,809.00', '60,648.00']
        for value in forbidden:
            self.assertNotIn(value, excel_text, 
                f"Forbidden USD value {value} found in Excel")
```

### 5.3 Helper Functions

```python
def assert_decimal_equal(actual, expected, field_name):
    """Assert decimal values match with 2dp precision."""
    actual_dec = Decimal(str(actual)).quantize(Decimal('0.01'))
    expected_dec = Decimal(str(expected)).quantize(Decimal('0.01'))
    assert actual_dec == expected_dec, \
        f"{field_name}: {actual_dec} != {expected_dec}"

def extract_pdf_totals(license_id):
    """Extract purchase, sale, profit from PDF."""
    # Implementation: Call PDF exporter, parse PDF, extract values
    pass

def extract_excel_totals(license_id):
    """Extract purchase, sale, profit from Excel."""
    # Implementation: Call Excel exporter, read workbook, extract values
    pass

def count_pdf_transactions(license_id):
    """Count non-commission transactions in PDF."""
    # Implementation: Parse PDF, count rows
    pass

def count_excel_transactions(license_id):
    """Count non-commission transactions in Excel."""
    # Implementation: Read Excel sheet, count rows
    pass

def get_ui_transaction_ids(license_id):
    """Get list of transaction IDs (SR Numbers) from UI."""
    data = CanonicalLedgerService.build_canonical_ledger_dataset(license_id, 'DFIA')
    return [t['id'] for t in data['display_transactions']]

def get_pdf_transaction_ids(license_id):
    """Get list of transaction IDs from PDF."""
    # Implementation: Parse PDF, extract SR numbers
    pass

def get_excel_transaction_ids(license_id):
    """Get list of transaction IDs from Excel."""
    # Implementation: Read Excel, extract SR numbers
    pass

def generate_and_read_pdf(license_id):
    """Generate PDF and return as text."""
    # Implementation: Call PDF exporter, convert to text
    pass

def generate_and_read_excel(license_id):
    """Generate Excel and return workbook object."""
    # Implementation: Call Excel exporter, load workbook
    pass
```

---

## SECTION 6: PARITY ASSERTIONS CHECKLIST

### Financial Totals (Primary Gates)
- [ ] UI Purchase INR = ₹45,83,719.00
- [ ] UI Sale INR = ₹65,24,056.00
- [ ] UI Profit INR = ₹19,40,337.00
- [ ] PDF Purchase INR = ₹45,83,719.00
- [ ] PDF Sale INR = ₹65,24,056.00
- [ ] PDF Profit INR = ₹19,40,337.00
- [ ] Excel Purchase INR = ₹45,83,719.00
- [ ] Excel Sale INR = ₹65,24,056.00
- [ ] Excel Profit INR = ₹19,40,337.00

### Transaction-Level Parity
- [ ] UI transaction count == PDF transaction count == Excel transaction count
- [ ] UI transaction IDs ⊂ PDF transaction IDs (exact match)
- [ ] UI transaction IDs ⊂ Excel transaction IDs (exact match)
- [ ] UI transaction order == PDF transaction order == Excel transaction order
- [ ] Every transaction shows same date in all three outputs
- [ ] Every transaction shows same amount (INR) in all three outputs
- [ ] Every transaction shows same company in all three outputs

### Data Quality
- [ ] All amounts have exactly 2 decimal places
- [ ] No USD conversion artifacts in PDF
- [ ] No USD conversion artifacts in Excel
- [ ] No rounding errors > 0.01 INR
- [ ] Commission transactions excluded from all three outputs
- [ ] Linked transactions handled consistently

### Edge Cases
- [ ] Opening balance (if present) shown correctly in all three
- [ ] Zero-amount transactions handled identically
- [ ] Same-date transactions maintain deterministic order
- [ ] Large datasets (100+ txns) parse correctly in all outputs
- [ ] Empty ledger (no transactions) returns 0.00 in all outputs

---

## SECTION 7: PASS/FAIL CRITERIA

### PASS Condition
```
All 14 assertions pass AND
all transaction-level checks pass AND
no forbidden USD values detected AND
decimal precision = 2dp in all outputs AND
transaction counts match across all three sources
```

### FAIL Condition
```
Any assertion fails OR
USD conversion artifacts detected OR
Decimal precision < 2dp OR
Transaction counts diverge OR
Transaction IDs mismatch
```

### Report Format
```
PARITY TEST RESULT FOR LICENSE 0310833996
========================================

UI Totals:      Purchase ₹45,83,719.00 | Sale ₹65,24,056.00 | Profit ₹19,40,337.00
PDF Totals:     Purchase ₹45,83,719.00 | Sale ₹65,24,056.00 | Profit ₹19,40,337.00
Excel Totals:   Purchase ₹45,83,719.00 | Sale ₹65,24,056.00 | Profit ₹19,40,337.00

Transaction Counts:
  UI:     [N] transactions
  PDF:    [N] transactions
  Excel:  [N] transactions
  Match:  YES

Forbidden USD Values:
  PDF:    NONE FOUND ✓
  Excel:  NONE FOUND ✓

Decimal Precision:
  UI:     2dp ✓
  PDF:    2dp ✓
  Excel:  2dp ✓

VERDICT: PASS ✓
```

---

## SECTION 8: TEST EXECUTION

### Run Command
```bash
./run-tests.sh backend/apps/license/tests/test_golden_parity_0310833996.py
```

### Expected Output
```
test_golden_ui_totals ... ok
test_golden_pdf_totals ... ok
test_golden_excel_totals ... ok
test_golden_transaction_count_parity ... ok
test_golden_transaction_ids_match ... ok
test_forbidden_usd_values_not_in_pdf ... ok
test_forbidden_usd_values_not_in_excel ... ok

Ran 7 tests in 0.523s
OK
```

---

## SECTION 9: DEPENDENCIES & DATA

### Required Systems
- License 0310833996 must exist in database with transaction history
- CanonicalLedgerService must return valid dataset
- PDF exporter must be functional
- Excel exporter must be functional
- All three systems must have access to the same underlying trade/transaction data

### Data Integrity Assumptions
- License 0310833996 transaction history is immutable (production fixture)
- Expected totals are confirmed as accurate
- All transactions are linked to license 0310833996
- No filtering or display rules change totals
- Currency conversions are consistent (INR only in outputs)

---

## SECTION 10: COVERAGE GAPS & FUTURE WORK

### What This Test Covers
✓ Golden case reconciliation (UI, PDF, Excel)
✓ Transaction-level parity (counts, IDs, order)
✓ Financial totals consistency
✓ Forbidden value detection (USD artifacts)
✓ Decimal precision verification

### What This Test Does NOT Cover
- Multi-license batch exports
- Date-range filtering parity
- Company-specific ledger parity
- SION norm calculations in exports
- Large dataset performance (100K+ txns)
- Concurrent access race conditions

### Recommended Follow-Up Tests
1. **Multi-license parity** — Run same test for 5 random licenses
2. **Date-range filtering** — Verify parity with date filters applied
3. **CSV export parity** — Add CSV export to the matrix
4. **Performance test** — Verify parity time <2s for 10K txns
5. **Stress test** — Verify parity with 100K+ transactions

---

## APPENDIX A: REFERENCE SCRIPTS

### Script 1: Extract API Totals
```python
from apps.license.models import LicenseDetailsModel
from apps.license.services.canonical_ledger_service import CanonicalLedgerService

license = LicenseDetailsModel.objects.get(license_number='0310833996')
data = CanonicalLedgerService.build_canonical_ledger_dataset(license.id, 'DFIA')
summary = data['summary']

print(f"Purchase: {summary['total_credit_bill']}")
print(f"Sale: {summary['total_debit_bill']}")
print(f"Profit: {summary['total_profit_loss']}")
```

### Script 2: Verify Golden Values in DB
```python
from decimal import Decimal
from apps.license.models import LicenseDetailsModel
from apps.license.services.license_profit import profit_for_licenses

license = LicenseDetailsModel.objects.get(license_number='0310833996')
profit_data = profit_for_licenses([license.id]).get(license.id)

print(f"DB Purchase: {profit_data['purchase_amount']}")
print(f"DB Sale: {profit_data['sale_amount']}")
print(f"DB Profit: {profit_data['profit_loss']}")
```

---

**Document Version:** 1.0  
**Last Updated:** 2026-08-14  
**Status:** ACTIVE — Test implementation required
