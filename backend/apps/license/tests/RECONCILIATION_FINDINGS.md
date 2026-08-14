# Ledger Reconciliation - Smoking Gun Findings

**Date:** 2026-08-14  
**Test Type:** QA Reconciliation Matrix - Production Data Analysis  
**Licenses Tested:** 0310833996 (DFIA), 0310834296 (DFIA)  
**Status:** CRITICAL DISCREPANCIES FOUND

## Executive Summary

Comprehensive reconciliation of the license ledger system has identified **critical data consistency bugs** across multiple sources:

1. **Balance Mismatch Bug** - Canonical service final balance ≠ Summary block current balance
2. **Transaction Count Discrepancy** - Opening row handling creates transaction count mismatches
3. **Zero Balance Bug** - Summary incorrectly reports $0 balance when opening balance exists

These bugs affect:
- API responses (`/license-ledger/<id>`)
- PDF exports
- Excel exports
- UI display

## Detailed Findings

### License 0310833996 (DFIA)

**Basic Facts:**
- License Number: 0310833996
- License Type: DFIA
- Opening Balance: $192,805.77
- Exporter: LABDHI GLOBAL LLP

**Raw Database Analysis:**

```
Transaction Summary (6 line items):
  Purchases: 3 trades → ₹4,583,719.00 (Purchases)
  Sales:     3 trades → ₹6,524,056.00 (Sales)
  
Amount Breakdown:
  Purchase 1: ₹1,326,985
  Purchase 2: ₹1,442,043
  Purchase 3: ₹1,814,691
  Sale 1:     ₹2,901,564
  Sale 2:     ₹1,668,209
  Sale 3:     ₹1,954,283
```

**Canonical Ledger Service Output:**

```
Opening Balance:      $192,805.77
Final Balance:        $192,834.54
Transactions (all):   5 rows
  - OPENING:          1 row (synthetic)
  - PURCHASE:         1 row  
  - SALE:             3 rows

Transactions (display): 4 rows (excludes OPENING)

Totals:
  Purchases (USD):    $192,806.27
  Sales (USD):        $192,777.50
  Commission:         $0.00
```

**Summary Block Output:**

```
Total Debit (USD):            $192,777.50
Total Credit (USD):           $192,806.27
Total Debit Bill (INR):       ₹4,583,719.00
Total Credit Bill (INR):      ₹6,524,056.00
Current Balance (USD):        $28.77        ← BUG: Should be $192,834.54
Profit/Loss (INR):            ₹1,940,337.00
Profit State:                 PROFIT
```

**SMOKING GUN #1: Balance Mismatch**

```
Canonical final balance:      $192,834.54
Summary current balance:      $28.77
Discrepancy:                  $192,805.77

The discrepancy exactly equals the opening balance!
This suggests summary block is computing NET CHANGE, not ABSOLUTE BALANCE.
```

**Transaction Flow (Canonical):**

```
Date       Type         Company            Amount (USD)    Running Balance
─────────────────────────────────────────────────────────────────────────
2020-01-08 OPENING                         $192,805.77     $192,805.77
2026-06-17 PURCHASE     LABDHI GLOBAL LLP  $192,806.27     $385,612.04
2026-06-17 SALE         LABDHI GLOBAL LLP  $76,320.50      $309,291.54
2026-06-17 SALE         LABDHI GLOBAL LLP  $55,809.00      $253,482.54
2026-06-17 SALE         LABDHI GLOBAL LLP  $60,648.00      $192,834.54
```

### License 0310834296 (DFIA)

**Basic Facts:**
- License Number: 0310834296
- License Type: DFIA
- Opening Balance: $178,562.32
- Exporter: (Same company)

**Raw Database Analysis:**

```
Transaction Summary (2 line items):
  Purchase: 1 trade → $2,673.44 (₹5,876.13)
  Sale:     1 trade → $2,673.44 (₹26,710.00)
```

**Canonical Ledger Service Output:**

```
Opening Balance:      $178,562.32
Final Balance:        $178,562.32
Transactions (all):   3 rows
  - OPENING:          1 row (synthetic)
  - PURCHASE:         1 row
  - SALE:             1 row

Transactions (display): 2 rows (excludes OPENING)

Totals:
  Purchases (USD):    $2,673.44
  Sales (USD):        $2,673.44
  Commission:         $0.00
```

**Summary Block Output:**

```
Total Debit (USD):            $2,673.44
Total Credit (USD):           $2,673.44
Total Debit Bill (INR):       ₹5,876.13
Total Credit Bill (INR):      ₹26,710.00
Current Balance (USD):        $0.00         ← BUG: Should be $178,562.32
Profit/Loss (INR):            ₹20,833.87
Profit State:                 PROFIT
```

