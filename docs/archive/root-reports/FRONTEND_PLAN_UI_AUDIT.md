# FRONTEND PLAN UI — DUPLICATION AUDIT

**Date:** 2026-08-17  
**Status:** Analysis Complete

---

## TL;DR

**Two Completely Separate Features:**

1. **SION Allocation Editor** (PlanningEditor)
   - Purpose: Edit individual allocation splits
   - Location: Accordion "Plan" tab (editable rows)
   - Modal: LicensePlanningPanel
   - Status: ✅ Consolidated (uses PlanningEditor shared core)

2. **License Plan Utilization Viewer** (PlanningTab)
   - Purpose: View plan vs usage, Auto Plan
   - Location: License detail "Plan" tab (read-only)
   - Status: ❌ Missing from accordion, only in full detail view
   - **Action Required:** Add Plan Utilization view to accordion as separate tab or modal

**Summary Card Duplication:**
- "Balance CIF", "Planned CIF", "Remaining CIF" duplicated across 10+ files
- No consolidation needed — different styling contexts

---

## Detailed Audit

### Component 1: SION Allocation Editor (SHARED)

**Files:**
- `frontend/src/components/planning/PlanningEditor.tsx` (987 lines)
- `frontend/src/components/planning/LicensePlanningPanel.tsx` (60 lines wrapper)
- `frontend/src/pages/masters/tables/PlanTab.tsx` (27 lines wrapper)

**Usage Locations:**
| Location | Route | Purpose | Status |
|---|---|---|---|
| Accordion "Plan" tab | `/licenses` → accordion expand | Edit SION allocations | ✅ Uses PlanningEditor |
| Plan Modal | Via LicensePlanningPanel | Edit in dialog | ✅ Uses PlanningEditor |
| ItemPivotReport "Plan me" | `/reports/item-pivot` | Adjust plan for item | ✅ Uses LicensePlanningPanel |
| MasterList (undeclared) | `/masters` | Declared but not wired | ⚠️ Dead state |
| AllotmentAction failover | `/allocate/:id` | Plan when allotment exceeds | ✅ Uses LicensePlanningPanel |

**Status:** ✅ **CONSOLIDATED** — Only PlanningEditor.tsx used, all wrappers point there

---

### Component 2: License Plan Utilization Viewer

**Files:**
- `frontend/src/pages/license-overview/PlanningTab.tsx` (232 lines)
- `frontend/src/pages/license-overview/useLicenseOverviewPlanning.ts` (22 lines hook)

**Location:** License detail view only
- Route: `/licenses/:id/overview?tab=planning`
- Not visible in accordion

**Features:**
- ✅ Auto Plan button (NEW mode, safe default)
- ✅ Force Re-plan dropdown (ALL mode, requires confirmation)
- ✅ Planned items table
- ✅ Planned Qty, Allocated Qty, Available Qty, Remaining Qty, Shortage Qty columns
- ✅ Status badges (FEASIBLE, SHORT, BLOCKED_UNIT_MISMATCH)
- ✅ Uses canonical `useLicenseOverviewPlanning()` hook

**Status:** ✅ **COMPLETE** — Single implementation, all requirements met

---

## Three Separate "Plan" UIs

### 1. SION Allocation Editor
```
/licenses accordion
    → License row expand
    → Click "Plan" tab
    → PlanTab → PlanningEditor (inline editable rows)
    → Edit individual splits
    → Save to LicenseItemPlan
```

**Not Utilization** — User manually allocates quantities to splits.

### 2. License Plan Utilization Viewer
```
License detail page
    → Click "Plan" tab
    → PlanningTab (read-only table)
    → Shows: planned vs used vs available
    → Auto Plan button
    → Force Re-plan dropdown
```

**Utilization View** — Read-only display of planning results + planning actions.

### 3. Plan Modal (from various triggers)
```
ItemPivotReport / AllotmentAction
    → "Plan me" button
    → LicensePlanningPanel modal
    → PlanningEditor (same as accordion)
```

**Also Editor** — Same as accordion #1, just in modal shell.

