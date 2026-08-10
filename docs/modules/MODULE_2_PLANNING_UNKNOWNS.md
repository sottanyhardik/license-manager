# MODULE 2 — PLANNING UNKNOWNS & AMBIGUITIES

## Overview

This document consolidates every question about planning/auto-planning that lacks code evidence, requires business clarification, or remains ambiguous after the audit. Each entry includes:
- **Question/Ambiguity**
- **Current Code Evidence** (what we know)
- **Missing Information** (what we don't know)
- **Why It Matters**
- **Suggested Resolution**

---

## 1. NORM CLASSIFICATION DECISIONS

### 1.1 PP Norm Planning Rules
- **Question**: What are the business planning rules for PP (SION norm class) licenses?
- **Current Evidence**:
  - 73 of 228 real licenses (32%) are PP norm class — single largest group after E5's 76
  - `detect_norm()` explicitly returns "" (not recognized) for PP
  - No `pp_auto_plan.py` module exists
  - Audit BL-PLAN-02 classification: "Improvement (feature-coverage gap), NOT a defect"
- **Missing Information**:
  - Are PP licenses intended to have auto-plan support?
  - If yes: What are the classification rules (items → planning items)?
  - What are the pricing rules (category waterfall, fixed prices, fixed rate)?
  - Are there splits (like PKO/Olive-Oil for E126)?
  - What planning items should PP licenses reference?
- **Why It Matters**: 
  - 73 real licenses currently cannot use auto-plan; users must manually enter all plans
  - Item Pivot Report shows no pre-filled utilization for PP licenses
  - Balance Excel export shows no pre-filled planning for PP licenses
- **Suggested Resolution**: 
  1. Confirm with business whether PP planning is in scope
  2. If yes, document PP planning rules formally
  3. Implement `pp_auto_plan.py` following the pattern of E1/E5/E126/E132
  4. Register with PlannerFactory

---

### 1.2 A3627 Norm Planning Rules (Incomplete Documentation)
- **Question**: What is the complete formal specification for A3627 (ores/minerals) planning?
- **Current Evidence**:
  - `a3627_auto_plan.py` exists (215 lines, in-progress)
  - 1 real license with A3627 norm in current DB
  - Engine computes fixed-rate allocation (similar to planning item prices)
  - Includes import-price averaging logic
  - Audit BL-PLAN-02: "added most recently, per the in-progress, out-of-scope a3627_auto_plan.py"
- **Missing Information**:
  - Are there sub-categories within A3627 (like E126's Nuts/PKO/Olive-Oil)?
  - What are the classification rules?
  - Are there any splits (e.g., for different ore types)?
  - Why is import-price averaging used (instead of fixed planning item prices like E126/E132)?
  - What is the import-price averaging formula?
  - Is the engine feature-complete or still under development?
- **Why It Matters**:
  - Only 1 real license currently, but rules needed if more A3627 licenses are onboarded
  - Auto-plan output might change as engine matures
  - Unclear if engine should inherit BL-PLAN-01 defect or avoid it
- **Suggested Resolution**:
  1. Document A3627 planning specification formally
  2. Determine if engine is production-ready or experimental
  3. If experimental, flag to users
  4. Consider whether to apply BL-PLAN-01 fix when E126/E132 are fixed

---

## 2. CALCULATION PRECISION & ROUNDING

### 2.1 Exact Rounding Behavior During Category Waterfall
- **Question**: What is the exact rounding mode and sequence during E1/E5 category waterfall?
- **Current Evidence**:
  - `_quantize()` helper exists (e1_plan.py:46, e5_plan.py:51)
  - Uses `ROUND_HALF_UP` rounding mode (Decimal context)
  - Precision: 2 decimals for CIF, 3 decimals for quantities
  - Rounding applied at multiple stages:
    1. Category CIF allocation
    2. Category unit price computation
    3. Per-item CIF computation
- **Missing Information**:
  - Exact sequence of rounding (which stage happens first)?
  - Does category waterfall ensure sum of item CIFs equals category CIF?
  - What is the tolerance for the sum (e.g., if rounding creates 0.01 gap)?
  - Are there documented test cases for edge cases (e.g., 3 items, 100 units, 100.00 CIF)?
- **Why It Matters**:
  - Rounding effects accumulate; could cause remaining_cif to be off
  - Audit evidence needed to confirm waterfall is correct (and E126/E132 defect is isolated)
  - If remaining_cif becomes negative due to rounding, it would be a bug
- **Suggested Resolution**:
  1. Add test case: verify sum(item_cif) ≈ category_cif (with documented tolerance)
  2. Document exact rounding sequence in code comments
  3. Add assertion to catch rounding drift

---

### 2.2 BL-PLAN-01 Fix: Will It Create Rounding Cascades?
- **Question**: If the suggested fix for BL-PLAN-01 is applied (recompute planned_cif_fc after flooring), will it cause cascading rounding effects?
- **Current Evidence**:
  - BL-PLAN-01 defect: `planned_cif_fc = round(raw_planned_cif, 2)` (should be `round(fqty * unit_price, 2)`)
  - Example: fractional split produces +0.90 CIF mismatch
  - Suggested fix is to "recompute from floored quantity" (like E5 does)
- **Missing Information**:
  - Will the fix change total_planned_cif for affected licenses?
  - Could fixing one license cause another license's remaining_cif to change?
  - Are there cross-license calculations that would be affected?
  - Should there be a data migration for existing corrupted LicenseItemPlan rows?
- **Why It Matters**:
  - Changing persisted plan values could affect reports, balance calculations, and user-facing displays
  - Regression tests need to cover before/after behavior
  - Possibly needs audit trail or user notification
- **Suggested Resolution**:
  1. Before applying fix, run before/after comparison on test licenses
  2. Check if any existing LicenseItemPlan rows are actually affected
  3. If affected, decide: migrate data or leave as-is?
  4. Add regression test to prevent re-introduction

---

## 3. VALIDATION GAPS

### 3.1 Missing Validation: planned_cif_fc = planned_quantity × unit_price
- **Question**: Why is the invariant `planned_cif_fc ≈ planned_quantity × unit_price` not enforced during validation?
- **Current Evidence**:
  - `validate_group_plan_lines()` checks:
    - unit_price ≤ ceiling_price + 1%
    - sum(planned_qty) ≤ available_qty + 1%
  - But does NOT check: `planned_cif_fc ≈ planned_qty * unit_price`
  - Audit BL-PLAN-01: "It NEVER checks planned_cif_fc == planned_quantity * unit_price"
- **Missing Information**:
  - Was this validation intentionally omitted, or an oversight?
  - Why is it missing from the validation gate but implicitly assumed elsewhere?
  - What tolerance should be used (±0.01, ±0.001, etc.)?
- **Why It Matters**:
  - E126/E132 defect (BL-PLAN-01) is not caught by validation
  - Corrupted rows are silently saved
  - Implicit assumptions in reporting code could produce wrong effective rates
- **Suggested Resolution**:
  1. Add validation check: `planned_cif_fc ≈ round(planned_qty * unit_price, 2)` (±0.01 tolerance)
  2. Add unit test: validate_group_plan_lines() with mismatched cif/qty pair

---

## 4. LEDGER & BALANCE INTERACTIONS

### 4.1 Plan Interaction with Hidden BOE Rows
- **Question**: How should planning interact with hidden BOE rows?
- **Current Evidence**:
  - Audit BL-LEDGER-01: "Link BOE to Trade can silently un-hide a genuinely-hidden previous-owner BOE"
  - Hidden BOE rows affect balance_cif calculation
  - Planning engines use balance_cif to allocate CIF
- **Missing Information**:
  - If a BOE row is hidden, should that row's CIF be excluded from planning balance?
  - If a hidden row is later un-hidden, does auto-plan need to be re-run?
  - Are there licenses currently with corrupted balance_cif due to BL-LEDGER-01?
- **Why It Matters**:
  - If hidden rows incorrectly affect balance_cif, planning amounts could be wrong
  - Users might not realize balance changed when a BOE is un-hidden
- **Suggested Resolution**:
  1. Clarify business rule: should hidden BOEs affect planning balance?
  2. If yes, ensure balance_cif calculation excludes/includes hidden correctly
  3. Add test case: hide/unhide BOE, verify balance_cif and plan allocation

---

### 4.2 Plan Interaction with Cached vs. Live Balance CIF
- **Question**: Does planning use the cached balance_cif (from LicenseBalance table) or live-computed balance_cif?
- **Current Evidence**:
  - Audit BL-LEDGER-02: "Cached LicenseBalance.balance_cif goes stale after reconciliation allocation actions"
  - Auto-plan engines call `license_obj.get_balance_cif()`
  - This property might return cached or computed value (unclear from inspection)
- **Missing Information**:
  - Does `get_balance_cif()` use cached LicenseBalance.balance_cif or recompute?
  - If cached, what triggers a refresh?
  - If stale, could auto-plan allocation be incorrect?
- **Why It Matters**:
  - If cached balance_cif is stale, auto-plan might over-allocate CIF
  - Could corrupt license balance
- **Suggested Resolution**:
  1. Verify `get_balance_cif()` implementation (cached vs. live)
  2. If cached and stale (per BL-LEDGER-02), add test case to verify auto-plan uses current balance
  3. Consider using live-computed balance for planning critical path

---

## 5. MANUAL PLAN INTERACTION

### 5.1 Manual Plan Merge Semantics
- **Question**: When a manual plan line exists and auto-plan is re-run, what exactly happens?
- **Current Evidence**:
  - `effective_plan_for_license()`: "MANUAL FIRST — if an import item has a manual plan line, that line is used and is FIXED: the automated norm logic never overrides it"
  - `save_plan_lines_for_license()`: deletes non-preserved, non-manual plan lines
- **Missing Information**:
  - Are manual lines deleted when auto-plan is re-run?
  - Or are they preserved?
  - If a user creates a manual plan line, then runs auto-plan, what happens?
  - Is there a UI warning that manual lines will be preserved?
- **Why It Matters**:
  - User might not expect manual lines to persist when auto-plan is re-run
  - Could lead to confusion or unexpected behavior
  - Should be clearly documented in UI
- **Suggested Resolution**:
  1. Verify manual line preservation logic (code inspection already done; test case needed)
  2. Add UI note: "Manual plan lines will be preserved; running Auto-Plan will not overwrite them"
  3. Consider adding "reset to norm plan" button to clear manual lines and re-run auto-plan

---

### 5.2 Unit Price Derivation from Manual Plans
- **Question**: When a manual plan line is created, what unit price is stored?
- **Current Evidence**:
  - `effective_plan_for_license()` computes unit_price: `round(c / q, 2) if q else 0.0`
  - Manual plan lines come from `LicenseItemPlanModel` rows
- **Missing Information**:
  - Does a manual plan line have a unit_price field?
  - If yes, is it user-supplied or computed?
  - If computed, is the formula documented?
  - Are there edge cases (e.g., zero quantity, zero CIF)?
- **Why It Matters**:
  - Reporting code might display the unit price; if wrong, reports are wrong
  - Allocation validation uses unit price; if wrong, validation is wrong
- **Suggested Resolution**:
  1. Inspect LicenseItemPlanModel schema to see if unit_price is stored
  2. If not stored, verify it's always computed correctly
  3. Add test case: create manual plan line with fractional quantity, verify unit_price

---

## 6. GROUP SCOPING & AGGREGATION

### 6.1 Group Key Definition for Plan Grouping
- **Question**: What exactly defines a "group" for plan grouping purposes?
- **Current Evidence**:
  - `plan_group_key()` function exists in `plan_grouping.py:73`
  - Used to aggregate items for validation and allocation
  - Function signature not inspected in detail
- **Missing Information**:
  - What fields are used to compute the group key?
  - Is it based on classification (e.g., E126 "PKO" category)?
  - Or based on description/HSN?
  - Are there edge cases (e.g., mixed HSN/classification)?
  - How does it interact with splits?
- **Why It Matters**:
  - Group key affects how planned CIF is aggregated
  - Wrong grouping could cause validation errors or allocation bugs
- **Suggested Resolution**:
  1. Document `plan_group_key()` function (purpose, fields, edge cases)
  2. Add test cases: verify items are grouped correctly, splits handled correctly

---

## 7. REMAINING QUANTITY TRACKING

### 7.1 Remaining Quantity Refresh After Allotments
- **Question**: When an allotment is created/deleted, how quickly is remaining_quantity updated?
- **Current Evidence**:
  - `effective_plan_for_license()` computes remaining: `max(planned - allotted, 0)`
  - Allotments maintained in `LicenseImportItemsModel.allotted_quantity`
  - Signals trigger balance updates
- **Missing Information**:
  - Does allotment create/delete trigger signals to update LicenseImportItemsModel.allotted_quantity?
  - Is there a delay (e.g., async task)?
  - Could a user see stale remaining_quantity in the UI?
- **Why It Matters**:
  - If stale, allocation form could show wrong available quantity
  - Could allow over-allocation
- **Suggested Resolution**:
  1. Verify allotment signals update `allotted_quantity` synchronously
  2. Add test case: create allotment, verify remaining_quantity decreases immediately

---

## 8. EDGE CASES & DATA QUALITY

### 8.1 Fractional Available Quantities
- **Question**: How common are fractional available_quantity values in real data?
- **Current Evidence**:
  - Audit BL-PLAN-01: "22 of 2401 real import items have fractional available_quantity"
  - Examples: 3066.09, 5110.15, 9637.11 kg
- **Missing Information**:
  - Are these fractional quantities intentional (e.g., post-allocation residuals)?
  - Or data quality issues from DGFT import?
  - Should planning engines expect fractional quantities?
  - Are there rounding/precision issues in balance calculations due to these fractions?
- **Why It Matters**:
  - Fractional quantities trigger splits and flooring in E126/E132
  - Could accumulate rounding errors
- **Suggested Resolution**:
  1. Investigate source of fractional quantities (DGFT import or post-allocation residuals)
  2. Document expectations (should be common or rare?)
  3. Add test case: allocate from fractional items, verify balance remains consistent

---

### 8.2 Zero Quantity Items
- **Question**: How should planning handle import items with zero available_quantity?
- **Current Evidence**:
  - Auto-plan engines check `if not planned_qty or float(planned_qty) <= 0: continue`
  - But unclear if this happens before or after flooring
- **Missing Information**:
  - Can an import item have zero available_quantity legitimately?
  - If so, should it appear in plan at all?
  - Are there test cases for zero-quantity items?
- **Why It Matters**:
  - Edge case that could cause allocation errors if not handled
- **Suggested Resolution**:
  1. Add test case: license with zero-quantity import item, verify no plan line created

---

### 8.3 Missing or Invalid Unit Prices
- **Question**: What happens if a planning item has no unit price (NULL) or zero price?
- **Current Evidence**:
  - E5 milk planning can produce zero CIF for milk (per documentation: "e.g. Milk" marked as price To-Be-Defined)
  - Audit BL-PLAN-02 mentions MIN_PLAN_QTY = 50 filtering
- **Missing Information**:
  - Is there a list of "To-Be-Defined" planning items?
  - How are they handled in allocation?
  - Can a planned line have zero CIF?
  - If so, how does remaining_cif behave?
- **Why It Matters**:
  - Could allow allocation of items with no actual CIF value
- **Suggested Resolution**:
  1. Document which planning items have TBD prices
  2. Add test case: allocate from item with zero CIF, verify behavior

---

## 9. API CONTRACT & SEMANTICS

### 9.1 Auto-Plan Idempotence
- **Question**: Is auto-plan idempotent (running twice gives same result)?
- **Current Evidence**:
  - Preserved branch re-emits lines without recomputation
  - Fresh branch deletes old lines and creates new ones
- **Missing Information**:
  - If you run auto-plan, then immediately run it again, is the result identical?
  - Or could the second run produce different lines (e.g., due to balance changes)?
  - Should the API warn users if they're about to overwrite a previous plan?
- **Why It Matters**:
  - Idempotence is important for safe retry behavior
  - If not idempotent, users could lose data
- **Suggested Resolution**:
  1. Document idempotence guarantee (or lack thereof)
  2. Add test case: run auto-plan twice, verify results identical (if expected)

---

### 9.2 Auto-Plan Atomicity
- **Question**: If auto-plan fails partway through, is the license in a corrupted state?
- **Current Evidence**:
  - `save_plan_lines_for_license()` appears to be single transaction
- **Missing Information**:
  - Is the entire auto-plan operation (classify + validate + persist) wrapped in a transaction?
  - If validation fails, are old plan lines deleted?
  - Are there cleanup handlers?
- **Why It Matters**:
  - If not atomic, a crash could leave license with partial plan
- **Suggested Resolution**:
  1. Verify auto-plan is wrapped in transaction
  2. Add test case: simulate failure during auto-plan, verify old plan intact

---

## 10. REPORTING & DISPLAY

### 10.1 Plan Mismatch Detection in Reports
- **Question**: Do Item Pivot Report and License Overview Planning tab detect when displayed plan (from norm_plan_for_license) doesn't match persisted plan (from LicenseItemPlan)?
- **Current Evidence**:
  - `norm_plan_for_license()` computes plan for display
  - `save_plan_lines_for_license()` persists it
  - But no documented check to ensure they match
- **Missing Information**:
  - Do these ever diverge?
  - What would cause divergence?
  - Is there a test to verify they match?
  - Is there a UI warning if they diverge?
- **Why It Matters**:
  - Could show users wrong utilization numbers
  - Could confuse allocation decision-making
- **Suggested Resolution**:
  1. Add test case: compute and persist plan, verify they match
  2. Add assertion to catch divergence

---

## Summary of Unknowns

| Category | Count | Priority |
|----------|-------|----------|
| Norm Classification | 2 | HIGH (affects 73+ real licenses for PP) |
| Calculation Precision | 2 | MEDIUM (affects correctness but not obvious) |
| Validation Gaps | 1 | HIGH (E126/E132 defect not caught) |
| Balance Interactions | 2 | MEDIUM (BL-LEDGER issues) |
| Manual Plan Semantics | 2 | MEDIUM (UX clarity needed) |
| Group Scoping | 1 | MEDIUM (affects allocation logic) |
| Remaining Qty Tracking | 1 | MEDIUM (staleness risk) |
| Data Quality & Edge Cases | 3 | LOW (rare cases, but should be documented) |
| API Contracts | 2 | MEDIUM (safety guarantees needed) |
| Reporting | 1 | MEDIUM (display correctness) |
| **TOTAL** | **17** | |

## Recommendations for Clarification

**Immediate Priority (Block on these)**:
1. Clarify PP norm planning rules (73 real licenses affected)
2. Confirm whether BL-PLAN-01 fix should be applied and if data migration needed
3. Add validation check for `planned_cif_fc ≈ planned_qty × unit_price`

**Short-term Priority (High value, moderate effort)**:
1. Document A3627 planning specification formally
2. Verify manual plan preservation behavior is intentional
3. Document group key definition and edge cases
4. Add test case: verify plan computed ≈ plan persisted

**Ongoing (Technical debt)**:
1. Document exact rounding sequence in category waterfall
2. Investigate fractional quantity prevalence
3. Verify auto-plan idempotence/atomicity
4. Add rounding drift assertions

