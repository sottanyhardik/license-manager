# MODULE 2 — PLANNING FUNCTIONS INVENTORY

## Overview

This document consolidates every function, method, and callable related to planning/auto-planning in the License Manager system. Each entry includes:
- **Function name and location**
- **Caller → Called relationship**
- **Input/Output types**
- **Function type** (Financial | Validation | Business Rule | Classification | Infrastructure)
- **Test coverage** (if known)

---

## 1. NORM DETECTION & DISPATCH LAYER

### 1.1 detect_norm()
- **File**: `backend/apps/license/services/norm_plan.py:23`
- **Signature**: `detect_norm(license_obj) → str`
- **Function Type**: Classification
- **Purpose**: Determine which planning norm (E1/E5/E126/E132/A3627) applies to a license
- **Input**: `LicenseDetailsModel` instance
- **Output**: Norm code string ('E1' | 'E5' | 'E126' | 'E132' | 'A3627' | '')
- **Business Rules**:
  - Checks `license_obj.export_license.first().norm_class.norm_class`
  - E132 takes priority over E126 in code path
  - E126 takes priority over E5
  - E5 takes priority over E1
  - Any code containing "E1" (but not E126/E132) returns "E1"
  - Returns "" if no recognized norm
- **Callers**: 
  - `effective_plan_for_license()`
  - `norm_plan_for_license()`
  - `PlannerFactory.run()` (via views)
  - Auto-plan API endpoints
- **Evidence**: `backend/apps/license/services/norm_plan.py:23-42`
- **Confidence**: HIGH
- **Test Coverage**: Indirectly tested via e1/e5/e126/e132 auto-plan tests

---

### 1.2 PlannerFactory.register()
- **File**: `backend/apps/license/services/planner_factory.py:51`
- **Signature**: `register(norm_code: str, fn: Callable) → None`
- **Function Type**: Infrastructure (Registry)
- **Purpose**: Register a planner function for a norm code
- **Input**: norm code string, callable(license_obj) → (lines, remaining_cif)
- **Output**: None (modifies module-global _REGISTRY)
- **Callers**: `_load_defaults()`, custom norm registration
- **Evidence**: `backend/apps/license/services/planner_factory.py:51-58`
- **Confidence**: HIGH

---

### 1.3 PlannerFactory.supported_norms()
- **File**: `backend/apps/license/services/planner_factory.py:61`
- **Signature**: `supported_norms() → list[str]`
- **Function Type**: Infrastructure (Registry Query)
- **Purpose**: List all registered planner norm codes
- **Output**: Sorted list of registered norm codes ['A3627', 'E1', 'E126', 'E132', 'E5']
- **Evidence**: 
  - Code: `backend/apps/license/services/planner_factory.py:61-63`
  - Audit BL-PLAN-02: "PlannerFactory.supported_norms() = ['A3627', 'E1', 'E126', 'E132', 'E5'] — PP is absent"
- **Confidence**: HIGH

---

### 1.4 PlannerFactory.is_supported()
- **File**: `backend/apps/license/services/planner_factory.py:66`
- **Signature**: `is_supported(norm_code: str) → bool`
- **Function Type**: Infrastructure (Registry Query)
- **Purpose**: Check if a norm code has a registered planner
- **Input**: norm code string (e.g. 'E1', 'PP')
- **Output**: Boolean
- **Evidence**: 
  - Code: `backend/apps/license/services/planner_factory.py:66-68`
  - Audit BL-PLAN-02: "PlannerFactory.is_supported('PP') is False"
- **Confidence**: HIGH

---

### 1.5 PlannerFactory.run()
- **File**: `backend/apps/license/services/planner_factory.py:71`
- **Signature**: `run(license_obj, norm_code: str) → PlanResult`
- **Function Type**: Infrastructure (Dispatch Orchestrator)
- **Purpose**: Execute the registered planner for a norm against a license
- **Input**: 
  - `license_obj`: LicenseDetailsModel instance
  - `norm_code`: str (e.g. 'E1', 'E5')
