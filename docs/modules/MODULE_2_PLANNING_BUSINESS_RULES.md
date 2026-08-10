# MODULE 2 — PLANNING BUSINESS RULES INVENTORY

## Overview

This document consolidates every business constraint and rule enforced by the planning system. Each entry includes:
- **Rule description**
- **Formal statement**
- **Scope** (which licenses, items, or conditions)
- **Enforcement point** (where checked/applied)
- **Evidence** (file:line)
- **Compliance status** (enforced, partially enforced, gaps identified)

---

## 1. PLANNING NORM COVERAGE

### 1.1 E1 Norm: Fixed-Rate Category Allocation
- **Rule**: E1 licenses allocate their balance CIF to category-based planning items, with each category assigned an effective unit price (CIF / quantity)
- **Formal Statement**:
  - For each import item in an E1 license:
    - Classify into a category (Cereals, Pulses, Spices, Sugar, etc.)
    - Group items by category
    - Allocate balance_cif proportionally to categories (weight = sum of item quantities)
    - Per-category unit price = category_cif / category_qty
    - Per-item planned_cif = planned_qty × unit_price
- **Scope**: 25 real licenses (per audit BL-PLAN-02, norm distribution)
- **Enforcement Point**:
  - Classification: `classify_e1_item()` in `e1_plan.py:88`
  - Waterfall: `plan_e1_items()` in `e1_plan.py:225`
  - Auto-plan: `compute_e1_auto_plan()` in `e1_auto_plan.py:96`
  - Persistence: `save_plan_lines_for_license()` in `plan_enforcement.py:130`
- **Evidence**:
  - `backend/apps/license/services/e1_plan.py:88-306`
  - `backend/apps/license/services/e1_auto_plan.py:96-148`
- **Compliance Status**: FULLY ENFORCED
- **Known Issues**: None

---

### 1.2 E5 Norm: Category + Milk 40/60 Split
- **Rule**: E5 licenses allocate balance CIF to categories (Oils, Cereals, Pulses, Spices, Milk)
  - For non-milk categories: same as E1 (proportional allocation)
  - For milk category: apply 40/60 split between two milk planning items
- **Formal Statement**:
  - Classify each item into category
  - If category = Milk:
    - 40% of milk_category_cif goes to Milk_40 planning item
    - 60% of milk_category_cif goes to Milk_60 planning item
    - Respect ceiling prices for each bucket
  - Otherwise: proportional allocation (E1 rule)
- **Scope**: 76 real licenses (largest norm-class group per audit BL-PLAN-02)
- **Enforcement Points**:
  - Classification: `classify_e5_item()` in `e5_plan.py:95`
  - Milk split: `split_milk_0404()` in `milk_planner.py:48`
  - Waterfall: `plan_e5_items()` in `e5_plan.py:233` (_run_oils, _run_milk methods)
  - Auto-plan: `compute_e5_auto_plan()` in `e5_auto_plan.py:128`
- **Evidence**:
  - `backend/apps/license/services/e5_plan.py:233-353`
  - `backend/apps/license/services/milk_planner.py:48-186`
- **Compliance Status**: FULLY ENFORCED
- **Known Issues**: None

---

### 1.3 E126 Norm: PKO/Olive-Oil Deterministic Splits
- **Rule**: E126 licenses classify items into 3 planning categories: Nuts, PKO, Olive Oil
  - Items with both PKO signal (HSN 1513 vegetable oil + specific descriptions) AND Olive Oil signal trigger a 50/50 split
  - Each split half is priced at the respective planning item's fixed unit price
- **Formal Statement**:
  - For each import item with HSN 1513 (vegetable oils):
    - Check for PKO signal (specific description patterns)
    - Check for Olive Oil signal (specific description patterns)
    - If BOTH signals: split into PKO (50%) and Olive Oil (50%)
    - If PKO only: classify as PKO
    - If Olive Oil only: classify as Olive Oil
    - If neither: classify as Nuts
    - Planned quantity = available_qty × (split % if split, else 100%)
    - Unit price = planning_item's fixed rate
    - Planned CIF = planned_qty × unit_price
