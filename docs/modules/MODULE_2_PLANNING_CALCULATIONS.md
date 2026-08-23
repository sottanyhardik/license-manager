# MODULE 2 — PLANNING CALCULATIONS INVENTORY

## Overview

This document consolidates every calculation performed during planning/auto-planning. Each entry includes:
- **Calculation name and context**
- **Formula (human-readable and code reference)**
- **Input variables and types**
- **Output type and precision**
- **Rounding behavior**
- **Source** (where the calculation is performed: canonical engine, duplicate, validation, presentation)
- **Evidence** (file:line)
- **Known issues** (defects, off-by-one errors, precision losses)

---

## 1. CATEGORY ALLOCATION (E1 / E5)

### 1.1 Category CIF Allocation
- **Calculation Type**: Financial (Category Waterfall)
- **Context**: E1/E5 planning engines allocate license balance_cif to item categories proportionally
- **Formula**:
  ```
  category_weight = sum(available_quantity for all items in category)
  category_share_of_cif = balance_cif × (category_weight / total_weight)
  category_unit_price = category_share_of_cif / category_weight
  ```
- **Input Variables**:
  - `balance_cif`: float (license's available CIF budget)
  - `category_weight`: float (sum of item quantities in category, Decimal in code)
  - `total_weight`: float (sum of all item quantities across all categories)
- **Output**: `category_unit_price` (float, rounded to 2 decimals)
- **Precision**: Decimal type during computation, rounded to 2 decimals for output
- **Rounding**: Via `_quantize()` helper (ROUND_HALF_UP rounding mode in code)
- **Per-Item Calculation**:
  ```
  per_item_planned_qty = item_available_qty
  per_item_unit_price = category_unit_price
  per_item_planned_cif = per_item_planned_qty × per_item_unit_price (rounded to 2 decimals)
  ```
- **Source**: Canonical (E1/E5 planning engines only)
- **Evidence**:
  - E1: `backend/apps/license/services/e1_plan.py:225-306` (plan_e1_items, _run_generic methods)
  - E5: `backend/apps/license/services/e5_plan.py:233-353` (_run_milk, _run_oils methods)
- **Confidence**: HIGH
- **Known Issues**: None

---

### 1.2 Item Remaining = Planned − Allotted
- **Calculation Type**: Quantity Tracking (Per-Item Remaining)
- **Context**: After creating a plan line, compute how much of that line can still be allocated
- **Formula**:
  ```
  item_remaining_quantity = max(item_planned_quantity - item_allotted_quantity, 0)
  item_remaining_cif = max(item_planned_cif - item_allotted_value, 0)
  ```
- **Input Variables**:
  - `item_planned_quantity`: float (from LicenseItemPlan.planned_quantity)
  - `item_allotted_quantity`: float (from LicenseImportItemsModel.allotted_quantity, maintained by signals)
  - `item_planned_cif`: float (from LicenseItemPlan.planned_cif_fc)
  - `item_allotted_value`: float (from LicenseImportItemsModel.allotted_value)
- **Output**: (remaining_qty, remaining_cif), both floats ≥ 0
- **Rounding**: No rounding (values already rounded in source fields)
- **Source**: Multiple locations (computed live in multiple contexts)
  - `norm_plan.py:effective_plan_for_license()` (lines 105-111)
  - `plan_enforcement.py:plan_status_for()` (lines 243-276)
  - `balance_calculator.py` (ledger balance calculation)
- **Evidence**:
  - `backend/apps/license/services/norm_plan.py:105-111`
  - `backend/apps/license/services/plan_enforcement.py:252-265`
- **Confidence**: HIGH
- **Known Issues**:
  - **BL-LEDGER-03**: `ItemBalanceCalculator.calculate_item_balance()` ignores sibling items' outstanding allotments in the zero-cif_fc branch
  - In this branch, debit = ENTIRE license's BOE total, not just this item's portion

---

## 2. QUANTITY FLOORING (E126 / E132 SPLIT)

### 2.1 Floor Quantity to Whole Number
- **Calculation Type**: Quantity Normalization (Planning Item Quantity)
- **Context**: E126/E132 auto-plan engines receive fractional split quantities and must floor them to whole units
- **Formula**:
  ```
  floored_qty = floor(raw_planned_quantity)
  ```
- **Input Variables**:
  - `raw_planned_quantity`: Decimal or float (from plan_e126_per_item_split / plan_e132_per_item_split)
  - May be fractional (e.g., 50.5 for PKO half of 101-unit total)
- **Output**: `floored_qty` (float, no fractional part)
- **Rounding**: Floor (toward −∞), not ROUND_HALF_UP
- **Source Code** (E126):
  ```python
  # backend/apps/license/services/e126_auto_plan.py:111-116
  def _floor_qty(x) -> float:
      try:
          return float(math.floor(float(x)))
      except (TypeError, ValueError):
          return 0.0
  ```
- **Source Code** (E132):
  ```python
  # backend/apps/license/services/e132_auto_plan.py:108-113
  def _floor_qty(x) -> float:
      try:
          return float(math.floor(float(x)))
      except (TypeError, ValueError):
          return 0.0
  ```
- **Evidence**:
  - E126: `backend/apps/license/services/e126_auto_plan.py:111-116` + `242-266`
  - E132: `backend/apps/license/services/e132_auto_plan.py:108-113` + `239-269`
- **Confidence**: HIGH
- **Known Issues**: NONE in the calculation itself

---

### 2.2 (DEFECT) CIF NOT RECOMPUTED AFTER FLOORING
- **Calculation Type**: Financial (DEFECT — Expected vs. Actual)
- **Context**: After flooring planned_quantity, planned_cif_fc should be recomputed, but it is not
- **Expected Formula**:
  ```
  floored_qty = floor(raw_planned_qty)
  corrected_planned_cif_fc = round(floored_qty × unit_price, 2)
  ```
- **Actual Formula** (DEFECT):
  ```
  floored_qty = floor(raw_planned_qty)
  planned_cif_fc = round(raw_planned_cif, 2)  # NOT recomputed!
  # Result: planned_cif_fc ≠ floored_qty × unit_price
  ```
- **Effect**: For every fractional split:
  - saved `planned_quantity` = floored, but `planned_cif_fc` = un-floored CIF
  - Violates invariant: `planned_cif_fc ≠ planned_quantity × unit_price`
  - This invariant is implicitly assumed elsewhere (e.g., `plan_grouping._effective_rate`, `plan_grouping._blended_pko_olive_rate`)
- **Numerical Example** (from BL-PLAN-01):
  - Input: PKO/Olive-Oil split with available_qty = 101, balance_cif = 343.40
  - Raw split: PKO 50.5 @ 1.80 = 90.90, Olive Oil 50.5 @ 5.00 = 252.50
  - **Expected Output** (if corrected):
    - PKO: planned_qty=50, unit_price=1.80, planned_cif_fc = 50 × 1.80 = **90.00**
    - Olive Oil: planned_qty=50, unit_price=5.00, planned_cif_fc = 50 × 5.00 = **250.00**
  - **Actual Output** (DEFECT):
    - PKO: planned_qty=50, unit_price=1.80, planned_cif_fc = **90.90** (mismatch of +0.90)
    - Olive Oil: planned_qty=50, unit_price=5.00, planned_cif_fc = **252.50** (mismatch of +2.50)
- **Impact**:
  - Consumes real DFIA license Balance CIF (legally capped entitlement) against NO recorded plannable quantity
  - License `remaining_cif` understates what is actually usable
  - Persisted `LicenseItemPlan` row is internally inconsistent
- **Source Code**:
  - E126: `backend/apps/license/services/e126_auto_plan.py:242-266`
  - E132: `backend/apps/license/services/e132_auto_plan.py:239-269`
- **Evidence**:
  - Audit BL-PLAN-01 independent verification: `backend/apps/license/services/e126_auto_plan.py:242-266` and e132_auto_plan.py:239-269 confirmed VERBATIM
  - Skeptic check reproduction: independent re-run with available_qty=77 produced identical mismatch pattern (0.9 and 2.5 CIF mismatch)
- **Confidence**: HIGH (independently reproduced, defect confirmed)
- **Suggested Fix**:
  - Recompute: `planned_cif_fc = round(floored_qty * _r2(unit_price), 2)` (mirroring E5's pattern)
  - No API change, only persisted values change for future runs

---

## 3. MILK SPLIT ALLOCATION (E5 / E132)

### 3.1 Milk 40/60 Split
- **Calculation Type**: Financial (Percentage Allocation)
- **Context**: E5/E132 licenses with milk category use a 40/60 split between two milk planning items
- **Formula**:
  ```
  milk_cif_40_percent = balance_cif × 0.40
  milk_cif_60_percent = balance_cif × 0.60
  
  milk_qty_40 = min(milk_qty_available, milk_cif_40_percent / milk_price_40)
  milk_qty_60 = min(milk_qty_available - milk_qty_40, milk_cif_60_percent / milk_price_60)
  ```
- **Input Variables**:
  - `milk_qty_available`: float (available milk quantity for the license)
  - `balance_cif`: float (available license CIF budget)
  - `milk_price_40`: fixed Decimal (planning item ceiling price for 40% bucket)
  - `milk_price_60`: fixed Decimal (planning item ceiling price for 60% bucket)
- **Output**: 
  - `milk_qty_40`, `milk_qty_60` (floats)
  - `milk_cif_40`, `milk_cif_60` (floats, rounded to 2 decimals)
- **Rounding**: To 2 decimals via `_quantize()`
- **Source**: `backend/apps/license/services/milk_planner.py:48-82` (split_milk_0404)
- **Confidence**: HIGH
- **Known Issues**: None identified

---

## 4. ROUND-TO-2-DECIMALS UTILITY

### 4.1 _r2() Function
- **Calculation Type**: Infrastructure (Precision Control)
- **Context**: Utility used universally for CIF rounding
- **Formula**: `round(x, 2)` → float
- **Input**: `x` (any type, coerced to float)
- **Output**: float with max 2 decimal places
- **Error Handling**: Returns 0.0 if x is unparseable
- **Source Code** (E126):
  ```python
  # backend/apps/license/services/e126_auto_plan.py:104-109
  def _r2(x) -> float:
      try:
          return round(float(x), 2)
      except (TypeError, ValueError):
          return 0.0
  ```
- **Evidence**:
  - E126: `backend/apps/license/services/e126_auto_plan.py:104-109`
  - E132: `backend/apps/license/services/e132_auto_plan.py:101-106`
  - Audit BL-PLAN-01: verified as byte-identical in both files
- **Confidence**: HIGH
- **Known Issues**: None (consistent use)

---

## 5. CEILING PRICE VALIDATION

### 5.1 Unit Price ≤ Ceiling Price Check
- **Calculation Type**: Validation (Constraint Check)
- **Context**: Planning items (e.g., PKO, Olive Oil) have fixed unit prices (ceiling prices). Auto-plan lines must respect these.
- **Formula**:
  ```
  is_valid = unit_price ≤ ceiling_price × (1 + tolerance_percent)
  tolerance_percent = 0.01  # 1% margin for rounding
  ```
- **Input Variables**:
  - `unit_price`: float (from auto-plan engine, e.g. 1.80 for PKO)
  - `ceiling_price`: Decimal (from PlanningItemModel)
  - `tolerance_percent`: float (hardcoded)
- **Output**: Boolean (is_valid)
- **Source**: `backend/apps/license/services/plan_grouping.py:330-391` (validate_group_plan_lines)
- **Evidence**: Code line ~360-370 in plan_grouping.py
- **Confidence**: HIGH
- **Known Issues**: 
  - Does NOT validate `planned_cif_fc == planned_quantity × unit_price` (per audit BL-PLAN-01)

---

## 6. QUANTITY CAP VALIDATION

### 6.1 Total Planned Quantity ≤ Available Quantity Check
- **Calculation Type**: Validation (Constraint Check)
- **Context**: Group auto-plan lines must not exceed the group's available quantity
- **Formula**:
  ```
  is_valid = sum(planned_quantity for all lines in group) ≤ available_qty × (1 + tolerance)
  tolerance = 0.01  # 1% margin
  ```
- **Input Variables**:
  - `planned_quantity`: list of floats (from each plan line)
  - `available_qty`: float (group's total available quantity, summed from import items)
  - `tolerance`: float (hardcoded 0.01)
- **Output**: Boolean (is_valid)
- **Source**: `backend/apps/license/services/plan_grouping.py:330-391`
- **Confidence**: HIGH
- **Known Issues**: None identified

---

## 7. PRESERVED PLAN RE-EMISSION

### 7.1 Preserved Plan Passthrough
- **Calculation Type**: Infrastructure (Non-Computation)
- **Context**: For licenses that have had an auto-plan run before, the `preserved` branch re-emits the same lines without recomputation
- **Formula**:
  ```
  # NO calculation; simply re-emit:
  new_line = old_line  # Copy all fields verbatim
  ```
- **Input**: Existing `LicenseItemPlan` row with `preserved_during_re_generation=True`
- **Output**: Identical line (no change)
- **Source**: `backend/apps/license/services/plan_enforcement.py:180-191` (save_plan_lines_for_license preserved branch)
- **Confidence**: HIGH
- **Known Issues**:
  - If the original line had a BL-PLAN-01 mismatch (E126/E132 defect), the preserved branch INHERITS that mismatch
  - Re-running the auto-plan does NOT fix the defect; it persists forever

---

## 8. AVAILABLE QUANTITY CALCULATION

### 8.1 License Available Quantity
- **Calculation Type**: Financial (Balance Tracking)
- **Context**: Per-license sum of all available quantities (licensed but not yet allotted)
- **Formula**:
  ```
  license_available_qty = sum(import_item.available_quantity for all import items)
  ```
- **Input**: All `LicenseImportItemsModel` rows for a license
- **Output**: float (kg or units, depends on commodity)
- **Source**: Implicit (used by all planning engines)
- **Confidence**: HIGH
- **Known Issues**: None identified

---

### 8.2 Item Available Quantity
- **Calculation Type**: Financial (Balance Tracking)
- **Context**: Per-import-item available quantity
- **Formula**:
  ```
  item_available_qty = balance_cif_fc  # If applicable, else weight/volume
  ```
- **Input**: `LicenseImportItemsModel.available_quantity` (persisted field, not computed live)
- **Output**: float
- **Precision**: Depends on source (DGFT data, typically to 2-3 decimals for weights)
- **Rounding**: None (value stored as-is)
- **Source**: Persisted in DB (set during license import from DGFT)
- **Evidence**:
  - Audit BL-PLAN-01: "22 of 2401 import items have fractional available_quantity values"
  - Real examples: 3066.09, 5110.15, 9637.11, etc.
- **Confidence**: HIGH
- **Known Issues**: None (source data issue, not calculation)

---

## 9. LICENSE BALANCE CALCULATION

### 9.1 License Balance CIF
- **Calculation Type**: Financial (Aggregate Balance)
- **Context**: Per-license CIF balance (legal limit on import value)
- **Formula**: Computed by `calculate_financial_balance()` in `balance_calculator.py`
  - DEBIT = sum of all BOE row CIF values (adjusted for hidden/shown status)
  - CREDIT = sum of all BOE DEBIT row CIF values
  - BALANCE = CREDIT − DEBIT
- **Input**:
  - All `BillOfEntryRowDetails` rows for the license
  - Status field (hidden vs. visible)
  - Transaction type (DEBIT vs. CREDIT)
- **Output**: float (license's available CIF budget)
- **Caching**: Cached in `LicenseBalance.balance_cif` column
- **Update Trigger**: Signals (reconciliation actions should trigger refresh)
- **Known Issue** (BL-LEDGER-02):
  - Cached `LicenseBalance.balance_cif` can go stale after reconciliation allocation actions
  - `InvoiceBOEAllocation` creation does not trigger balance refresh
- **Evidence**:
  - Audit BL-LEDGER-02: "Cached LicenseBalance.balance_cif goes stale after reconciliation allocation actions"
- **Confidence**: MEDIUM (caching issue identified)

---

## 10. GROUP USAGE SNAPSHOT

### 10.1 Group Used (Allotted) Quantity
- **Calculation Type**: Quantity Tracking (Group-Level Remaining)
- **Context**: For a group of related import items, track how much has been allotted
- **Formula**:
  ```
  group_used_qty = sum(item.allotted_quantity for item in group)
  group_used_cif = sum(item.allotted_value for item in group)
  ```
- **Input**: List of `LicenseImportItemsModel` with same group key
- **Output**: (used_qty, used_cif) tuple of floats
- **Source**: `backend/apps/license/services/plan_enforcement.py:116-128` (group_used_snapshot)
- **Confidence**: HIGH
- **Known Issues**: None identified

---

## Summary of Calculations

| Category | Count | Status | Issues |
|----------|-------|--------|--------|
| Category Allocation (E1/E5) | 3 | HIGH | None |
| Quantity Flooring (E126/E132) | 2 | HIGH | **BL-PLAN-01 defect** |
| Milk Split (E5/E132) | 1 | HIGH | None |
| Rounding & Precision | 1 | HIGH | None |
| Validation Checks | 2 | HIGH | Does NOT check cif/qty invariant |
| Preserved Plan | 1 | HIGH | Inherits BL-PLAN-01 defect |
| Available Quantity | 2 | HIGH | None |
| License Balance | 1 | MEDIUM | **BL-LEDGER-02 caching stale** |
| Group Tracking | 1 | HIGH | None |
| **TOTAL** | **14** | | **2 issues** |