- **Output**: PlanResult dataclass with:
  - `lines`: list[dict] — planned item lines (each with planned_quantity, unit_price, planned_cif_fc)
  - `remaining_cif`: float — CIF not allocated to any plan line
- **Error Handling**: Raises `ValueError` if norm_code not registered
- **Callers**: 
  - `backend/apps/license/views/item_plan.py:auto_plan()`
  - `backend/apps/license/views/item_plan.py:auto_plan_all()`
  - `backend/apps/license/views/item_plan.py:e1_auto_plan()`
- **Evidence**: `backend/apps/license/services/planner_factory.py:71-90`
- **Confidence**: HIGH

---

## 2. NORM-SPECIFIC PLANNING ENGINES

### 2.1 E1 Auto-Plan

#### 2.1.1 compute_e1_auto_plan()
- **File**: `backend/apps/license/services/e1_auto_plan.py:96`
- **Signature**: `compute_e1_auto_plan(license_obj) → (lines, remaining_cif)`
- **Function Type**: Financial (Auto-Plan Engine)
- **Purpose**: Generate automatic plan lines for E1 licenses
- **Output Format**: 
  - `lines`: list[dict] with keys: planned_quantity, unit_price, planned_cif_fc, planning_item_id, planning_item_name
  - `remaining_cif`: float (balance_cif - sum(planned_cif_fc))
- **Internal Calls**:
  - `plan_e1_items()` — core category waterfall
  - `plan_enforcement.save_plan_lines_for_license()` — persist lines
  - `plan_enforcement.plan_status_for_items()` — retrieve existing plans for merge
- **Business Logic**:
  - Classifies each import item into an E1 category
  - Runs category waterfall (allocates balance_cif proportionally)
  - Creates LicenseItemPlan rows with remaining_quantity = planned_quantity (non-preserved branch)
  - For preserved=True branch, re-emits existing lines without recomputation
- **Test Coverage**: 
  - `backend/apps/license/tests/test_e1_auto_plan.py` (multiple test cases)
  - `backend/apps/allotment/tests/test_allocate_items_e1_group_plan_cap.py`
- **Evidence**: `backend/apps/license/services/e1_auto_plan.py:96-148`
- **Confidence**: HIGH

#### 2.1.2 classify_e1_item()
- **File**: `backend/apps/license/services/e1_plan.py:88`
- **Signature**: `classify_e1_item(item_name: str, hs_code: str, description: str) → str`
- **Function Type**: Classification
- **Purpose**: Classify an import item into an E1 category (code-based, not price-based)
- **Input**:
  - `item_name`: planning item name or description
  - `hs_code`: HS code string
  - `description`: import item description
- **Output**: E1 category code (e.g. 'Cereals', 'Sugar', 'Spices') or empty string if unclassified
- **Evidence**: `backend/apps/license/services/e1_plan.py:88-156`
- **Confidence**: HIGH

#### 2.1.3 plan_e1_items()
- **File**: `backend/apps/license/services/e1_plan.py:225`
- **Signature**: `plan_e1_items(items: list[E1Item], balance_cif: Decimal) → E1PlanResult`
- **Function Type**: Financial (Category Waterfall)
- **Purpose**: Run the E1 category waterfall algorithm
- **Input**:
  - `items`: list of E1Item(key=import_item_id, category=category_code, qty=available_qty)
  - `balance_cif`: Available CIF budget (Decimal)
- **Output**: E1PlanResult with planned lines (each: key, category, planned_quantity, planned_cif)
- **Business Logic**: 
  - Groups items by category
  - Allocates CIF proportionally to category weight (sum of available quantities)
  - Computes unit price = category_cif / category_qty
  - Per-item planned_quantity = item_qty, unit_price = category unit price, planned_cif = qty × price
- **Evidence**: `backend/apps/license/services/e1_plan.py:225-306`
- **Confidence**: HIGH
- **Related**: E1PlanResult, E1Item, E1PlanLine classes