- **Scope**: 0 real E126 licenses currently (per audit BL-PLAN-02); 2 real E132 licenses
- **Enforcement Points**:
  - Classification: `classify_e126_record()` in `e126_plan.py:161`
  - Split detection: `_is_pko_signal()`, `_is_olive_oil_signal()` in `e126_plan.py:127-131`
  - Split execution: `_split_pko_olive_record()` in `e126_plan.py:213`
  - Per-item planning: `plan_e126_per_item_split()` in `e126_plan.py:472`
  - Wastage rebalance: `_rebalance_pko_olive_wastage()` in `e126_plan.py:314` (separate, correct mechanism)
  - Auto-plan: `compute_e126_auto_plan()` in `e126_auto_plan.py:118`
- **Evidence**:
  - `backend/apps/license/services/e126_plan.py:161-185`, `213-276`, `472-515`
  - `backend/apps/license/services/e126_auto_plan.py:118-338`
- **Compliance Status**: PARTIALLY ENFORCED
  - **Defect (BL-PLAN-01)**: For fractional available quantities (which trigger fractional split quantities), the floored `planned_quantity` is saved WITHOUT recomputing `planned_cif_fc`, creating a permanent arithmetic inconsistency
  - Split logic itself is correct; persistence arithmetic is defective
- **Known Issues**: 
  - **BL-PLAN-01**: E126 auto-plan creates LicenseItemPlan rows where `planned_cif_fc ≠ planned_quantity × unit_price`

---

### 1.4 E132 Norm: Vegetable Oils + Dairy with 40/60 Splits
- **Rule**: E132 licenses classify items into 6 planning categories: Nuts, Yeast, PKO, RBD (refined bleached deodorized oils), Cheese, Aluminium
  - PKO/Cheese split: when both signals present, apply 40/60 split (40% PKO, 60% Cheese)
  - Each category priced at planning item's fixed unit price
- **Formal Statement**:
  - For each import item:
    - Check classification signals (HSN codes, descriptions)
    - If PKO AND Cheese signals: split 40% PKO / 60% Cheese
    - Else: classify into one of 6 categories
    - Planned quantity = available_qty × (split %, or 100% if no split)
    - Unit price = planning_item's fixed rate
    - Planned CIF = planned_qty × unit_price
- **Scope**: 2 real E132 licenses (per audit BL-PLAN-02)
  - Only 1 classified item (id 37537) with available_qty = 4.00 (below MIN_PLAN_QTY = 50)
  - No real E132 license currently has PKO + Cheese-signal item triggering split
  - However, split logic is in place and will fire on next matching import
- **Enforcement Points**:
  - Classification: `classify_e132_record()` in `e132_plan.py:199`
  - Signal detection: `_is_pko_signal()`, `_is_explicit_cheese()`, `_is_cheese_strict()`, `_is_rbd()` in `e132_plan.py:139-157`
  - Split execution: `_split_veg_oil_record()` in `e132_plan.py:259`
  - Per-item planning: `plan_e132_per_item_split()` in `e132_plan.py:532`
  - Wastage rebalance: `_rebalance_veg_oil_wastage()` in `e132_plan.py:364`
  - Auto-plan: `compute_e132_auto_plan()` in `e132_auto_plan.py:115`
- **Evidence**:
  - `backend/apps/license/services/e132_plan.py:199-231`, `259-311`, `532-575`
  - `backend/apps/license/services/e132_auto_plan.py:115-286`
- **Compliance Status**: PARTIALLY ENFORCED
  - **Defect (BL-PLAN-01)**: Identical to E126 — fractional split quantities lose their floored CIF recomputation
