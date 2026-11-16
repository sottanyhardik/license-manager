# Browser Acceptance Test Checklist - Phase 2D.5

**Date:** 2026-08-17  
**Module:** UI/DB-Driven SION Planning  
**Reviewer:** Manual (cannot automate)

## Scenario A: Rule Edit → Auto Plan

**Duration:** ~10 minutes  
**URL Path:** `/planning` → `/licenses`

### Setup
- [ ] Logged in with test user (export company with active licenses)
- [ ] Test SION created: E1 or E5
- [ ] Test license created with import items
- [ ] At least 1 existing E1/E5 rule with priority 1

### Execution

#### Step 1-2: Load planning page
```
Action: Navigate to /planning
Expected:
  ✓ Page loads (no 404, no 500)
  ✓ SION selector visible
  ✓ Existing rules listed
  ✓ "Add Rule" button enabled
```
- [ ] Page loads without errors
- [ ] SION selector is interactive
- [ ] Rules list displays

#### Step 3: Edit existing rule
```
Action: Click "Edit" on E1 priority-1 rule
Expected:
  ✓ Form loads with all fields populated
  ✓ Expression tree shows correct conditions
  ✓ Output Item shows selected item
  ✓ Price shows current max_unit_price (e.g., 2.50)
```
- [ ] Form opens (not page reload, modal/side drawer)
- [ ] All fields populated correctly
- [ ] Expression displays visually

#### Step 4: Change price
```
Action: Edit max_unit_price: 2.50 → 2.80
Expected:
  ✓ Field updates immediately in UI
  ✓ Error (if any) is inline, under field, not toast
  ✓ Save button becomes enabled
```
- [ ] Field updates without page reload
- [ ] No validation errors (price is valid)
- [ ] Save button is enabled

#### Step 5: Save rule
```
Action: Click "Save"
Expected:
  ✓ API call succeeds (check DevTools Network tab)
  ✓ Toast shows success message (e.g., "Rule saved")
  ✓ Form remains open
  ✓ Version number incremented (e.g., v1 → v2)
```
- [ ] Success toast appears (top right)
- [ ] Form does not close
- [ ] No page reload
- [ ] Version incremented in UI

#### Step 6: Reload page
```
Action: Browser refresh (Ctrl+R or Cmd+R)
Expected:
  ✓ Form closes
  ✓ Planning page reloads
  ✓ Rule still shows with new price (2.80)
  ✓ Version shows updated
```
- [ ] Page reloads successfully
- [ ] Rule persisted with new price
- [ ] Version number updated

#### Step 7: Navigate to licenses
```
Action: Navigate to /licenses
Expected:
  ✓ License list loads
  ✓ Test license visible and clickable
  ✓ License status shows (Active, etc.)
```
- [ ] License list loads
- [ ] Test license is in list

#### Step 8: Auto plan license
```
Action: Expand license → Plan tab → Click "Auto Plan"
Expected:
  ✓ No page reload (Plan tab stays visible)
  ✓ Spinner appears briefly
  ✓ Toast shows success (e.g., "Plan created: 5 items, qty 100 units")
  ✓ Plan tab refreshes with new plan rows
```
- [ ] Spinner visible (loading indicator)
- [ ] Success toast with counts
- [ ] Plan tab updates (new rows visible)
- [ ] NO page reload

#### Step 9: Verify plan uses new price
```
Action: Open Item Pivot report or view plan details
Expected:
  ✓ Plan shows calculated with new price (2.80)
  ✓ Total CIF reflects new price
  ✓ Plan is from Step 8 execution, not recalculated
```
- [ ] Plan data visible with correct calculations
- [ ] New price (2.80) was used in plan

### Acceptance Criteria
- [x] All steps 1-9 completed without errors
- [x] No page reloads except browser refresh (Step 6)
- [x] No console errors (F12 → Console tab)
- [x] Toast messages appear for user feedback
- [x] Data persists across page reloads

---

## Scenario B: Force Re-Plan After Rule Change

**Duration:** ~10 minutes  
**Prerequisite:** Scenario A completed

### Setup
- [ ] License from Scenario A has active plan with qty*2.50 calculations
- [ ] Still on /licenses page with plan visible

### Execution

#### Step 1-2: Return to planning, edit same rule
```
Action: Navigate back to /planning
        Select E1
        Click "Edit" on priority-1 rule
Expected:
  ✓ Form shows current data (price still 2.80 from Scenario A)
```
- [ ] Form loads with 2.80

#### Step 3: Change price again
```
Action: Edit price: 2.80 → 3.00
```
- [ ] Field updates to 3.00

#### Step 4: Save
```
Action: Click "Save"
Expected:
  ✓ Toast shows success
```
- [ ] Save succeeds

#### Step 5: Reload planning page
```
Action: Refresh /planning
Expected:
  ✓ Rule shows price 3.00
```
- [ ] Price persisted (3.00)

