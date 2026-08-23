# Phase 4E-D Implementation Guide
## Excel Export Canonical Migration

**Status:** QUEUED (auto-launch after 4E-C PASS)  
**Role:** Backend Engineer + Implementation Agent  
**Duration:** ~20 minutes  

---

## PHASE OBJECTIVE

Migrate backend Excel exporter to consume `CanonicalLedgerService` instead of independent balance calculation.

**Golden Rule:**
```
Excel = Canonical Data + Formatting
No Excel-specific financial logic.
```

---

## CURRENT STATE (Before)

File: `backend/apps/license/services/exporters/license_balance_excel.py`

Current logic:
- ✅ Fetches transaction data
- ❌ Recalculates running balance independently
- ❌ Per-company balance logic
- ❌ No commission handling verified
- ❌ Duplicate of canonical logic

---

## TARGET STATE (After)

```python
from apps.license.services.canonical_ledger_service import CanonicalLedgerService

def export_license_balance_excel(license_id, license_type='DFIA'):
    # Fetch canonical data (NOT independent calculation)
    canonical_data = CanonicalLedgerService.build_canonical_ledger_dataset(
        license_id=license_id,
        license_type=license_type
    )
    
    # Build Excel sheets from CANONICAL DATA
    # Do NOT recalculate balance, commission, totals
    
    return excel_workbook
```

---

## IMPLEMENTATION STEPS

### Step 1: Audit Current Implementation
```bash
grep -n "running_balance" backend/apps/license/services/exporters/license_balance_excel.py
grep -n "balance\s*+=" backend/apps/license/services/exporters/license_balance_excel.py
grep -n "balance\s*-=" backend/apps/license/services/exporters/license_balance_excel.py
```

**Action:** Identify and list all independent balance calculations.

### Step 2: Add Canonical Service Integration
```python
from apps.license.services.canonical_ledger_service import CanonicalLedgerService

def export_license_balance_excel(license_id, license_type='DFIA'):
    license_obj = get_license(license_id)
    
    # FETCH CANONICAL DATA (not independent)
    canonical_data = CanonicalLedgerService.build_canonical_ledger_dataset(
        license_id=license_id,
        license_type=license_type
    )
    
    # Build balance map: transaction_id → running_balance
    balance_map = {}
    for txn in canonical_data.get('transactions', []):
        balance_map[txn.get('id')] = txn.get('license_running_balance', Decimal('0.00'))
    
    # ... rest of Excel generation uses canonical data
    return build_excel_workbook(license_obj, canonical_data, balance_map)
```

### Step 3: Update Transaction Processing
```python
def build_excel_workbook(license_obj, canonical_data, balance_map):
    workbook = Workbook()
    worksheet = workbook.active
    
    # Headers
    worksheet['A1'] = 'Date'
    worksheet['B1'] = 'Type'
    worksheet['C1'] = 'Company'
    worksheet['D1'] = 'Amount'
    worksheet['E1'] = 'Balance'
    
    # Opening balance
    worksheet['E2'] = canonical_data.get('opening_balance')
    
    # Transactions from CANONICAL (not independent calc)
    row = 3
    for txn in canonical_data.get('transactions', []):
        worksheet[f'A{row}'] = txn.get('date')
        worksheet[f'B{row}'] = txn.get('type')
        worksheet[f'C{row}'] = txn.get('company_name')
        worksheet[f'D{row}'] = float(txn.get('amount', 0))
        
        # USE CANONICAL BALANCE (not recalculated)
        worksheet[f'E{row}'] = float(balance_map.get(txn.get('id'), 0))
        
        row += 1
    
    # Final balance from canonical (not sum of column)
    final_row = row + 1
    worksheet[f'E{final_row}'] = float(canonical_data.get('license_running_balance'))
    
    return workbook
```

### Step 4: Remove Independent Balance Logic
```python
# DELETE:
# - running_balance = 0
# - running_balance += amount
# - running_balance -= amount
# - balance recalculation loops
# - per-company balance tracking
# - commission handling (use canonical flag)

# KEEP:
# - Excel formatting
# - Column headers
# - Sheet organization
# - Style/colors
# - Export function signature
```

### Step 5: Test Parity
```python
# test_license_balance_excel.py

def test_excel_uses_canonical_balance():
    """Excel balance must match canonical, not independent calc."""
    license_id = 1
    
    # Get canonical balance
    canonical = CanonicalLedgerService.build_canonical_ledger_dataset(license_id)
    canonical_balance = canonical['license_running_balance']
    
    # Export Excel
    excel_file = export_license_balance_excel(license_id)
    excel_balance = extract_final_balance_from_excel(excel_file)
    
    # MUST match (zero financial difference)
    assert excel_balance == canonical_balance
    
    # Check each transaction
    for txn in canonical['transactions']:
        excel_txn_balance = extract_transaction_balance_from_excel(excel_file, txn['id'])
        canonical_txn_balance = txn['license_running_balance']
        assert excel_txn_balance == canonical_txn_balance
```

### Step 6: Verify Golden Scenarios
For all 14 golden scenarios:
- Scenario balance = Excel balance ✅
- Totals match ✅
- Commission visible but not counted ✅
- Opening balance correct ✅

---

## GATE CRITERIA

✅ Phase 4E-D PASS requires:
- [ ] No independent balance calculation
- [ ] All balance from CanonicalLedgerService
- [ ] All 14 golden scenarios match canonical
- [ ] Financial difference = 0
- [ ] Excel generates without errors
- [ ] Decimal precision: 2 places
- [ ] Commission handling correct
- [ ] Opening balance correct
- [ ] Company utilization shown
- [ ] Totals match canonical

---

**Ready for auto-execution after Phase 4E-C PASS**
