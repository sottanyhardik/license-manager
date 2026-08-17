# Phase 1: Separate Read & Write Paths — Implementation Roadmap

**Date:** 2026-08-17  
**Status:** Planning Complete, Ready for Implementation  
**Scope:** Remove ALL planner calls from read paths, migrate to persisted LicenseItemPlan only

---

## Critical Findings

### VIOLATION 1: item_pivot_report.py — Direct Planner Calls in GET Endpoint

**Location:** `/backend/apps/license/views/item_pivot_report.py` lines 1277-1487

**Current Behavior:**
```
GET /api/reports/item-pivot/
    → fetch licenses
    → FOR EACH LICENSE:
        IF E1:
            import plan_e1_items()
            → classify import items
            → run E1 planning waterfall
            → return calculated planned CIF
        IF E5:
            import plan_e5_items()
            → classify import items
            → run E5 planning waterfall
            → return calculated planned CIF
        IF E126/E132:
            import plan_e126_per_item() / plan_e132_per_item()
            → run planning logic
            → return calculated planned CIF
    → return report with ON-THE-FLY planned values
```

**Problem:**
- GET endpoint executes planning logic
- No plan = silently runs planner (fallback pattern)
- ~210 lines of planning code (E1 section alone: lines 1277-1388)
- Repeated for E5 (lines 1389-1488), E126/E132 sections follow

**Required Fix:**
- Remove all planner imports and calls
- Read ONLY from persisted LicenseItemPlan
- If no plan persisted: show "Not Planned" / 0 quantities
- No fallback, no inference

---

### VIOLATION 2: item_report.py — Uses effective_plan_for_license() in GET

**Location:** `/backend/apps/license/views/item_report.py` lines 300+

**Current Behavior:**
```
GET /api/reports/item-report/
    → for each import item:
        call effective_plan_for_license(license)
        → merges manual plan + norm plan
        → returns combined result
```

**Problem:**
- Calls `effective_plan_for_license()` which calls `norm_plan_for_license()`
- `norm_plan_for_license()` calls legacy planners (plan_e1_items, plan_e5_items, etc.)
- Hidden in GET request processing

**Required Fix:**
- Remove `effective_plan_for_license()` call
- Read LicenseItemPlan directly
- No fallback to norm planning

---

### VIOLATION 3: norm_plan.py — Fallback Logic

**Location:** `/backend/apps/license/services/norm_plan.py` lines 45-114

**Current Behavior:**
```python
def effective_plan_for_license(license_obj):
    manual = plan_map_for_license(license_obj.id)
    norm = norm_plan_for_license(license_obj)  # ← calls planners
    
    # FALLBACK: if manual missing, use norm
    out = {}
    for iid in set(norm) | set(manual):
        if iid in manual:
            use_manual[iid]
        else:
            use_norm[iid]  # ← fallback to calculated plan
```

**Problem:**
- `norm_plan_for_license()` calls all legacy planners
- Used as fallback when no manual plan exists
- Means "no plan" can trigger planning

**Required Fix:**
- Remove `norm_plan_for_license()` call from read paths
- Keep it ONLY in write paths (sion_planning_execution)
- `effective_plan_for_license()` becomes "read manual plan, period"

---

## Current Data Flow (WRONG)

```
GET /api/reports/item-pivot/
    ├─ Read license
    ├─ Read import items
    ├─ Read LicenseItemPlan (manual plans)
    ├─ Classify items
    ├─ Run planners (E1/E5/E126/E132)  ← WRONG: in read path
    ├─ Merge manual + calculated
    └─ Return pivot grid

GET /api/reports/item-report/
    ├─ Read licenses
    ├─ Read import items
    ├─ Call effective_plan_for_license()
    │  ├─ Read manual plan
    │  ├─ Call norm_plan_for_license()
    │  │  └─ Run planners (E1/E5/E132/E126)  ← WRONG: in read path
    │  └─ Merge
    └─ Return report
```

---

## Target Data Flow (CORRECT)

```
WRITE PATHS (Planning):
    /planning UI
    /licenses Auto Plan
    /licenses Force Re-plan
    python manage.py plan_norms
        → Canonical planning engine
        → LicenseItemPlan persistence

READ PATHS (Reporting):
    GET /api/reports/item-pivot/
        ├─ Read license
        ├─ Read import items
        ├─ Read LicenseItemPlan
        └─ Return only what's saved

    GET /api/reports/item-report/
        ├─ Read licenses
        ├─ Read import items
        ├─ Read LicenseItemPlan
        └─ Return only what's saved
```

---

## Implementation Phases

### Phase 1A: Create Read-Only Aggregation Services (DONE ✅)
- ✅ ItemPivotAggregationService — created
- ✅ LicensePlanPresentationService — already exists
- ✅ Both read ONLY from LicenseItemPlan

### Phase 1B: Migrate item_pivot_report.py

