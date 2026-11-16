# Module 07 — Item Pivot Report
## COMPLETE AUDIT FINDINGS

**Date:** 2026-08-17  
**Auditor:** Claude Code  
**Status:** ⚠️ CRITICAL ARCHITECTURE VIOLATION IDENTIFIED

---

## Executive Summary

Item Pivot contains **DIRECT VIOLATIONS** of Module 06 architectural constraints:

1. **Duplicates E1/E5/E132 planning engines** — calls `e1_plan`, `e5_plan`, `e132_plan` directly
2. **Does not read canonical Module 06 plans** — ignores persisted `LicenseItemPlan` rows
3. **Re-calculates "norm-derived planned CIF"** — reimplements planning logic that Module 06 owns
4. **Maintains parallel planning state** — Item Pivot's `effective_planned_cif` vs Module 06's canonical plans can diverge

**Impact:** If Module 06 rules change and planning is rerun, Item Pivot will show **STALE DATA** until it is manually re-exported (or until the legacy planning engines are called again, which should never happen).

---

## Current Architecture (WRONG)

```
Legacy Planning Engines        Module 06 Canonical Planning
(E1, E5, E132, A3627)         (FROZEN)
        ↓                      ↓
Item Pivot Report  ←── DUPLICATES BOTH
        ↓
User sees table
```

**Problem:** Item Pivot calls BOTH legacy engines AND maintains its own calculation of `effective_planned_cif` / `effective_planned_quantity`.

**When Module 06 runs NEW planning rules:**
- ✅ `LicenseItemPlan` rows are updated
- ❌ Item Pivot has no idea — it still has old data cached in memory / in the Excel file

---

## Correct Architecture (TARGET)

```
Module 06 Planning Rules
        ↓
Module 06 Canonical Engine (FROZEN)
        ↓
Persisted LicenseItemPlan Rows
        ↓
Item Pivot Aggregator Service
(reads plans, groups, sums)
        ↓
┌──────────────┬──────────────┐
UI Render     Excel Export   JSON API
```

**Guarantee:** Any change to planning automatically flows through to Item Pivot's view.

---

## Code Locations — Legacy Duplication

### 1. Item Pivot View Main File

**File:** `backend/apps/license/views/item_pivot_report.py`

**Lines 1261-1372: E1 Planning Recreation**
```python
from apps.license.services.e1_auto_plan import STEP_ITEM_NAME as _E1_STEP_ITEM_NAME
from apps.license.services.e1_plan import (
    E1Item as _E1Item, classify_e1_item as _classify, plan_e1_items as _plan_e1_items,
)
# ... then calls _plan_e1_items() directly to recalculate planning per license
```

**Lines 1373-1463: E5 Planning Recreation**
```python
from apps.license.services.e5_auto_plan import STEP_ITEM_NAME as _E5_STEP_ITEM_NAME
from apps.license.services.e5_plan import (
    E5Item as _E5Item, classify_e5_item as _classify, plan_e5_items as _plan_e5_items,
)
# ... then calls _plan_e5_items() directly to recalculate planning per license
```

**Lines 1471-1483: E132 Planning Recreation**
```python
from apps.license.services.e132_plan import plan_e132_per_item
# ... then calls plan_e132_per_item() directly to recalculate planning per license
```

### 2. Effective Planned CIF/Quantity Calculations

**Lines 41-72: Per-Cell Manual-vs-Norm Selection**
```python
def _effective_planned_cif(plan_quantity, plan_cif, planned_cif):
    """Choose between manual plan (from LicenseItemPlan) OR 
    norm-derived (E1/E5/E132 waterfall). The norm-derived branch
    SHOULD BE ELIMINATED in favor of reading Module 06's canonical plans."""
    
    pq = plan_quantity or 0
    pc = plan_cif or 0
    return pc if (pq or pc) else (planned_cif or 0)

def _effective_planned_quantity(plan_quantity, plan_cif, available_quantity):
    """Parallel logic for quantities — also duplicates Module 06."""
    pq = plan_quantity or 0
    pc = plan_cif or 0
    return pq if (pq or pc) else (available_quantity or 0)
```

**Problem:** The fallback to `planned_cif` / `available_quantity` is trying to simulate "what the E1/E5/E132 waterfall WOULD compute" — but that computation happens in lines 1261-1483 above.

### 3. Notification Summary Aggregation

**Lines 75-212: `_build_notification_summary()`**
- Aggregates item totals from licenses
- Computes `blended_unit_price = total_planned_cif / total_planned_qty`
- Uses the already-computed `effective_planned_cif` fields