#### Step 6: Navigate back to licenses
```
Action: Go to /licenses
```
- [ ] License list loads

#### Step 7: Verify old plan still exists
```
Action: Expand license → Plan tab
Expected:
  ✓ Plan still shows old calculation (qty*2.80)
  ✓ Total CIF unchanged from Scenario A
```
- [ ] Old plan data visible (price 2.80 still in existing plan)

#### Step 8: Force re-plan
```
Action: Click "Force Re-plan" button
Expected:
  ✓ Spinner appears
  ✓ Toast shows success (e.g., "Plan re-planned: 5 items")
  ✓ Plan tab updates with new data
```
- [ ] Spinner visible
- [ ] New plan created
- [ ] Toast shows success

#### Step 9: Verify new plan uses new price
```
Action: Check plan total CIF
Expected:
  ✓ Total CIF changed (higher by qty*0.20)
  ✓ Plan reflects price 3.00
```
- [ ] Plan recalculated with 3.00
- [ ] CIF increased as expected

#### Step 10: Verify different SION unaffected
```
Action: In /licenses, find a different SION license (e.g., E5)
Expected:
  ✓ E5 license plan unchanged
  ✓ Auto Plan button works for E5
```
- [ ] Other SION licenses are independent

### Acceptance Criteria
- [x] Steps 1-10 completed
- [x] Price change propagates to new plans only
- [x] Old plans retained, then replaced by Force Re-plan
- [x] No cross-SION impacts

---

## Scenario C: Split Allocation UI

**Duration:** ~15 minutes  
**SION:** E5 (Milk Products - has split categories)

### Setup
- [ ] E5 SION selected in /planning
- [ ] Rules with split outputs created:
  - SWP (Sweet Whey Powder)
  - DWP (Demineralized Whey Powder)
  - Optional: BUTTERMILK (3rd output)

### Execution

#### Step 1: Load split rule
```
Action: Navigate /planning → E5 → Edit existing split rule
Expected:
  ✓ Split editor visible
  ✓ Two or more output rows shown (SWP, DWP, etc.)
  ✓ Each row has: Item selector, Ratio (%), Prices
```
- [ ] Split editor loads
- [ ] Multiple outputs visible

#### Step 2: Verify outputs
```
Action: Check each output row
Expected:
  ✓ Output 1: SWP, ratio 50%, price shown
  ✓ Output 2: DWP, ratio 50%, price shown
```
- [ ] Each output configured correctly

#### Step 3: Add new output
```
Action: Click "+ Add Output" button
Expected:
  ✓ New row added to split
  ✓ Default values (empty item, ratio, prices)
  ✓ Remove button available for new row
```
- [ ] New row added at bottom
- [ ] Remove icon visible for new row

#### Step 4: Configure new output
```
Action: Select item for new output
        Set ratio (e.g., 20%)
        Set price
Expected:
  ✓ Item selector shows available items
  ✓ Selection saves in UI
  ✓ Ratio and prices can be entered
```
- [ ] New output fields editable
- [ ] Values update in UI

#### Step 5: Auto-adjust ratios (if supported)
```
Action: Click "Auto-balance ratios" (if available)
Expected:
  ✓ Ratios recalculate to sum to 100%
  ✓ All outputs remain included
```
- [ ] Ratios auto-balanced (or manual entry OK)

#### Step 6: Save split rule
```
Action: Click "Save"
Expected:
  ✓ API call succeeds
  ✓ Toast shows success
  ✓ All 3+ outputs persisted
```
- [ ] Success toast
- [ ] All outputs saved

#### Step 7: Reload to confirm persistence
```
Action: Refresh /planning
Expected:
  ✓ Rule loads with 3 outputs
  ✓ All outputs correct (items, ratios, prices)
```
- [ ] All outputs persist after reload

#### Step 8: Force re-plan with split
```
Action: Go to /licenses → Force Re-plan
Expected:
  ✓ Plan created with all 3 outputs
  ✓ Qty conserved across outputs
  ✓ Total CIF conserved
```
- [ ] Plan shows all output items
- [ ] Allocation correct (qty distributed by ratio)

#### Step 9: Change a ratio
```
Action: Edit split rule → Change SWP ratio 50% → 70%
        Click "Auto-balance" or manually adjust DWP
        Save
Expected:
  ✓ Ratio change persisted
```
- [ ] New ratios saved

#### Step 10: Force re-plan again
```
Action: Force Re-plan
Expected:
  ✓ Plan allocation changes
  ✓ SWP qty increased, DWP qty decreased
  ✓ Total qty and CIF still conserved
```
- [ ] New allocation reflects ratio change
- [ ] Conservation maintained

### Acceptance Criteria
- [x] Split editor visible and functional
- [x] Can add/remove outputs
- [x] Ratios sum to 100%
- [x] All outputs persist
- [x] Plan allocation matches ratios
- [x] Qty and CIF conserved