**Approach:**
1. Remove all E1/E5/E126/E132 planner imports
2. Remove lines 1277-1487 (planning calculation code)
3. Replace with: `ItemPivotAggregationService.build_pivot_item_data(license)`
4. Adjust response structure to match expected format
5. Update Excel export path (use same aggregated data)

**Risk:** Report will show "Not Planned" for licenses without persisted plans
**Mitigation:** This is CORRECT behavior per architecture requirement

**Effort:** ~200 lines changed, ~400 lines deleted

### Phase 1C: Migrate item_report.py

**Approach:**
1. Remove `effective_plan_for_license()` calls
2. Replace with direct `LicenseItemPlan` reads
3. Use `LicensePlanPresentationService.get_plan_rows_for_license()`
4. Adjust row structure

**Risk:** Same as 1B
**Effort:** ~50 lines changed

### Phase 1D: Refactor norm_plan.py

**Approach:**
1. Mark `norm_plan_for_license()` as WRITE-ONLY
2. Move to sion_planning_execution or mark as deprecated
3. Remove from read-path callers
4. Keep in sion_planning_execution adapters (write paths only)

**Risk:** None if read paths don't call it
**Effort:** ~30 lines changed, restructuring imports

### Phase 1E: Add Regression Tests

**Tests to add:**
```python
def test_item_pivot_no_planner_calls():
    # Mock all planner functions to raise AssertionError
    patch_planners_to_fail()
    
    # Call GET /api/reports/item-pivot/
    response = client.get('/api/reports/item-pivot/?format=json')
    
    # Must succeed with no planner calls
    assert response.status_code == 200
    assert no_planners_were_called()

def test_item_report_no_planner_calls():
    patch_planners_to_fail()
    response = client.get('/api/reports/item-report/')
    assert response.status_code == 200
    assert no_planners_were_called()

def test_get_license_item_plans_no_side_effects():
    # Fetch initial count
    initial_plans = LicenseItemPlan.objects.count()
    
    # Call GET
    response = client.get('/api/license-item-plans/?license=2086')
    
    # Must not create/modify plans
    assert LicenseItemPlan.objects.count() == initial_plans
    assert response.status_code == 200
```

---

## Semantic Change: What Changes After Phase 1

### Before (Current — WRONG)
```
License 0311021261 (E1):
  - No LicenseItemPlan persisted yet
  - Report shows: E1 norm plan (calculated on-the-fly)
  
License 0311032964 (E5):
  - No LicenseItemPlan persisted yet
  - Report shows: E5 norm plan (calculated on-the-fly)
```

### After (After Phase 1 — CORRECT)
```
License 0311021261 (E1):
  - No LicenseItemPlan persisted yet
  - Report shows: Not Planned / 0 planned / 0 planned CIF
  
License 0311032964 (E5):
  - No LicenseItemPlan persisted yet
  - Report shows: Not Planned / 0 planned / 0 planned CIF

License 0311021261 (E1) — AFTER Auto Plan:
  - LicenseItemPlan now persisted (via Auto Plan button)
  - Report shows: actual planned quantities/CIF from LicenseItemPlan
```

**Impact:** Users must explicitly plan licenses via Auto Plan / Force Re-plan to see planned values in reports.

---

## Migration Strategy for Existing Licenses

**Option A: One-Time Backfill (Recommended)**
- Run a management command: `python manage.py backfill_plans`
- For every license without LicenseItemPlan:
  - Run the canonical planning engine
  - Persist to LicenseItemPlan
- After: all licenses have explicit plans in the database

**Option B: Just Clean Up (Current Approach)**
- Remove fallback logic immediately
- Licenses without plans show as "Not Planned"
- Users manually plan licenses as needed via Auto Plan
- Eventual consistency over time

---

## Dependencies & Order

```
Phase 1B (item_pivot_report.py)
    ↓ depends on
ItemPivotAggregationService ✅ (done)

Phase 1C (item_report.py)
    ↓ depends on
LicensePlanPresentationService ✅ (done)

Phase 1D (norm_plan.py refactoring)
    ↓ depends on
1B, 1C complete (to verify read paths don't call it)

Phase 1E (tests)
    ↓ depends on
1B, 1C, 1D complete
```

**Safe to parallelize:** 1B and 1C (independent files)

---

## Blockers / Questions

1. **Backfill Strategy:** Should we backfill LicenseItemPlan for existing licenses, or let them appear as "Not Planned" until manually planned?

2. **Reporting Semantics:** Is showing "Not Planned" for unplanned licenses acceptable, or should we first backfill?

3. **Exports:** Should PDF/Excel exports also stop computing plans and only show persisted data?

---

## Sign-Off Ready

- ✅ ItemPivotAggregationService created and ready
- ✅ LicensePlanPresentationService exists and is clean
- ✅ Critical violations identified
- ✅ Refactoring roadmap complete
- ⏳ **Awaiting user approval to proceed with 1B-1E**
