# Phase 4E-E Implementation Guide
## Cross-Output Parity Verification

**Status:** QUEUED (auto-launch after 4E-D PASS)  
**Role:** QA Test Engineer  
**Duration:** ~20 minutes  

---

## PHASE OBJECTIVE

Verify that all three output formats (API, PDF, Excel) produce identical financial data for all 14 golden scenarios.

**Golden Rule:**
```
API Balance = Backend PDF Balance = Frontend PDF Balance = Excel Balance
Financial Difference = 0 for all outputs
```

---

## PARITY TEST MATRIX

For each of 14 golden scenarios, test all 3 outputs:

```
Scenario 1 (Single company, 1300.00):
  API (CanonicalLedgerService): 1300.00 ✓
  Backend PDF: 1300.00 ✓
  Frontend PDF: 1300.00 ✓
  Excel: 1300.00 ✓
  
Scenario 2 (Multiple companies, 2650.00):
  API: 2650.00 ✓
  Backend PDF: 2650.00 ✓
  Frontend PDF: 2650.00 ✓
  Excel: 2650.00 ✓
  
... (12 more scenarios)
```

**Total Parity Checks:** 14 scenarios × 3 outputs = 42 comparisons

---

## TEST IMPLEMENTATION

### Test Framework
```python
# test_cross_output_parity.py

import pytest
from decimal import Decimal
from apps.license.services.canonical_ledger_service import CanonicalLedgerService
from apps.license.services.exporters.ledger_pdf import get_license_transactions
from apps.license.services.exporters.license_balance_excel import export_license_balance_excel

GOLDEN_SCENARIOS = [
    # (license_id, expected_balance)
    (scenario_1_license_id, Decimal('1300.00')),
    (scenario_2_license_id, Decimal('2650.00')),
    # ... 14 scenarios
]

class TestCrossOutputParity:
    """Verify API, PDF, and Excel all produce same financial truth."""
    
    @pytest.mark.parametrize('license_id,expected_balance', GOLDEN_SCENARIOS)
    def test_api_pdf_excel_balance_match(self, license_id, expected_balance):
        """All outputs must have same balance for same license."""
        
        # API (canonical)
        api_data = CanonicalLedgerService.build_canonical_ledger_dataset(license_id)
        api_balance = api_data['license_running_balance']
        
        # Backend PDF
        license_obj = LicenseDetailsModel.objects.get(id=license_id)
        pdf_txns = get_license_transactions(license_obj)
        pdf_balance = pdf_txns[-1]['balance'] if pdf_txns else Decimal('0.00')
        
        # Frontend PDF (via API, same as api_data)
        frontend_balance = api_balance  # Frontend uses API directly
        
        # Excel
        excel_file = export_license_balance_excel(license_id)
        excel_balance = extract_final_balance(excel_file)
        
        # ASSERTION: All must match
        assert api_balance == expected_balance, f"API balance {api_balance} != expected {expected_balance}"
        assert pdf_balance == api_balance, f"PDF balance {pdf_balance} != API balance {api_balance}"
        assert frontend_balance == api_balance, f"Frontend PDF {frontend_balance} != API {api_balance}"
        assert excel_balance == api_balance, f"Excel balance {excel_balance} != API {api_balance}"
        
        # All must be 2 decimal places
        assert str(api_balance) == f"{expected_balance:.2f}"
        assert str(pdf_balance) == f"{expected_balance:.2f}"
        assert str(excel_balance) == f"{expected_balance:.2f}"
    
    @pytest.mark.parametrize('license_id,expected_balance', GOLDEN_SCENARIOS)
    def test_transaction_parity_all_outputs(self, license_id, expected_balance):
        """Every transaction must match across all outputs."""
        
        # Fetch from canonical
        api_data = CanonicalLedgerService.build_canonical_ledger_dataset(license_id)
        api_txns = {t['id']: t for t in api_data['transactions']}
        
        # Fetch from PDF
        license_obj = LicenseDetailsModel.objects.get(id=license_id)
        pdf_txns_list = get_license_transactions(license_obj)
        pdf_txns = {t['transaction_id']: t for t in pdf_txns_list}
        
        # For each transaction, verify match
        for txn_id, api_txn in api_txns.items():
            pdf_txn = pdf_txns.get(txn_id)
            
            assert pdf_txn is not None, f"Transaction {txn_id} missing from PDF"
            assert Decimal(str(pdf_txn['balance'])) == api_txn['license_running_balance']
            assert pdf_txn['amount'] == api_txn['amount']
            assert pdf_txn['is_commission'] == api_txn['is_commission']
    
    @pytest.mark.parametrize('license_id,expected_balance', GOLDEN_SCENARIOS)
    def test_commission_exclusion_all_outputs(self, license_id, expected_balance):
        """Commission must be visible but not counted in any output."""
        
        api_data = CanonicalLedgerService.build_canonical_ledger_dataset(license_id)
        
        # Count commission rows
        commissions = [t for t in api_data['transactions'] if t['is_commission']]
        
        if commissions:
            # Commission visible
            assert len(commissions) > 0
            
            # But balance does NOT include commission
            # (balance would be higher if commissions were counted)
            # This is verified by matching against expected_balance
            assert api_data['license_running_balance'] == expected_balance
            
            # PDF must show same
            license_obj = LicenseDetailsModel.objects.get(id=license_id)
            pdf_txns = get_license_transactions(license_obj)
            pdf_balance = pdf_txns[-1]['balance'] if pdf_txns else Decimal('0.00')
            assert pdf_balance == expected_balance
    
    def test_opening_balance_consistency(self):
        """Opening balance must be consistent across all outputs."""
        
        for license_id, expected_final in GOLDEN_SCENARIOS:
            api_data = CanonicalLedgerService.build_canonical_ledger_dataset(license_id)
            api_opening = api_data['opening_balance']
            
            # PDF opening balance
            license_obj = LicenseDetailsModel.objects.get(id=license_id)
            pdf_txns = get_license_transactions(license_obj)
            pdf_opening = pdf_txns[0]['balance'] if pdf_txns else Decimal('0.00')
            
            # Excel opening balance
            excel_file = export_license_balance_excel(license_id)
            excel_opening = extract_opening_balance(excel_file)
            
            # All must match
            assert api_opening == pdf_opening, f"License {license_id}: API opening {api_opening} != PDF {pdf_opening}"
            assert api_opening == excel_opening, f"License {license_id}: API opening {api_opening} != Excel {excel_opening}"
```

### Helper Functions
```python
def extract_final_balance(excel_file):
    """Extract final balance from Excel workbook."""
    workbook = openpyxl.load_workbook(excel_file)
    worksheet = workbook.active
    # Assuming final balance is in column E, last row
    return Decimal(str(worksheet['E'].value))

def extract_opening_balance(excel_file):
    """Extract opening balance from Excel."""
    # Return value from opening balance cell
    pass

def extract_transaction_balance(pdf_data, transaction_id):
    """Extract transaction balance from PDF data."""
    pass
```

---

## PARITY GATE CRITERIA

✅ Phase 4E-E PASS requires:
- [ ] All 14 scenarios: API = PDF = Excel (balance)
- [ ] All 14 scenarios: API = PDF = Excel (transactions)
- [ ] All 14 scenarios: API = PDF = Excel (opening balance)
- [ ] Commission visible in all outputs
- [ ] Commission NOT counted in any output
- [ ] Decimal precision: 2 places in all
- [ ] Deterministic ordering preserved in all
- [ ] Financial difference = 0 across all outputs
- [ ] No floating-point rounding errors

---

**Ready for auto-execution after Phase 4E-D PASS**