---

### 2.2 E5 Auto-Plan

#### 2.2.1 compute_e5_auto_plan()
- **File**: `backend/apps/license/services/e5_auto_plan.py:128`
- **Signature**: `compute_e5_auto_plan(license_obj) → (lines, remaining_cif)`
- **Function Type**: Financial (Auto-Plan Engine)
- **Purpose**: Generate automatic plan lines for E5 licenses
- **Output Format**: lines and remaining_cif (same as E1)
- **Internal Calls**: Similar to E1 (plan_e5_items, save_plan_lines_for_license)
- **Business Logic**:
  - Similar to E1 (category waterfall), but with E5-specific categories
  - Includes milk 40/60 split logic
- **Test Coverage**: 
  - `backend/apps/license/tests/test_e5_auto_plan.py`
  - `backend/apps/allotment/tests/test_allocate_items_group_plan_cap.py`
- **Evidence**: `backend/apps/license/services/e5_auto_plan.py:128-244`
- **Confidence**: HIGH

#### 2.2.2 classify_e5_item()
- **File**: `backend/apps/license/services/e5_plan.py:95`
- **Signature**: `classify_e5_item(item_name: str, hs_code: str, description: str) → str`
- **Function Type**: Classification
- **Purpose**: Classify an import item into an E5 category
- **Output**: E5 category code ('Oils', 'Cereals', 'Pulses', 'Spices', 'Milk') or ""
- **Evidence**: `backend/apps/license/services/e5_plan.py:95-148`
- **Confidence**: HIGH

#### 2.2.3 plan_e5_items()
- **File**: `backend/apps/license/services/e5_plan.py:233`
- **Signature**: `plan_e5_items(items: list[E5Item], balance_cif: Decimal) → E5PlanResult`
- **Function Type**: Financial (Category Waterfall)
- **Purpose**: Run the E5 category waterfall algorithm
- **Business Logic**:
  - Similar to E1, but E5 includes:
    - Oils category: uses `_run_oils()` method (may generate split lines for milk)
    - Milk category: uses `_run_milk()` method (applies 40/60 split for E5, calls `milk_planner.plan_milk()`)
  - Calls `split_milk_0404()` for milk split allocation
- **Evidence**: `backend/apps/license/services/e5_plan.py:233-353`
- **Confidence**: HIGH

---

### 2.3 E126 Auto-Plan

#### 2.3.1 compute_e126_auto_plan()
- **File**: `backend/apps/license/services/e126_auto_plan.py:118`
- **Signature**: `compute_e126_auto_plan(license_obj) → (lines, remaining_cif)`
- **Function Type**: Financial (Auto-Plan Engine)
- **Purpose**: Generate automatic plan lines for E126 licenses
- **Output Format**: lines and remaining_cif (same as E1/E5)
- **Known Defect** (AUDIT BL-PLAN-01):
  - **Issue**: planned_cif_fc is computed from the UN-FLOORED planned_quantity, never recomputed after floor
  - **Effect**: For fractional available quantities, saved LicenseItemPlan.planned_cif_fc != planned_quantity * unit_price
  - **Root Cause**: 
    ```python
    fqty = _floor_qty(planned_qty)    # floors to whole number
    cif  = _r2(planned_cif)           # keeps CIF computed from UN-FLOORED qty
    item_lines.append({'planned_quantity': fqty, 'planned_cif_fc': cif, ...})  # MISMATCH
    ```
  - **Correct Pattern** (from E5): `planned_cif = fqty * unit_price` (recompute from floored qty)
  - **Evidence**: 
    - `backend/apps/license/services/e126_auto_plan.py:242-266`
    - Audit BL-PLAN-01 independent verification: `backend/apps/license/services/e126_auto_plan.py:242-266` confirmed verbatim
- **Test Coverage**: Tests exercise only even quantities (never trigger the bug)
- **Internal Calls**:
  - `plan_e126_per_item_split()` — classification & allocation
  - `save_plan_lines_for_license()` — persist (propagates the mismatch)