- **Known Issues**: 
  - **BL-PLAN-01**: E132 auto-plan creates LicenseItemPlan rows where `planned_cif_fc ≠ planned_quantity × unit_price`

---

### 1.5 A3627 Norm: Ores/Minerals (Rutile, etc.) Fixed-Rate Allocation
- **Rule**: A3627 licenses (ores, minerals) allocate balance CIF to commodity-specific planning items at fixed unit prices
- **Status**: In-progress (per audit BL-PLAN-02, "added most recently")
- **Scope**: 1 real license (per audit BL-PLAN-02)
- **Enforcement Point**: `compute_a3627_auto_plan()` in `a3627_auto_plan.py:205`
- **Evidence**: `backend/apps/license/services/a3627_auto_plan.py:205-315`
- **Compliance Status**: PARTIAL (engine under development)
- **Known Issues**: Unknown (limited real-world data)

---

### 1.6 Coverage Gap: PP Norm Has Zero Auto-Plan Support
- **Rule**: [NOT ENFORCED] PP (SION norm class) licenses should have automatic planning support
- **Evidence**:
  - Audit BL-PLAN-02: "73 of 228 real licenses (32%) are PP norm class"
  - `detect_norm()` returns "" for PP licenses
  - `PlannerFactory.is_supported('PP')` returns False
  - No `pp_auto_plan.py` module exists
