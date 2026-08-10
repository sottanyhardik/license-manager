# MODULE 2 — PLANNING FUNCTIONS INVENTORY

## Overview

Planning functions in the License Manager are organized across multiple layers:
1. **Norm Detection** — identify which auto-planning engine to use
2. **Norm Planning** — per-import-item effective plan computation
3. **Auto-Plan Engines** — generate plan lines from license data
4. **Plan Enforcement** — track remaining quantities, validate allocations
5. **Plan Persistence** — save/load plan lines to database

---

## 1. Norm Detection Layer

### `detect_norm(license_obj) -> str`

**File:** `backend/apps/license/services/norm_plan.py:23`

**Type:** Utility function  
**Caller:** PlannerFactory, norm_plan_for_license, effective_plan_for_license  
**Called By:** Multiple, used extensively in planning dispatch

**Purpose:** Determine which auto-planning engine (E1/E5/E126/E132/A3627/PP) applies to a license

**Inputs:**
- `license_obj` — a License model instance

**Output:** 
- `'E1'` | `'E5'` | `'E126'` | `'E132'` | `'A3627'` | `''` (empty string if no norm matches)

**Business Logic:**
1. Read license's first export-item `norm_class`
2. Match against whitelist:
   - Exact match: `E132`, `E126`, `E5`, `A3627`
   - Partial match: `"E1" in code` (but exclude E126/E132)
   - No match: return `""`

**Evidence Type:** Code, verified by unit test  
**Confidence:** High  
**Financial Impact:** No  
**Validation Impact:** Determines which validation rules apply  
**Notes:** PP norm (73 real licenses) currently unmapped — returns `""` for all 73 (see BL-PLAN-02)

---

### `PlannerFactory.register(norm_code: str, fn: Callable) -> None`

**File:** `backend/apps/license/services/planner_factory.py:51`

**Type:** Static facade for extensible dispatch  
**Caller:** Called at module import time via `_load_defaults()`  
**Called By:** Manual registration (not called dynamically)

**Purpose:** Register a new norm auto-planner

**Inputs:**
- `norm_code` — Upper-case string (e.g., 'E6', 'PP')
- `fn` — Callable `fn(license_obj) -> (lines, remaining_cif)`

**Output:** None (modifies internal registry)

**Business Logic:**
1. Add norm_code → function mapping to `_REGISTRY` dict
2. No validation of norm_code format or fn signature

**Evidence Type:** Code, test coverage in test_a3627_auto_plan.py  
**Confidence:** High  
**Notes:** Four engines pre-registered: E1, E5, E126, E132, A3627 (all in `_load_defaults()`)

---

## 2. Norm Planning Layer

### `norm_plan_for_license(license_obj, *, balance_cif=None) -> dict`

**File:** `backend/apps/license/services/norm_plan.py:117`

**Type:** Norm-aware per-import-item plan computation  
**Caller:** effective_plan_for_license, plan_reporting.py  
**Called By:** Views, exporters, Item Pivot Report

**Purpose:** Generate per-import-item norm plan: `{item_id: {planned_quantity, unit_price, planned_cif}}`

**Inputs:**
- `license_obj` — License instance
- `balance_cif` (optional) — pre-computed balance; computed from model property if omitted

**Output:** Dict mapping import_item_id → `{planned_quantity, unit_price, planned_cif}`  
(items with no norm allocation are absent from dict)

**Business Logic by Norm:**

**E1/E5:** Category-based waterfall
1. Classify each import item into a category (milk, edible-oil, spirits, etc.)
2. Run shared waterfall engine (plan_e1_items / plan_e5_items)
3. Allocate category's planned CIF to items in that category proportionally
4. Unit price = effective rate (category CIF / category qty)

**E126/E132:** Deterministic per-item classification
1. Classify each import item by HSN code + description
2. Apply fixed unit prices per planning item
3. planned_cif = available_qty × unit_price
4. Unclassified items get no plan line

**A3627:** Waterfall with fixed rate per category
1. Classify into Rutile, Titanium, Soda Ash, PP
2. Apply fixed prices with avg-price thresholds (Rutile)
3. Allocate remaining balance in category order

**Evidence Type:** Code, extensive test coverage  
**Confidence:** High  
**Financial Impact:** Yes — produces CIF allocation values  
**Precision:** Uses 3 decimals for qty, 2 decimals for unit_price and CIF

---

### `effective_plan_for_license(license_obj, *, balance_cif=None) -> (source, dict)`

**File:** `backend/apps/license/services/norm_plan.py:45`