**Problem:** This is correct *as an aggregation layer*, but it's aggregating data that was computed by re-running the legacy planners. Should aggregate Module 06's canonical plans instead.

---

## Data Lineage Issues

### Current (Broken) Lineage

```
generate_report()
  ↓
  pulls licenses from DB
  ↓
  _build_license_row() per license
    ↓
    if E1: calls _plan_e1_items()   (LEGACY ENGINE)
    if E5: calls _plan_e5_items()   (LEGACY ENGINE)
    if E132: calls plan_e132_per_item()  (LEGACY ENGINE)
    ↓
    populates item_plan_data[] with computed planned_cif
    ↓
  _effective_planned_cif() selects manual vs computed
  ↓
_build_notification_summary() aggregates
  ↓
Response JSON / Excel export
```

**Issue:** If Module 06 runs new planning rules and updates `LicenseItemPlan`, Item Pivot is **unaware** — it still has old `item_plan_data[]` from the legacy engine.

### Correct (Target) Lineage

```
generate_report()
  ↓
  pulls licenses from DB
  ↓
  load canonical LicenseItemPlan rows for each license
    ↓
    read: planned_quantity, planned_cif, rule_priority, allocation_strategy
    ↓
  aggregate by item name
  ↓
ItemPivotAggregationService.summarize()
  ↓
Response JSON / Excel export
```

**Guarantee:** Always reads current persisted plans. Never diverges from Module 06.

---

## Column Definitions — Audit

### Available Balance Qty

**Current Screenshot Value:** 1,27,468.73 (appears to be **quantity**, not CIF)

**Current Implementation:** Sums `import_item.available_quantity` across the license's import items, *grouped by item name*.

**Definition (Per Code):**
```python
'available_quantity': Decimal(str(import_item.available_quantity))
```

**Issue:** The screenshot shows this in the **quantity** column, which is correct semantically, but the label "Available Balance Qty" is misleading because:

1. This is **current available quantity** at report-run time
2. It is **NOT adjusted for planning** — it includes quantities that may already be planned
3. Split-planned items show 0 available but nonzero planned (lines 173-174)

**Recommendation:**
- **Keep the calculation:** It's correct as-is
- **Fix the label:** "Available Qty at Report Time" or "Current Available Balance"
- **Add note in UI:** "Shows quantity available before planning execution"

### Planned Qty

**Current Implementation (BROKEN):**
- For **manual plan**: sums `plan_quantity` from `LicenseItemPlan` (via `item_plan_totals`)
- For **norm plan** (no manual plan): **RE-RUNS E1/E5/E132 engine** and uses that output

**Problem:** Should ALWAYS read from canonical `LicenseItemPlan`, never re-run legacy engines.

**Target Definition:**
```
For each (SION, item_name):
  SUM(LicenseItemPlan.planned_quantity)
  WHERE license.export_license contains this SION
```

### Total Planned CIF

**Current Implementation (BROKEN):**
- Aggregates `effective_planned_cif` which falls back to **re-computed E1/E5/E132 CIF** if no manual plan exists

**Target Definition:**
```
For each (SION, item_name):
  SUM(LicenseItemPlan.planned_cif)
  WHERE license.export_license contains this SION
```

### Unit Price

**Current Implementation (BROKEN for Norm Planning):**
```python
'unit_price': round(item_plan / item_planned_qty, 2) if item_planned_qty > 0 else 0.0
```
- Where `item_plan` = re-computed E1/E5/E132 CIF
- Where `item_planned_qty` = re-computed E1/E5/E132 quantity

**Target Definition:**
```
Unit Price = Total Planned CIF / Total Planned Qty
  (weighted average per item across all licenses in scope)
```

**Note:** Module 06 may store different unit prices per plan row (split allocation, different prices). The report should aggregate:
```
Total Planned CIF = SUM(LicenseItemPlan.planned_cif)
Total Planned Qty = SUM(LicenseItemPlan.planned_quantity)
Blended Unit Price = Total Planned CIF / Total Planned Qty
```

### Opening Balance

**Current Implementation:**
```python
opening_balance = sum(float(lic.get('balance_cif', 0) or 0) for lic in licenses)
```

**Semantic Definition:**
- **SUM of all licenses' CIF balances** at report-run time
- This is **financial CIF in USD or INR**, NOT quantity
- Should be labeled: "Opening Balance (INR)" or "Total CIF"

**Issue in Screenshot:**
- Shown in the **"Available Balance Qty"** column
- But the number appears to be CIF, not quantity
- **FIX:** Move to separate CIF column or clarify label