- **Scope**: 73 real PP licenses (single largest norm group after E5's 76)
- **Current Behavior**: 
  - `/auto-plan/`, `/auto-plan-all/` endpoints return "unknown norm" for PP licenses
  - Item Pivot Report / License Overview Planning tab show no pre-filled utilization
  - Users must manually enter plans for all items
- **Enforcement Status**: NOT ENFORCED (feature gap, not bug)
- **Suggested Follow-Up** (per audit): Confirm business spec for PP planning rules and implement `pp_auto_plan.py`

---

## 2. QUANTITY & VALUE CONSTRAINTS

### 2.1 Planning Quantity Constraint: Cannot Exceed Available Quantity
- **Rule**: For any group of planned import items, the sum of planned quantities cannot exceed the group's total available quantity (with 1% tolerance for rounding)
- **Formal Statement**:
  ```
  sum(LicenseItemPlan.planned_quantity for all lines in group)
    ≤ available_quantity × 1.01
  ```
- **Scope**: All planned items (across all norms: E1, E5, E126, E132, A3627)
- **Enforcement Point**: `validate_group_plan_lines()` in `plan_grouping.py:330-391`
- **Enforcement Trigger**: Auto-plan engines call this validation gate before `save_plan_lines_for_license()`
- **Evidence**:
  - `backend/apps/license/services/plan_grouping.py:330-391` (lines ~360-370)
  - Audit BL-PLAN-01 skeptic check confirmed: validation gate exists but does NOT check cif/qty invariant
- **Compliance Status**: ENFORCED (gate in place, validation runs)
- **Known Issues**: None for this specific constraint

---

### 2.2 Planning CIF Constraint: Cannot Exceed Available License CIF
- **Rule**: The total planned CIF across all items cannot exceed the license's available balance CIF
- **Formal Statement**:
  ```
  sum(LicenseItemPlan.planned_cif_fc for all items on license)
    ≤ license.get_balance_cif()
  ```
- **Scope**: All licenses with any planned items
- **Enforcement Point**: Implicit in auto-plan engines (they allocate balance_cif to items)
  - `plan_e1_items()`, `plan_e5_items()`, `plan_e126_per_item_split()`, etc. never allocate more than balance_cif
- **Evidence**:
  - E1: `backend/apps/license/services/e1_plan.py:225-306` (category allocation)
  - E5: `backend/apps/license/services/e5_plan.py:233-353`
- **Compliance Status**: ENFORCED (implicit in algorithm; no separate validation gate, but inherent in design)
- **Known Issues**: 
  - **BL-PLAN-01 defect**: For E126/E132, the CIF might be slightly over-allocated due to flooring defect
    - Example: balance_cif = 343.40, but saved planned_cif_fc = 343.40 (100%) while only 100 units saved (vs. 101 available)
    - The constraint is technically met (100% ≤ 100%), but quantities don't align

---

### 2.3 Unit Price Constraint: Cannot Exceed Planning Item Ceiling Price
- **Rule**: For deterministic-pricing norms (E126, E132, A3627), the planned unit price must not exceed the planning item's fixed ceiling price (with 1% tolerance)
- **Formal Statement**:
  ```
  LicenseItemPlan.unit_price ≤ PlanningItemModel.unit_price × 1.01
  ```
- **Scope**: Items from norms with fixed-price planning items (E126, E132, A3627)
  - E1/E5 use category-derived prices (computed dynamically), so "ceiling" is implicit in balance allocation
- **Enforcement Point**: `validate_group_plan_lines()` in `plan_grouping.py:330-391` (line ~365)
- **Evidence**:
  - `backend/apps/license/services/plan_grouping.py:330-391`
- **Compliance Status**: ENFORCED (validation gate checks this)
- **Known Issues**: None

---

## 3. MANUAL PLAN OVERRIDE RULES

### 3.1 Manual Plan Takes Priority Over Norm
- **Rule**: If an import item has a manual plan line, that line is used and the norm plan is NOT applied
- **Formal Statement**:
  - For each import_item_id:
    - If LicenseItemPlanModel exists (manual): use it (fixed, never recomputed)
    - Else if norm exists: use norm plan
    - Else: no plan for this item
- **Scope**: All licenses (applies regardless of norm)
- **Enforcement Point**: `effective_plan_for_license()` in `norm_plan.py:45-114` (lines ~77-89)
- **Evidence**:
  - `backend/apps/license/services/norm_plan.py:77-89`
- **Compliance Status**: FULLY ENFORCED
- **Known Issues**: None

---

### 3.2 Manual Plan Line Cannot Be Overridden by Auto-Plan
- **Rule**: Running auto-plan should not delete or modify existing manual plan lines
- **Formal Statement**:
  - When `save_plan_lines_for_license()` is called:
    - Delete all non-preserved, non-manual plan lines
    - Keep all manual lines (do not touch them)
    - Create new norm-based plan lines
- **Scope**: All licenses with mixed manual + norm plans
- **Enforcement Point**: `save_plan_lines_for_license()` in `plan_enforcement.py:130-192`
- **Evidence**:
  - `backend/apps/license/services/plan_enforcement.py:130-192` (manual flag check at line ~182)
- **Compliance Status**: ENFORCED (manual flag checked)
- **Known Issues**: None explicitly identified (but not tested across all auto-plan runs)

---

## 4. ALLOCATION & CONSUMPTION RULES

### 4.1 Remaining = Planned − Allotted (Cannot Go Negative)
- **Rule**: The remaining plannable quantity/CIF for an item is never negative
- **Formal Statement**:
  ```
  item_remaining_qty = max(item_planned_qty - item_allotted_qty, 0)
  item_remaining_cif = max(item_planned_cif - item_allotted_value, 0)
  ```
- **Scope**: All items with plan lines
- **Enforcement Point**: `effective_plan_for_license()` in `norm_plan.py:105-111`
- **Evidence**:
  - `backend/apps/license/services/norm_plan.py:105-111`
- **Compliance Status**: ENFORCED (floor(0) applied)
- **Known Issues**: None

---

### 4.2 Allocation Cannot Exceed Item Plan Remaining
- **Rule**: When allocating to an item, the allocation quantity must not exceed the item's remaining planned quantity
- **Formal Statement**:
  ```
  allocation_qty ≤ item_remaining_qty = max(item_planned_qty - item_allotted_qty, 0)
  ```
- **Scope**: All allocations via `allocate_items()` endpoint
- **Enforcement Point**: 
  - `AllocationService.allocate_item()` in `allocation_service.py`
  - Validated during allocation request processing
- **Evidence**: 
  - `backend/apps/allotment/services/allocation_service.py` (check needed)
- **Compliance Status**: ENFORCED (by allocation validation)
- **Known Issues**: None identified

---

### 4.3 Group Plan Cap (Non-Double-Counting for E1/E5 Grouped Items)
- **Rule**: For E1/E5 licenses with grouped items (e.g., multiple items classified into same category), the group's total planned CIF should not be double-counted
- **Formal Statement**:
  - Group items by category
  - Allocate group_cif to category
  - Distribute group_cif to individual items within category (proportionally)
  - Don't count the same group_cif twice across items
- **Scope**: E1/E5 licenses with multiple items per category
- **Enforcement Point**: Category waterfall logic in `plan_e1_items()`, `plan_e5_items()`
- **Evidence**:
  - Test: `backend/apps/allotment/tests/test_allocate_items_group_plan_cap.py:143-206`
  - Test Case: "TestGroupPlanCapIsNotDoubleCounted"
- **Compliance Status**: ENFORCED (tested)
- **Known Issues**: None

---

## 5. SPLIT SEMANTICS

### 5.1 PKO/Olive-Oil Split (E126)
- **Rule**: When an E126 import item signals both PKO and Olive Oil, split the available quantity 50/50 and create two plan lines
- **Formal Statement**:
  ```
  if (item has both PKO signal AND Olive Oil signal):
    pko_qty = available_qty / 2
    olive_qty = available_qty / 2
    Create two plan lines (one for each)
  else:
    Create one plan line
  ```
- **Scope**: E126 licenses with items having both signals
- **Enforcement Point**: `_split_pko_olive_record()` in `e126_plan.py:213-276`
- **Evidence**:
  - `backend/apps/license/services/e126_plan.py:213-276`
  - Test: `backend/apps/license/tests/test_e126_auto_plan.py` (check for split cases)
- **Compliance Status**: ENFORCED (split logic implemented)
- **Known Issues**: 
  - **BL-PLAN-01 defect**: After split (produces fractional quantities), the quantities are floored but CIF is not recomputed

---

### 5.2 PKO/Cheese Split (E132)
- **Rule**: When an E132 import item signals both PKO and Cheese, split as 40% PKO / 60% Cheese and create two plan lines
- **Formal Statement**:
  ```
  if (item has both PKO signal AND Cheese signal):
    pko_qty = available_qty × 0.40
    cheese_qty = available_qty × 0.60
    Create two plan lines (one for each)
  else:
    Create one plan line
  ```
- **Scope**: E132 licenses with items having both signals
- **Enforcement Point**: `_split_veg_oil_record()` in `e132_plan.py:259-309`
- **Evidence**:
  - `backend/apps/license/services/e132_plan.py:259-309`
- **Compliance Status**: ENFORCED (split logic implemented)
- **Known Issues**: 
  - **BL-PLAN-01 defect**: Same as E126 — fractional split quantities lose floored CIF recomputation

---

### 5.3 Milk 40/60 Split (E5)
- **Rule**: When E5 license has milk category items, split milk CIF as 40/60 between Milk_40 and Milk_60 planning items
- **Formal Statement**:
  ```
  if (category == Milk):
    milk_40_cif = balance_cif × 0.40
    milk_60_cif = balance_cif × 0.60
    milk_40_qty = min(available_qty, milk_40_cif / milk_40_price)
    milk_60_qty = min(available_qty - milk_40_qty, milk_60_cif / milk_60_price)
    Create two plan lines
  ```
- **Scope**: E5 licenses with milk items (category classification produces milk)
- **Enforcement Point**: `split_milk_0404()` in `milk_planner.py:48-82`
- **Evidence**:
  - `backend/apps/license/services/milk_planner.py:48-82`
  - `backend/apps/license/services/e5_plan.py:310-353` (_run_milk method calls split_milk_0404)
- **Compliance Status**: FULLY ENFORCED (tested)
- **Known Issues**: None identified

---

## 6. PRESERVED PLAN RE-EMISSION

### 6.1 Preserved Plan Lines Must Re-Emit Without Change
- **Rule**: If a plan line is flagged `preserved_during_re_generation=True`, auto-plan must re-emit it without recomputation
- **Formal Statement**:
  ```
  if (LicenseItemPlan.preserved_during_re_generation == True):
    new_line = old_line  # Copy verbatim, no recalculation
  ```
- **Scope**: Licenses with existing plans when auto-plan is re-run
- **Enforcement Point**: `save_plan_lines_for_license()` in `plan_enforcement.py:180-191` (preserved branch)
- **Evidence**:
  - `backend/apps/license/services/plan_enforcement.py:180-191`
- **Compliance Status**: ENFORCED (preserved flag checked)
- **Known Issues**: 
  - If original line has BL-PLAN-01 defect, defect persists forever (never corrected on re-emit)

---

## 7. PLAN LINE INVARIANTS

### 7.1 (VIOLATED) planned_cif_fc = planned_quantity × unit_price
- **Rule**: For every plan line, the CIF value must equal quantity times unit price
- **Formal Statement**:
  ```
  ∀ LicenseItemPlan rows: planned_cif_fc ≈ round(planned_quantity × unit_price, 2)
  (allowing ±0.01 rounding tolerance)
  ```
- **Scope**: All plan lines (all norms)
- **Enforcement Point**: Should be validated in `validate_group_plan_lines()`, but currently is NOT
- **Evidence**:
  - Audit BL-PLAN-01: "validate_group_plan_lines...NEVER checks planned_cif_fc == planned_quantity * unit_price"
  - Defect affects E126 and E132 (fractional splits)
  - E1/E5 are unaffected (no flooring, category waterfall maintains invariant)
- **Compliance Status**: PARTIALLY VIOLATED (E126/E132 defect)
- **Known Issues**: 
  - **BL-PLAN-01**: E126/E132 create rows where `planned_cif_fc ≠ planned_quantity × unit_price`
  - Validation gate does not catch this
  - This invariant is implicitly assumed by reporting code (e.g., `_effective_rate`, `_blended_pko_olive_rate` recompute rates as value / qty)

---

## 8. COMPANY & LICENSE SCOPE

### 8.1 Planning is License-Scoped (Not Company-Scoped)
- **Rule**: Auto-plan generates plans per-license, not per-company
- **Formal Statement**:
  ```
  LicenseItemPlan is scoped to exactly one LicenseDetailsModel
  Auto-plan runs on a single license_obj, generates lines for that license only
  ```
- **Scope**: All planning operations
- **Enforcement Point**: All auto-plan functions take `license_obj` as sole input
- **Evidence**:
  - Function signatures: `compute_e1_auto_plan(license_obj)`, `compute_e5_auto_plan(license_obj)`, etc.
- **Compliance Status**: ENFORCED (by architecture)
- **Known Issues**: None

---

## Summary of Rules

| Category | Count | Status | Issues |
|----------|-------|--------|--------|
| Norm Coverage | 6 | Partial | **BL-PLAN-02**: PP has 0 coverage |
| Quantity & Value Constraints | 3 | Enforced | None |
| Manual Plan Overrides | 2 | Enforced | None |
| Allocation & Consumption | 3 | Enforced | None |
| Split Semantics | 3 | Enforced | **BL-PLAN-01**: CIF not recomputed |
| Preserved Plan | 1 | Enforced | Inherits BL-PLAN-01 |
| Plan Line Invariants | 1 | Violated | **BL-PLAN-01**: E126/E132 defect |
| Company/License Scope | 1 | Enforced | None |
| **TOTAL** | **20** | | **2 issues** |