- **Evidence**: `backend/apps/license/services/e126_auto_plan.py:118-338`
- **Confidence**: HIGH (defect is confirmed by independent verification)

#### 2.3.2 classify_e126_record()
- **File**: `backend/apps/license/services/e126_plan.py:161`
- **Signature**: `classify_e126_record(record) → (planning_item_id, reason, planned_qty, unit_price, planned_cif)`
- **Function Type**: Classification
- **Purpose**: Classify an import item for E126 (PKO/Olive-Oil split)
- **Output**: Named tuple with classification result
- **Business Logic**:
  - E126 imports HSN 1513 (vegetable oils) and groups them as Nuts/PKO/Olive-Oil splits
  - Classifies each record into one of 3 planning items
  - Triggers 50/50 PKO/Olive-Oil split when both signals present
- **Evidence**: `backend/apps/license/services/e126_plan.py:161-185`
- **Confidence**: HIGH

#### 2.3.3 plan_e126_per_item_split()
- **File**: `backend/apps/license/services/e126_plan.py:472`
- **Signature**: `plan_e126_per_item_split(import_item) → dict`
- **Function Type**: Financial
- **Purpose**: Generate E126 plan for a single import item (may produce 2 lines if split)
- **Output**: {planning_item_id: {planned_quantity, unit_price, planned_cif}}
- **Business Logic**:
  - Uses fractional available_quantity (before flooring)
  - Splits may create fractional planned_quantity
  - E.g., for PKO+Olive-Oil split with available_qty=101: each gets 50.5 (then floored to 50 in auto_plan.py)
- **Evidence**: `backend/apps/license/services/e126_plan.py:472-515`
- **Confidence**: HIGH

---

### 2.4 E132 Auto-Plan

#### 2.4.1 compute_e132_auto_plan()
- **File**: `backend/apps/license/services/e132_auto_plan.py:115`
- **Signature**: `compute_e132_auto_plan(license_obj) → (lines, remaining_cif)`
- **Function Type**: Financial (Auto-Plan Engine)
- **Purpose**: Generate automatic plan lines for E132 licenses (vegetable oils + dairy)
- **Known Defect** (AUDIT BL-PLAN-01):
  - **Issue**: Identical to E126 — planned_cif_fc computed from UN-FLOORED quantity
  - **Effect**: For PKO/Cheese 40/60 split with fractional groups, saved rows have cif_fc mismatch
  - **Evidence**: 
    - `backend/apps/license/services/e132_auto_plan.py:239-269`
    - Audit BL-PLAN-01: "e132_auto_plan.py has the identical _floor_qty/_r2 helper pair"
- **Coverage Gap** (AUDIT BL-PLAN-02):
  - Only 2 real E132 licenses in current DB (both with items below MIN_PLAN_QTY = 50)
  - However, real E132 coverage gap is covered by BL-PLAN-02 (PP norm has zero coverage)
- **Internal Calls**: plan_e132_per_item_split(), save_plan_lines_for_license()
- **Evidence**: `backend/apps/license/services/e132_auto_plan.py:115-286`
- **Confidence**: HIGH (defect same as E126)

#### 2.4.2 classify_e132_record()
- **File**: `backend/apps/license/services/e132_plan.py:199`
- **Signature**: `classify_e132_record(record) → (planning_item_id, reason, planned_qty, unit_price, planned_cif)`
- **Function Type**: Classification
- **Purpose**: Classify an import item for E132 (vegetable oils + dairy)
- **Business Logic**:
  - E132 covers oils (RBD/PKO signal) and dairy (Cheese/Yeast/Milk signals)
  - Classifies into 6 planning items: Nuts / Yeast / PKO / RBD / Cheese / Aluminium
  - Can trigger 40/60 PKO/Cheese split
- **Evidence**: `backend/apps/license/services/e132_plan.py:199-231`
- **Confidence**: HIGH