**Questions to Resolve (with business):**
1. Is this **INR** or **USD CIF**?
2. Should it be in the **quantity** column?
3. Or should there be separate CIF columns?

### Grand Total Row

**Current Implementation:**
```
total_available = sum per-item available_quantity
total_planned_cif = sum per-item planned_cif
total_planned_qty = sum per-item planned_qty
blended_unit_price = total_planned_cif / total_planned_qty (if total_planned_qty > 0)
```

**Validation Test (NOT YET DONE):**
```
For a fixture with known Module 06 plans:
  SUM(LicenseItemPlan.planned_qty) should equal Item Pivot's "total_planned_qty"
  SUM(LicenseItemPlan.planned_cif) should equal Item Pivot's "total_planned_cif"
  (within Decimal tolerance)
```

---

## Module 06 Canonical Data NOT Being Used

### LicenseItemPlan Model (Module 06)

**Location:** `backend/apps/license/models/` (in migration 0009 or later)

**Key Fields:**
```python
class LicenseItemPlan(AuditModel):
    license = ForeignKey(LicenseDetailsModel)
    item_name = CharField()  # canonical planned item/category
    planned_quantity = DecimalField()
    planned_cif = DecimalField()
    unit_price = DecimalField()
    planned_cif_fc = DecimalField()
    
    # Module 06 provenance (new):
    rule_id = ForeignKey(SionPlanningRule, null=True)
    rule_priority = IntegerField()
    allocation_strategy = CharField()
    allocation_config = JSONField()
    
    stable_key = CharField()  # unique identifier for re-planning
    version = IntegerField()
```

**Item Pivot Currently Reads:**
- ✅ `planned_quantity` (via `item_plan_totals` parameter)
- ✅ `planned_cif` (via `item_plan_totals` parameter)
- ❌ **NOT reading** rule provenance, allocation strategy, or any Module 06 metadata