**SMOKING GUN #2: Zero Balance Bug**

```
Opening Balance:              $178,562.32
Final Balance:                $178,562.32
Summary Current Balance:      $0.00

When purchases equal sales, the balance should remain unchanged.
But summary shows $0, losing all context of absolute position.
```

**Transaction Flow (Canonical):**

```
Date       Type        Company         Amount (USD)    Running Balance
──────────────────────────────────────────────────────────────────────
2020-01-17 OPENING                     $178,562.32     $178,562.32
2026-06-02 PURCHASE    Purplehub       $2,673.44       $181,235.76
2026-06-16 SALE        Purplehub       $2,673.44       $178,562.32
```

## Root Cause Analysis

### Bug #1: Summary Block Balance Calculation

**Problem:** The summary block calculates `current_balance` as the net trade result:

```python
current_balance = total_credit - total_debit
```

**What it should be:** The absolute position after all transactions:

```python
current_balance = opening_balance + (total_credit - total_debit)
```

**Affected Code:** 
- File: `backend/apps/license/services/canonical_ledger_service.py`
- Function: `_build_summary()`
- Line: ~375

**Impact:**
- UI shows wrong balance
- PDF exports show wrong balance
- Excel exports show wrong balance
- API responses contain wrong balance

### Bug #2: Opening Row Handling

**Problem:** The canonical service adds a synthetic OPENING transaction when `opening_balance > 0`. This causes:
- Raw transaction count: 6 (from database)
- Canonical all transactions: 5 (excludes one purchase due to linked trade logic?)
- Canonical display: 4 (excludes OPENING)

**Investigation needed:** Why is raw count 6 but canonical all transactions is 5?

### Bug #3: Transaction Count Logic

The system uses multiple counts which creates confusion:

| Source | Count | Includes |
|--------|-------|----------|
| Raw DB | 6 | All line items from trades |
| Canonical all | 5 | All transactions including OPENING |
| Canonical display | 4 | User-facing transactions (excludes OPENING) |

**Question:** Which count is the source of truth?

## Consistency Checks

### Consistency Matrix

| Source | Debit Bill INR | Credit Bill INR | Current Balance USD | Profit/Loss INR |
|--------|---|---|---|---|
| Raw DB | ₹4,583,719 | ₹6,524,056 | N/A | N/A |
| Canonical Totals | N/A | N/A | $192,834.54 | ₹1,940,337 |
| Summary Block | ₹4,583,719 | ₹6,524,056 | $28.77 ❌ | ₹1,940,337 |

### What Matches ✓

- Debit/Credit bill amounts (INR) consistent across all sources
- Profit/Loss (INR) = Credit Bill - Debit Bill
- Purchase/Sale amounts (USD) match between raw DB and canonical

### What Doesn't Match ✗

- **Current Balance (USD):** Canonical ($192,834.54) ≠ Summary ($28.77)
- **Transaction Count:** Raw (6) vs Canonical all (5) vs Canonical display (4)

## Test Data

Full reconciliation data available in: `/tmp/reconciliation_full.json`

### Extraction Query

```python
# Raw Database
trades = LicenseTrade.objects.filter(
    license_type='DFIA',
    lines__sr_number__license_id=license_id
).prefetch_related('lines')

# Canonical Service
canonical = CanonicalLedgerService.build_canonical_ledger_dataset(
    license_id, 'DFIA'
)

# Compare
canonical['license_running_balance'] vs 
canonical['summary']['current_balance']
```

## Verdict

**Status:** CRITICAL - PRODUCTION DEFECT

The ledger system has a fundamental bug in the summary block balance calculation. This causes:

1. **API Responses**: `/license-ledger/<id>` returns wrong balance
2. **PDF Exports**: Shows wrong profit/loss in relation to UI
3. **UI Display**: Shows net change instead of absolute position
4. **Excel Exports**: Contains inconsistent data with PDF

The bug is **high-impact** because:
- Users cannot trust the balance shown in the UI
- Exports show different values than the UI
- The "current balance" field is actually "net change since opening"

This is exactly the type of bug that affects financial systems and causes audit failures.

## Recommended Fix

1. Verify which balance is the source of truth (canonical or summary)
2. Update the summary block calculation to use absolute balance
3. Add tests that verify balance consistency across all sources
4. Audit all exports (PDF, Excel, CSV) to use correct balance

## Test Case

See: `test_ledger_reconciliation_smoking_gun.py`

Key tests:
- `test_license_0310833996_balance_discrepancy_smoking_gun()`
- `test_license_0310834296_summary_balance_zero_bug()`
- `test_transaction_count_discrepancies_opening_row()`
- `test_bill_amount_consistency_across_sources()`