**Type:** Composite planner (manual + norm + allotment-adjusted)  
**Caller:** Frontend views, serializers, exporters  
**Called By:** Extensively used in display/reporting

**Purpose:** Per-import-item effective plan, net of allotments

**Inputs:**
- `license_obj` — License instance
- `balance_cif` (optional) — pre-computed balance

**Output:** `(source, out_dict)` where:
- `source` ∈ `{'manual', 'norm', ''}` (which takes precedence)
- `out_dict` — `{item_id: {planned_quantity, unit_price, planned_cif}}`

**Composition Rules:**
1. **Manual First** — if import item has a manual plan line, use it (fixed, norm never overrides)
2. **Norm Fills Rest** — items without manual line use norm plan
3. **Remaining** — plan qty/CIF reduced by live allotted (floored at 0)

**Remaining Formula:**
- remaining_qty = max(planned_qty - allotted_qty, 0)
- remaining_cif = max(planned_cif - allotted_value, 0)
- unit_price recalculated = remaining_cif / remaining_qty if remaining_qty > 0, else 0

**Evidence Type:** Code, test coverage  
**Confidence:** High  
**Notes:** Reads live allotted_quantity/allotted_value from import items, NOT from db count

---

## 3. Auto-Plan Engines

### `compute_e126_auto_plan(license_obj) -> (lines, remaining_cif)`

**File:** `backend/apps/license/services/e126_auto_plan.py:118`

**Type:** Auto-plan engine  
**Caller:** PlannerFactory.run()  
**Called By:** Views (auto_plan, auto_plan_all), management command (plan_norms)

**Purpose:** Generate E126 (Vegetable Oils) plan from available quantities

**High-Level Flow:**
1. Load import items, group by plan_group_key (HSN + description)
2. Skip groups with summed available_qty < MIN_PLAN_QTY (50)
3. Call plan_e126_per_item_split(records, balance_cif) — runs waterfall
4. For PKO/Olive-Oil split (50/50 target), check for EXISTING split and preserve if found
5. Convert split result to plan line dicts
6. Validate all lines (price ceiling, qty vs available)
7. Return (lines, remaining_cif)

**Key Business Rules:**
- **MIN_PLAN_QTY = 50** — minimum group quantity to plan
- **Split Preservation** — once PKO/Olive-Oil split is generated, it becomes fixed commitment (never recalculated)
- **Group-Anchored Planning** — one plan per physical product group (not per raw import item)
- **Representative Item** — plan stored on lowest-serial group member

**Known Defect (BL-PLAN-01):**
- `planned_cif_fc` computed from UN-FLOORED quantity, never reconciled with FLOORED planned_quantity
- When available_qty has fractional part, inconsistency is baked into persisted row
- Effect: real CIF balance consumed against non-recorded plannable quantity

**Output:** List of plan line dicts with structure:
```python
{
    'import_item': int (representative id),
    'item_name': int (ItemNameModel.id),
    'planned_quantity': float,
    'unit_price': float,
    'planned_cif_fc': float,
    'remaining_quantity': float (preserved or fresh),
    'remaining_cif_fc': float (preserved or fresh),
    'note': str
}
```

**Evidence Type:** Code, test coverage (test_e126_auto_plan.py)  
**Confidence:** High (code-reviewed, but defect found)  
**Financial Impact:** Yes, affects balance CIF allocation  

---

### `compute_e132_auto_plan(license_obj) -> (lines, remaining_cif)`

**File:** `backend/apps/license/services/e132_auto_plan.py:115`

**Type:** Auto-plan engine  
**Caller:** PlannerFactory.run()

**Purpose:** Generate E132 (Nuts & Cheese) plan from available quantities

**Business Logic:** Identical to E126 (module docstring says "Mirrors e126_auto_plan.py exactly")

**Known Defect (BL-PLAN-01):** Same as E126 — `planned_cif_fc` not recomputed from floored quantity

**Evidence Type:** Code (same pattern as E126)  
**Confidence:** High (same defect, same fix pattern)  

---

### `compute_e1_auto_plan(license_obj) -> (lines, remaining_cif)`

**File:** `backend/apps/license/services/e1_auto_plan.py:96`

**Type:** Auto-plan engine  
**Caller:** PlannerFactory.run()

**Purpose:** Generate E1 plan (spirits, alcohol) from available quantities

**Business Logic:**
1. Group import items by category
2. Run shared waterfall (plan_e1_items)
3. Allocate category CIF proportionally to items
4. Convert to plan line dicts