#### 2.4.3 plan_e132_per_item_split()
- **File**: `backend/apps/license/services/e132_plan.py:532`
- **Signature**: `plan_e132_per_item_split(import_item) → dict`
- **Function Type**: Financial
- **Purpose**: Generate E132 plan for a single import item (may produce 2 lines if split)
- **Output**: {planning_item_id: {planned_quantity, unit_price, planned_cif}}
- **Evidence**: `backend/apps/license/services/e132_plan.py:532-575`
- **Confidence**: HIGH

---

### 2.5 A3627 Auto-Plan

#### 2.5.1 compute_a3627_auto_plan()
- **File**: `backend/apps/license/services/a3627_auto_plan.py:205`
- **Signature**: `compute_a3627_auto_plan(license_obj) → (lines, remaining_cif)`
- **Function Type**: Financial (Auto-Plan Engine)
- **Purpose**: Generate automatic plan lines for A3627 licenses (ores/minerals — rutile, etc.)
- **Status**: In-progress (per audit BL-PLAN-02, "added most recently")
- **Business Logic**:
  - Uses fixed-rate allocation (similar to E5's per-category rates)
  - Includes import-price averaging
- **Evidence**: `backend/apps/license/services/a3627_auto_plan.py:205-315`
- **Confidence**: MEDIUM (new engine, under development)

---

## 3. PLAN ENFORCEMENT & PERSISTENCE

### 3.1 save_plan_lines_for_license()
- **File**: `backend/apps/license/services/plan_enforcement.py:130`
- **Signature**: `save_plan_lines_for_license(license_id, plan_lines: list[dict], remaining_cif=None) → None`
- **Function Type**: Infrastructure (Persistence)
- **Purpose**: Create or update LicenseItemPlan rows from auto-plan output
- **Input**:
  - `plan_lines`: list of dicts with keys: planned_quantity, unit_price, planned_cif_fc, planning_item_id
  - `remaining_cif`: unused CIF after planning
- **Business Logic**:
  - Deletes all existing non-preserved plan lines for the license
  - For each line dict:
    - If `preserved_during_re_generation=True`: re-emit unchanged (skip recomputation)
    - If fresh (non-preserved): create new LicenseItemPlan with remaining_quantity = planned_quantity, remaining_cif_fc = planned_cif_fc
  - **Critical**: remaining_cif_fc is set to planned_cif_fc verbatim (inherits any mismatch from planned_cif_fc != qty*price)
- **Effect of BL-PLAN-01 Defect**:
  - For E126/E132 with fractional available quantities, the cif/quantity mismatch is baked into remaining_cif_fc
  - This is then used by allocation logic and ledger calculations
- **Callers**: Every auto-plan compute function (e1/e5/e126/e132/a3627_auto_plan.py)
- **Evidence**: 
  - Code: `backend/apps/license/services/plan_enforcement.py:130-192`
  - Audit BL-PLAN-01: "save_plan_lines_for_license (plan_enforcement.py) then sets remaining_cif_fc = planned_cif_fc verbatim for a fresh (non-preserved) line, so the inconsistency is baked into the row"
- **Confidence**: HIGH

---

### 3.2 plan_status_for()
- **File**: `backend/apps/license/services/plan_enforcement.py:243`
- **Signature**: `plan_status_for(license_id, import_item_id) → dict`
- **Function Type**: Infrastructure (Query)
- **Purpose**: Get the plan status for a single import item (used by allocation validation)
- **Output**: dict with:
  - `planned_quantity`: Total planned across all plan lines for this item
  - `allocated_quantity`: Total allocated across all allotments for this item
  - `remaining_quantity`: plan - allocated (floored at 0)
  - `planned_value`: Total planned CIF
  - `allocated_value`: Total allocated CIF
  - `remaining_value`: plan - allocated (floored at 0)
- **Used For**: Validation during allocation (prevent over-allocation beyond plan)
- **Evidence**: `backend/apps/license/services/plan_enforcement.py:243-276`
- **Confidence**: HIGH

---

### 3.3 plan_status_for_items()
- **File**: `backend/apps/license/services/plan_enforcement.py:278`
- **Signature**: `plan_status_for_items(license_id, import_item_ids) → dict`
- **Function Type**: Infrastructure (Batch Query)
- **Purpose**: Batch version of plan_status_for() (used by auto-plan compute functions)
- **Output**: {import_item_id: plan_status_dict}
- **Evidence**: `backend/apps/license/services/plan_enforcement.py:278-329`
- **Confidence**: HIGH

---

## 4. PLAN GROUPING & VALIDATION

### 4.1 validate_group_plan_lines()
- **File**: `backend/apps/license/services/plan_grouping.py:330`
- **Signature**: `validate_group_plan_lines(license_obj, group_id, plan_lines) → (is_valid, errors)`
- **Function Type**: Validation (Business Rules)
- **Purpose**: Validate that a set of auto-plan lines meet business constraints
- **Input**:
  - `license_obj`: LicenseDetailsModel
  - `group_id`: import item group identifier (items with same norm classification)
  - `plan_lines`: list of plan line dicts
- **Output**: (is_valid: bool, errors: list[str])
- **Business Rules Checked**:
  1. `unit_price <= ceiling_price + tolerance` (e.g., fixed planning item rates, margin bounds)
  2. `total_planned_quantity <= available_quantity + tolerance`
  3. **Does NOT check**: `planned_cif_fc == planned_quantity * unit_price` (per audit BL-PLAN-01)
- **Evidence**:
  - Code: `backend/apps/license/services/plan_grouping.py:330-391`
  - Audit BL-PLAN-01: "validate_group_plan_lines...checks ONLY (a) unit_price <= ceiling price + tolerance, and (b) total planned_quantity <= avail_qty + tolerance. It NEVER checks planned_cif_fc == planned_quantity * unit_price."
- **Confidence**: HIGH

---

### 4.2 merge_planned_import_items()
- **File**: `backend/apps/license/services/plan_grouping.py:99`
- **Signature**: `merge_planned_import_items(import_items) → dict`
- **Function Type**: Infrastructure (Grouping)
- **Purpose**: Merge multiple import items into planning groups (e.g., for E126 PKO/Olive-Oil split)
- **Business Logic**:
  - Groups items by norm classification
  - Aggregates quantities and CIF for each group
- **Evidence**: `backend/apps/license/services/plan_grouping.py:99-170`
- **Confidence**: HIGH

---

## 5. EFFECTIVE/LIVE PLANNING

### 5.1 effective_plan_for_license()
- **File**: `backend/apps/license/services/norm_plan.py:45`
- **Signature**: `effective_plan_for_license(license_obj, balance_cif=None) → (source, plan_map)`
- **Function Type**: Financial (Composite Plan)
- **Purpose**: Get the effective per-item plan for a license (manual overrides + norm fill + remaining)
- **Output**: 
  - `source`: 'manual' | 'norm' | ''
  - `plan_map`: {import_item_id: {planned_quantity, unit_price, planned_cif}}
- **Composition**:
  1. MANUAL FIRST: If an import item has a manual plan line, use it (fixed, never overridden)
  2. NORM FILLS: Items without manual lines use the norm (E1/E5/E126/E132/A3627) plan
  3. REMAINING: planned_qty/cif reduced by allotted amounts (floored at 0)
- **Consumers**:
  - Item Pivot Report (planning display)
  - Balance Excel export (pre-filled utilization)
  - License Overview Planning tab
  - Allocation form pre-fill
- **Evidence**: `backend/apps/license/services/norm_plan.py:45-114`
- **Confidence**: HIGH

---

### 5.2 norm_plan_for_license()
- **File**: `backend/apps/license/services/norm_plan.py:117`
- **Signature**: `norm_plan_for_license(license_obj, balance_cif=None) → dict`
- **Function Type**: Financial (Norm Plan Query)
- **Purpose**: Get the norm-based (non-manual) per-item plan for a license
- **Output**: {import_item_id: {planned_quantity, unit_price, planned_cif}}
- **Per-Norm Logic**:
  - **E1/E5**: Calls `plan_e1_items()` / `plan_e5_items()` → category waterfall (shared with reports)
  - **E126**: Calls `plan_e126_per_item()` (deterministic classification)
  - **E132**: Calls `plan_e132_per_item()` (deterministic classification)
  - **A3627**: Calls `compute_a3627_auto_plan()` (fixed-rate allocation)
- **Critical Detail**: 
  - Delegates to the SAME per-item engine used by Item Pivot Report
  - Ensures pre-filled plan lines always match what reports show
- **Evidence**: `backend/apps/license/services/norm_plan.py:117-254`
- **Confidence**: HIGH

---

## 6. LIVE ALLOTMENT TRACKING

### 6.1 live_allotted_qty()
- **File**: `backend/apps/license/services/plan_enforcement.py:48`
- **Signature**: `live_allotted_qty(license_id) → float`
- **Function Type**: Infrastructure (Query)
- **Purpose**: Calculate total quantity allotted across all items for a license
- **Business Logic**: Sums `AllotmentItems.allocated_quantity` for all items on the license
- **Evidence**: `backend/apps/license/services/plan_enforcement.py:48-58`
- **Confidence**: HIGH

---

### 6.2 live_allotted_value()
- **File**: `backend/apps/license/services/plan_enforcement.py:59`
- **Signature**: `live_allotted_value(license_id) → float`
- **Function Type**: Infrastructure (Query)
- **Purpose**: Calculate total CIF allotted across all items for a license
- **Business Logic**: Sums `AllotmentItems.allocated_value` for all items on the license
- **Evidence**: `backend/apps/license/services/plan_enforcement.py:59-69`
- **Confidence**: HIGH

---

### 6.3 live_allotted_qty_for()
- **File**: `backend/apps/license/services/plan_enforcement.py:70`
- **Signature**: `live_allotted_qty_for(import_item_id) → float`
- **Function Type**: Infrastructure (Query)
- **Purpose**: Get the total quantity allotted for a single import item
- **Business Logic**: Sums `AllotmentItems.allocated_quantity` for this item
- **Evidence**: `backend/apps/license/services/plan_enforcement.py:70-80`
- **Confidence**: HIGH

---

### 6.4 live_allotted_value_for()
- **File**: `backend/apps/license/services/plan_enforcement.py:81`
- **Signature**: `live_allotted_value_for(import_item_id) → float`
- **Function Type**: Infrastructure (Query)
- **Purpose**: Get the total CIF allotted for a single import item
- **Evidence**: `backend/apps/license/services/plan_enforcement.py:81-91`
- **Confidence**: HIGH

---

## 7. MILK PLANNING (E5 & E132 SUB-COMPONENT)

### 7.1 plan_milk()
- **File**: `backend/apps/license/services/milk_planner.py:84`
- **Signature**: `plan_milk(raw_milk_qty_kg: Decimal, balance_cif: Decimal, config: MilkConfig) → dict`
- **Function Type**: Financial (Category Waterfall — Milk Sub-Engine)
- **Purpose**: Allocate milk CIF to a set of milk planning items (e.g., 40/60 split for E5)
- **Business Logic**:
  - Takes raw milk quantity and allocates to planning items (Milk_40, Milk_60 for E5 or similar for E132)
  - Respects per-item ceiling prices and quantity constraints
  - Returns {planning_item_id: {planned_quantity, unit_price, planned_cif}}
- **Evidence**: `backend/apps/license/services/milk_planner.py:84-186`
- **Confidence**: HIGH

---

### 7.2 split_milk_0404()
- **File**: `backend/apps/license/services/milk_planner.py:48`
- **Signature**: `split_milk_0404(available_qty: Decimal, balance_cif: Decimal, config: MilkConfig) → dict`
- **Function Type**: Financial (40/60 Split Logic)
- **Purpose**: Execute 40/60 milk split (E5/E132 specific)
- **Business Logic**:
  - Allocates 40% of CIF to first planning item, 60% to second
  - Respects ceiling prices
  - Returns {planning_item_id: {planned_quantity, unit_price, planned_cif}}
- **Evidence**: `backend/apps/license/services/milk_planner.py:48-82`
- **Confidence**: HIGH

---

## 8. API ENDPOINTS & VIEWS

### 8.1 auto_plan()
- **File**: `backend/apps/license/views/item_plan.py:376`
- **Signature**: `POST /auto-plan/` → Response
- **Function Type**: Infrastructure (HTTP Endpoint)
- **Purpose**: Generate auto-plan for a single license via HTTP
- **Input**: license_id (path parameter)
- **Output**: HTTP response with generated plan lines
- **Internal Flow**:
  1. Retrieve license
  2. Call `detect_norm(license_obj)`
  3. If supported, call `PlannerFactory.run(license_obj, norm_code)`
  4. Persist via `save_plan_lines_for_license()`
  5. Return response
- **Error Handling**: Returns "unknown norm" if norm not supported (BL-PLAN-02 issue: PP licenses return this)
- **Evidence**: `backend/apps/license/views/item_plan.py:376-455`
- **Confidence**: HIGH

---

### 8.2 auto_plan_all()
- **File**: `backend/apps/license/views/item_plan.py:457`
- **Signature**: `POST /auto-plan-all/` → Response
- **Function Type**: Infrastructure (HTTP Endpoint)
- **Purpose**: Generate auto-plan for all licenses (batch operation)
- **Business Logic**: Iterates over all licenses, calls `auto_plan()` for each
- **Evidence**: `backend/apps/license/views/item_plan.py:457-518`
- **Confidence**: HIGH

---

### 8.3 e1_auto_plan()
- **File**: `backend/apps/license/views/item_plan.py:295`
- **Signature**: `POST /e1-auto-plan/` → Response
- **Function Type**: Infrastructure (HTTP Endpoint)
- **Purpose**: Explicitly run E1 auto-plan (ignores detected norm)
- **Evidence**: `backend/apps/license/views/item_plan.py:295-374`
- **Confidence**: HIGH

---

## 9. SUPPORTING UTILITIES

### 9.1 ensure_plan_item_names()
- **File**: `backend/apps/license/services/auto_plan_shared.py:12`
- **Signature**: `ensure_plan_item_names(license_obj) → None`
- **Function Type**: Infrastructure (Setup)
- **Purpose**: Ensure all planning items referenced by a license's norm exist in PlanningItemModel
- **Business Logic**: Creates any missing planning items (e.g., "MILK_40" if missing)
- **Evidence**: `backend/apps/license/services/auto_plan_shared.py:12-39`
- **Confidence**: HIGH

---

### 9.2 planned_totals_for()
- **File**: `backend/apps/license/services/plan_enforcement.py:92`
- **Signature**: `planned_totals_for(license_id) → (total_qty, total_cif)`
- **Function Type**: Infrastructure (Query)
- **Purpose**: Get aggregate planned quantity and CIF for a license
- **Business Logic**: Sums `LicenseItemPlan.planned_quantity` and `planned_cif_fc`
- **Evidence**: `backend/apps/license/services/plan_enforcement.py:92-115`
- **Confidence**: HIGH

---

## Summary Statistics

| Category | Count | Status |
|----------|-------|--------|
| Norm Detection | 4 | HIGH confidence |
| Auto-Plan Engines | 5 | E1/E5 HIGH, E126/E132 with defect, A3627 in-progress |
| Classification Functions | 5 | HIGH confidence |
| Enforcement/Persistence | 10+ | HIGH confidence |
| API Endpoints | 3 | HIGH confidence |
| **KNOWN DEFECTS** | **2** | **BL-PLAN-01 (E126/E132 cif mismatch), BL-PLAN-02 (PP coverage gap)** |