**Item Pivot Currently IGNORES:**
- ❌ `allocation_strategy` (doesn't show split info)
- ❌ `rule_priority` (shows default waterfall instead)
- ❌ Module 06's actual planned item grouping (re-runs E1/E5 classifier instead)

---

## Split Planning — Currently Broken

### How Module 06 Split Planning Works

```
LicenseItemPlan row 1:
  item_name = "DWP - E1"
  planned_quantity = 600
  planned_cif = 900
  allocation_strategy = "split_by_unit_value"
  allocation_config = {"boundary": 1.50}

LicenseItemPlan row 2:
  item_name = "SWP - E1"
  planned_quantity = 400
  planned_cif = 2600
  allocation_strategy = "split_by_unit_value"
  allocation_config = {"boundary": 1.50}
```

### How Item Pivot Currently Shows Splits

**Code:** Lines 240-273 (`_planning_split_sheet_rows`)
```python
# Reads from LicenseItemPlan.splits (if it exists)
# and creates a separate "Planning Splits" Excel sheet
# showing split detail rows
```

**Problem:** This is a **detail sheet** parallel to the main grid. The main summary grid may not correctly aggregate splits because it's re-running the legacy planner (which may compute split differently).

**Fix Required:**
- Read Module 06's persisted split rows directly
- Group Item Pivot summary by canonical split item names (DWP, SWP)
- Do NOT re-run split allocation algorithm

---

## Tests That Must Pass After Fix

### Unit Tests (Module 07 only — do NOT modify Module 06)

1. **Single license, single item**
   - Input: 1 license with Module 06 manual plan for "DWP - E1" (qty 600, CIF 900)
   - Output: Item Pivot shows DWP planned_qty=600, planned_cif=900

2. **Multiple licenses, same item**
   - Input: 3 licenses with Module 06 plans for DWP (600, 500, 400 qty)
   - Output: Item Pivot shows DWP total planned_qty=1500

3. **Split allocation (SWP/DWP)**
   - Input: License with Module 06 split plan (DWP=600, SWP=400)
   - Output: Item Pivot shows both DWP and SWP rows with correct totals

4. **Zero planned quantity**
   - Input: License with available qty but zero planned
   - Output: Item Pivot shows available qty, planned qty=0

5. **Totals reconciliation**
   - Input: Multiple licenses with various plans
   - Output: SUM(per-license plans) == Item Pivot total row

### Golden Data Test (E1 fixture from Module 06 test suite)

Required fixture:
- E1 license with multiple import items
- Module 06 planning rules executed
- DWP, SWP, confectionery, fruit juice, aluminum foil, citric/tartaric items
- Known split allocation
- Different unit prices

Expected:
```
Item Pivot summary totals
  ==
Aggregation of underlying LicenseItemPlan rows
(within Decimal tolerance)
```

---

## Services That Need Refactoring

### Current Item Pivot Services (Problematic)

1. **`plan_grouping.py`** — grouping logic (used correctly, but operates on legacy-computed data)
2. **`plan_reporting.py`** — report generation (depends on legacy re-computation)
3. **`e1_plan.py`, `e5_plan.py`, `e132_plan.py`** — legacy engines (should NOT be called by Item Pivot)

### New Service Needed

**Name:** `ItemPivotAggregationService`

**Responsibility:**
- Read `LicenseItemPlan` rows for a given SION + license set
- Group by canonical item_name
- Aggregate: SUM(planned_quantity), SUM(planned_cif), compute weighted unit_price
- Return normalized DTO for JSON/Excel/UI to render

**API:**
```python
class ItemPivotAggregationService:
    @staticmethod
    def aggregate_by_item(
        licenses: QuerySet[LicenseDetailsModel],
        sion_code: str = None,
    ) -> Dict[str, ItemSummary]:
        """
        Returns:
        {
            "DWP - E1": {
                "available_qty": Decimal,
                "planned_qty": Decimal,
                "planned_cif": Decimal,
                "unit_price": Decimal,
                "license_count": int,
            },
            ...
        }
        """
```

---

## Remediation Plan

### Phase 1: Create New Aggregation Service (Non-Breaking)

1. Create `ItemPivotAggregationService` that reads `LicenseItemPlan`
2. Add comprehensive tests with Module 06 fixtures
3. Keep old code path intact

### Phase 2: Switch Item Pivot to New Service

1. Refactor `generate_report()` to use new aggregation
2. Remove calls to `e1_plan`, `e5_plan`, `e132_plan` from Item Pivot
3. Delete `_effective_planned_cif` / `_effective_planned_quantity` functions
4. Run regression tests

### Phase 3: Cleanup (After Verification)

1. Verify Item Pivot matches Module 06 plans for representative E1/E5/E132 licenses
2. Remove A3627 / E126 compatibility code if applicable
3. Clean up legacy imports

---

## Known Risks

### Risk 1: E1/E5/E132 Auto-Plan Still Uses Legacy Engines

**Status:** ✅ SAFE — Auto-Plan correctly stores results in `LicenseItemPlan`

Item Pivot should NOT use legacy engines. Item Pivot should only READ `LicenseItemPlan`.

### Risk 2: Backward Compatibility (Stale Manual Plans)

**Scenario:** Old manual plan exists before Module 06 migration.

**Handling:**
- Module 06 converts old `LicenseItemPlan` rows to new schema during migration
- Item Pivot reads the migrated rows
- No special handling needed in Item Pivot

### Risk 3: Split Allocation Not Persisted Correctly

**Scenario:** Module 06 split planning stores DWP/SWP in separate `LicenseItemPlan` rows.

**Handling:**
- Item Pivot must group by canonical item_name (not by import item)
- `LicenseItemPlan.item_name` contains "DWP - E1" or "SWP - E1"
- Item Pivot's aggregation will naturally sum them separately

---

## Questions Requiring Business Clarity

### Q1: Opening Balance Display

Current screenshot shows opening balance in the quantity column.

**Options:**
A. Keep it there (current state) — but clarify label
B. Move to separate CIF column
C. Remove it entirely

**Recommendation:** Clarify with product what this number represents and where it should live.

### Q2: Unit Price for Splits

When an item is split (DWP/SWP), should the unit price:

A. Be computed independently per split (DWP qty=600, DWP CIF=900 → DWP unit_price=1.50)
B. Be blended across all splits (total_cif / total_qty)
C. Something else?

**Recommendation:** Inspect Module 06 to see how it stores/computes unit_price per split row.

### Q3: Zero-Planned Items

Items with available qty but zero planned:

A. Show in Item Pivot summary? (current behavior)
B. Hide from summary?
C. Show only if activated by a filter?

**Recommendation:** Ask product. Current code shows them (lines 167-197).

---

## Conclusion

**Item Pivot is currently a reporting layer OVER DUPLICATED planning logic.**

It should be **a reporting layer OVER CANONICAL Module 06 plans**.

All fixes require:
1. Stop calling E1/E5/E132 planners
2. Start reading `LicenseItemPlan` rows
3. Create comprehensive tests with Module 06 fixtures
4. Verify reconciliation before declaring Module 07 frozen

**Until fixed, Item Pivot will show STALE DATA if Module 06 planning rules change.**