**Distinguishing Features:**
- Uses category waterfall (E5 sibling behavior)
- No split targets (unlike E126/E132)
- Proportional allocation within categories

**Evidence Type:** Code (test_e1_auto_plan.py)  
**Confidence:** High  

---

### `compute_e5_auto_plan(license_obj) -> (lines, remaining_cif)`

**File:** `backend/apps/license/services/e5_auto_plan.py:128`

**Type:** Auto-plan engine  
**Caller:** PlannerFactory.run()

**Purpose:** Generate E5 (Edible Oils) plan from available quantities

**Business Logic:**
1. Group import items by category
2. Detect milk groups (special handling for milk products)
3. Run shared waterfall (plan_e5_items) with milk detection
4. Allocate category CIF proportionally
5. Convert to plan line dicts

**Distinguishing Features:**
- Milk-group detection and consolidated handling
- Category waterfall similar to E1

**Evidence Type:** Code (test_e5_auto_plan.py)  
**Confidence:** High  

---

### `compute_a3627_auto_plan(license_obj) -> (lines, remaining_cif)`

**File:** `backend/apps/license/services/a3627_auto_plan.py:205`

**Type:** Auto-plan engine (in-progress)  
**Caller:** PlannerFactory.run()

**Purpose:** Generate A3627 (Mineral Specialties) plan

**Business Logic:**
1. Classify items by product category (Rutile, Titanium, Soda Ash, PP)
2. Apply fixed prices with Rutile avg-price threshold (3.0)
3. Allocate in order: Rutile → Titanium → Soda Ash → PP
4. Floor to whole units, cascade remainder to next category

**Key Calculations:**
- Rutile avg_price = Σ(available_qty × unit_price) / Σ(available_qty)
- If avg < 3.0: low price; else: high price
- Each category gets min(remaining_balance / fixed_price, available_qty)

**Evidence Type:** Code (test_a3627_auto_plan.py)  
**Confidence:** High (code-reviewed)  
**Financial Impact:** Yes  

---

## 4. Plan Enforcement & Constraint Checking

### `live_allotted_qty(item) -> Decimal`

**File:** `backend/apps/license/services/plan_enforcement.py:48`

**Type:** Live aggregation (bypasses denormalized cache)  
**Caller:** plan_status_for, allocate_items validation  
**Called By:** Allocation validators, cap enforcement

**Purpose:** Get current quantity already allotted for an import item

**Filter:** Non-BOE allotments where type="AT"  
**Output:** Decimal (sum of AllotmentItems.qty)  
**Confidence:** High  

---

### `live_allotted_value(item) -> Decimal`

**File:** `backend/apps/license/services/plan_enforcement.py:59`

**Type:** Live aggregation (bypasses denormalized cache)  
**Caller:** plan_status_for  
**Called By:** Allocation validators

**Purpose:** Get current CIF-FC value already allotted for an import item

**Filter:** Same as live_allotted_qty (non-BOE, type="AT")  
**Output:** Decimal (sum of AllotmentItems.cif_fc)  
**Confidence:** High  

---

### `planned_totals_for(item_ids) -> (Decimal, Decimal)`

**File:** `backend/apps/license/services/plan_enforcement.py:92`

**Type:** Plan aggregate (immutable outside Plan tab)  
**Caller:** plan_status_for, allocate_items validation  
**Called By:** Views, serializers

**Purpose:** Get total planned qty/CIF for a group

**Computation:** Sum of `LicenseItemPlan.planned_quantity` and `planned_cif_fc` where import_item_id in item_ids

**Output:** `(planned_qty: Decimal, planned_cif: Decimal)`

**Business Rule:** This is the "Original Plan" (immutable outside Plan tab), never touched by allotment create/delete/edit

**Confidence:** High  

---

### `plan_status_for_ids(gids) -> dict | None`

**File:** `backend/apps/license/services/plan_enforcement.py:194`

**Type:** Status aggregation  
**Caller:** Views, serializers, item_pivot_report  
**Called By:** Display, reporting

**Purpose:** Complete plan status for a group: Planned / Used / Remaining

**Output:** `{plan: Decimal, used: Decimal, remaining: Decimal}` or None

**Computation:**
- `plan` = `planned_totals_for(gids)` (immutable)
- `used` = `live_allotted_qty_for(gids)` (live)
- `remaining` = max(plan - used, 0)

**Confidence:** High  

---

### `save_plan_lines_for_license(license_obj, lines, *, delete_existing=True) -> list`