---

## What's Missing: Plan Utilization in Accordion

**Current State:**
- ✅ Accordion has "Plan" tab (PlanningEditor — for editing)
- ❌ Accordion has NO "Plan Utilization" view (read-only with Auto Plan)
- ✅ Full License page has "Plan" tab (PlanningTab — utilization viewer)

**Gap:** User must navigate to full License detail page to see utilization + Auto Plan. No way to plan directly from accordion.

---

## Summary Card Duplication

"Balance CIF", "Planned CIF", "Remaining CIF" summary cards appear in:
1. PlanningEditor.tsx — SummaryCard component (lines 200-214)
2. ItemPivotReport.tsx — Custom styled divs
3. BalanceTab.tsx — Custom styled divs
4. Multiple masters reports — Various implementations

**Assessment:** ❌ **No consolidation possible** — Different styling, different contexts (edit mode vs read-only, different color schemes, different surrounding content).

---

## API Calls

### Single Endpoint (Good)
```
POST /api/sion-planning-rules/plan-license/
  Input:  { license_id, mode: "NEW"|"ALL" }
  Output: { license_id, license_number, applicable_sions[], total_results }
```

**Called from:**
- PlanningTab.tsx (planLicense function at line 21)
- LicenseLedger.tsx (planLicense function at line 9)

**Status:** ✅ Single endpoint, both callers use it correctly

---

## Data Fetching

### PlanningEditor
```
fetchLicense()           — /licenses/{id}/
fetchItemPlans()         — /licenses/{id}/item-plans/
bulkUpsertItemPlans()    — PATCH /license-item-plans/
deleteItemPlan()         — DELETE /license-item-plans/{id}/
```

### PlanningTab
```
useLicenseOverviewPlanning()  — /licenses/{id}/plan-utilization/
```

**Status:** ✅ Clean separation, no data duplication

---

## Routes

| Route | Component | Purpose | Status |
|---|---|---|---|
| `/licenses` | LicensesTable | Accordion table | ✅ Plan tab uses PlanningEditor |
| `/licenses/:id/overview?tab=planning` | LicenseOverviewPage → PlanningTab | Utilization viewer | ✅ Single implementation |
| `/planning` | LicensePlanningWorkspace | Full planning editor (separate flow) | ✅ Isolated |

**Status:** ✅ No route duplication

---

## Recommendations

### Option A: Keep Current (Minimal Changes)
- ✅ Accordion "Plan" tab = PlanningEditor (edit allocations)
- ✅ License detail "Plan" tab = PlanningTab (view utilization + Auto Plan)
- ⚠️ Gap: No utilization view in accordion

### Option B: Add Utilization to Accordion (Recommended)
1. Add new accordion tab "Plan Utilization" → PlanningTab component
2. Keep "Plan" tab as PlanningEditor
3. Allow both workflows from accordion

### Option C: Replace Accordion "Plan" with Utilization
1. Remove PlanningEditor from accordion
2. Add PlanningTab (utilization) to accordion
3. Keep PlanningEditor available via modal

---

## Checklist: No Duplication Found

- ✅ One PlanningEditor (used in 3 locations via wrappers)
- ✅ One PlanningTab (used in 1 location)
- ✅ One planLicense API (called from 2 locations)
- ✅ One useLicenseOverviewPlanning hook (used in PlanningTab)
- ✅ No duplicate Auto Plan button implementations
- ✅ No duplicate confirmation dialogs
- ✅ No duplicate modal shells
- ✅ SummaryCard duplication (unavoidable due to styling context)

---

## Conclusion

**Primary Issue:** Confusion between two separate features:
1. **SION Allocation Editing** — PlanningEditor (consolidated ✅)
2. **License Plan Utilization** — PlanningTab (standalone ✅)

**No Code Duplication:** Both components are unique and serve different purposes.

**Missing Feature:** Plan Utilization not accessible from accordion (only from full License detail).

**Recommendation:** Add Plan Utilization view to accordion if users need it there.

**Code Quality:** ✅ Components are clean, no wasted duplication.