---

## Scenario D: Error UX

**Duration:** ~8 minutes

### Setup
- [ ] On /planning, E1 selected

### Execution

#### Step 1: Try to save rule without name
```
Action: Click "Add Rule"
        Leave Name field empty
        Click "Save"
Expected:
  ✓ Inline error appears BELOW Name field (not just toast)
  ✓ Error text: "Name required" (or similar)
  ✓ Save button remains disabled
  ✓ NO HTTP request sent (no error toast)
```
- [ ] Error message under Name field
- [ ] Save button disabled
- [ ] No page changes

#### Step 2: Fix error
```
Action: Enter rule name (e.g., "Test Rule")
Expected:
  ✓ Error disappears
  ✓ Save button becomes enabled
```
- [ ] Error clears when field populated
- [ ] Save button enabled

#### Step 3: Try to save split with <2 outputs
```
Action: Click "Add Rule" with split
        Add only 1 output (e.g., SWP only)
        Click "Save"
Expected:
  ✓ Inline error appears (e.g., "At least 2 outputs required for split")
  ✓ Save button disabled
```
- [ ] Error visible
- [ ] Save blocked

#### Step 4: Add second output
```
Action: Click "+ Add Output"
        Configure 2nd output (DWP)
Expected:
  ✓ Error disappears
  ✓ Save button enabled
```
- [ ] Error clears
- [ ] Save enabled

#### Step 5: Try invalid residual target
```
Action: If residual policy dropdown exists:
        Set residual policy to "ALLOCATE_REMAINDER"
        Set residual target to item NOT in split outputs
        Click "Save"
Expected:
  ✓ Inline error (e.g., "Target must be in split outputs")
  ✓ Save blocked
```
- [ ] Validation error shown (or success if not yet implemented)

#### Step 6: Clear all errors
```
Action: Correct all errors
        Enter valid name
        Ensure 2+ split outputs
        Set valid residual target (if applicable)
        Click "Save"
Expected:
  ✓ Save succeeds
  ✓ Toast shows success
```
- [ ] Save succeeds with valid data
- [ ] Success toast

### Acceptance Criteria
- [x] All validation errors shown inline (not just toast)
- [x] Save button disabled during errors
- [x] Errors clear when fields corrected
- [x] No spurious error messages

---

## Scenario E: NO PAGE RELOADS

**Throughout all above scenarios, verify:**

### Global Observations (Can be checked during each scenario)

- [ ] **Planning form save** (Scenarios A-C): Modal/side drawer stays open, NO page reload
- [ ] **Auto Plan** (Scenario A, Step 8): Plan tab updates via API, NO full page reload
- [ ] **Force Re-plan** (Scenario B, Step 8): Plan tab updates via API, NO full page reload
- [ ] **Split output add** (Scenario C, Step 3): New row appears, NO page reload
- [ ] **Error validation** (Scenario D, Step 1): Error appears inline, NO page reload
- [ ] **Browser refresh** (Step 6 of Scenario A): Only this should be a full page reload

### DevTools Verification

- [ ] Open DevTools (F12)
- [ ] Go to Network tab
- [ ] Filter by XHR (XMLHttpRequest)
- [ ] Execute each scenario
- [ ] Verify:
  - [ ] POST /api/sion-rules/ (save rule)
  - [ ] POST /api/licenses/{id}/plan/ (auto plan)
  - [ ] GET /api/license-item-plans/ (fetch plans after plan creation)
  - [ ] NO requests to `/planning` (would indicate page reload)
  - [ ] NO requests to `/licenses` (would indicate page reload)

### Console Verification

- [ ] Open DevTools Console tab (F12)
- [ ] Execute all scenarios
- [ ] Verify:
  - [ ] NO errors logged
  - [ ] NO "Uncaught ReferenceError" messages
  - [ ] NO "404 Not Found" messages
  - [ ] NO warnings (exceptions are OK if handled)

### Acceptance Criteria
- [x] All form operations use modal (not page reload)
- [x] All plan operations use API calls (not page reload)
- [x] DevTools shows only expected XHR calls
- [x] No console errors

---

## Sign-Off

**Tester Name:** _________________________  
**Date:** _________________________  
**Scenarios Passed:**
- [ ] Scenario A: Rule Edit → Auto Plan ✓
- [ ] Scenario B: Force Re-Plan ✓
- [ ] Scenario C: Split Allocation ✓
- [ ] Scenario D: Error UX ✓
- [ ] Scenario E: NO PAGE RELOADS ✓

**Overall Status:**
- [ ] ALL SCENARIOS PASSED ✓
- [ ] BLOCKERS FOUND (list below)

**Blockers (if any):**
```
[List any failures or issues found]
```

**Notes:**
```
[Additional observations or recommendations]
```

---

**This checklist is part of Phase 2D.5 Freeze Gate Verification.**