**File:** `backend/apps/license/services/plan_enforcement.py:130`

**Type:** Persistence layer  
**Caller:** auto_plan, e1_auto_plan, auto_plan_all, bulk_upsert, plan_norms command  
**Called By:** Views, management command

**Purpose:** Full-replace plan: delete existing, create new from lines

**Input:** List of plan line dicts with keys:
- `import_item` (required, int)
- `item_name` (required, int)
- `planned_quantity` (required, float)
- `unit_price` (required, float)
- `planned_cif_fc` (required, float)
- `note` (optional, str)
- `remaining_quantity` (optional, defaults to planned_quantity)
- `remaining_cif_fc` (optional, defaults to planned_cif_fc)

**Validation:** None here — caller is responsible

**Side Effects:**
1. Delete all existing LicenseItemPlan rows for license
2. For each line, create LicenseItemPlan with:
   - `baseline_used_quantity` = live allotted qty for item's group (snapshot at creation)
   - `baseline_used_cif_fc` = live allotted CIF for item's group (snapshot at creation)
3. Return list of created objects

**Business Rule:** Baseline snapshot timestamps enable "used since this plan" calculation without relying on AllotmentItems.created_on (which breaks on amendments)

**Confidence:** High  

---

### `validate_group_plan_lines(...) -> bool`

**File:** `backend/apps/license/services/plan_grouping.py` (called from e126_auto_plan, e132_auto_plan, etc.)

**Type:** Validation gate  
**Caller:** Every auto-plan engine (before saving lines)  
**Called By:** compute_e126_auto_plan, compute_e132_auto_plan, a3627_auto_plan

**Purpose:** Validate planned quantities against available, prices against ceiling

**Checks:**
1. **Price ceiling** — planned unit_price ≤ UNIT_PRICE[planning_item]
2. **Quantity constraint** — total planned_qty ≤ available_qty (UNLESS preserved split, then skipped)
3. **CIF totals** — sum of planned_cif_fc ≤ balance_cif (implicit via waterfall)

**Output:** True (valid) / False (invalid, logs warning)

**Confidence:** High  

---

## Summary Table

| Function | File | Type | Caller | Inputs | Output | Financial? |
|----------|------|------|--------|--------|--------|-----------|
| detect_norm | norm_plan.py | Utility | PlannerFactory, norm_plan_for_license | license_obj | str ('E1'\|'E5'\|...) | No |
| norm_plan_for_license | norm_plan.py | Aggregator | Views, exporters | license_obj, balance_cif? | {item_id: plan_values} | Yes |
| effective_plan_for_license | norm_plan.py | Aggregator | Views, serializers | license_obj, balance_cif? | (source, {item_id: plan_values}) | Yes |
| compute_e126_auto_plan | e126_auto_plan.py | Engine | PlannerFactory | license_obj | (lines, remaining_cif) | Yes |
| compute_e132_auto_plan | e132_auto_plan.py | Engine | PlannerFactory | license_obj | (lines, remaining_cif) | Yes |
| compute_e1_auto_plan | e1_auto_plan.py | Engine | PlannerFactory | license_obj | (lines, remaining_cif) | Yes |
| compute_e5_auto_plan | e5_auto_plan.py | Engine | PlannerFactory | license_obj | (lines, remaining_cif) | Yes |
| compute_a3627_auto_plan | a3627_auto_plan.py | Engine | PlannerFactory | license_obj | (lines, remaining_cif) | Yes |
| live_allotted_qty | plan_enforcement.py | Aggregator | Validators | item | Decimal | Yes |
| live_allotted_value | plan_enforcement.py | Aggregator | Validators | item | Decimal | Yes |
| planned_totals_for | plan_enforcement.py | Aggregator | Validators | item_ids | (Decimal, Decimal) | Yes |
| plan_status_for_ids | plan_enforcement.py | Status | Views | gids | dict\|None | Yes |
| save_plan_lines_for_license | plan_enforcement.py | Persistence | Views, command | license_obj, lines | [LicenseItemPlan] | Yes |

---

## Known Gaps (See MODULE_2_PLANNING_UNKNOWNS.md)

1. **PP Norm** — 73 real licenses (32% of book) have no auto-plan engine (BL-PLAN-02)
2. **Calculation Defect (BL-PLAN-01)** — E126/E132 don't recompute planned_cif_fc from floored quantity
3. **Milk Product Handling** — E5 milk detection logic is under-documented
4. **Wastage Rebalance** — E126/E132 move unused CIF from Nuts to split target; algorithm not fully documented

