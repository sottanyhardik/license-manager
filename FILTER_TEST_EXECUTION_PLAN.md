# Filter QA Test Execution Plan

**Mission**: Comprehensive QA audit of ALL filters across 40+ routes  
**Start Date**: 2026-09-25  
**Tester**: QA Test Engineer  
**Environment**: Development

---

## Phase 1: Discovery & Inventory ✓ COMPLETE

- [x] Identify all 57 routes in AppRoutes.tsx
- [x] Identify 40+ filterable pages
- [x] Document all filter implementations in FILTER_DISCOVERY.md
- [x] Create QA_FILTER_ROUTE_INVENTORY.md
- [x] Create ActiveFilters component

---

## Phase 2: Implementation (IN PROGRESS)

### Subtask 2.1: Implement ActiveFilters Component on All Pages

**Status**: Component created ✓

**Pages to Update** (38+ pages):
- [ ] `/licenses` — Implement ActiveFilters on MasterList (AdvancedFilter)
- [ ] `/allotments` — Implement ActiveFilters on MasterList
- [ ] `/bill-of-entries` — Implement ActiveFilters on MasterList
- [ ] `/trades` — Implement ActiveFilters on MasterList
- [ ] `/incentive-licenses` — Implement ActiveFilters on MasterList
- [ ] `/masters/:entity` — Implement ActiveFilters on MasterList
- [ ] `/license-ledger` — Implement ActiveFilters (custom filters)
- [ ] `/admin/users` — Implement ActiveFilters (UserList)
- [ ] `/admin/activity-log` — Implement ActiveFilters (ActivityLog)
- [ ] `/allotments/:id/allocate` — Implement ActiveFilters (AllotmentAction)
- [ ] `/planning` — Implement ActiveFilters (LicensePlanningWorkspace)
- [ ] `/reports/parle/sion-e1` through `/reports/license-purchase-profit` — Implement on all 11 report pages
- [ ] `/reconciliation` — Implement ActiveFilters (ReconciliationPanel)
- [ ] `/reconciliation-issues` — Implement ActiveFilters (ReconciliationIssues)
- [ ] `/license-ledger/:licenseId` — Implement ActiveFilters (LicenseLedgerDetail)
- [ ] `/licenses/:id/overview` — Implement ActiveFilters (LicenseOverviewPage)

**Acceptance Criteria** (for each page):
- [ ] ActiveFilters component displays when filters applied
- [ ] Hides when no filters applied
- [ ] Shows human-readable filter names
- [ ] Shows actual filter values (not codes)
- [ ] Individual × button removes filter
- [ ] Clear All button removes all filters
- [ ] Count shown is accurate
- [ ] Responsive at all 5 breakpoints
- [ ] WCAG AA accessible

---

### Subtask 2.2: Fix Known Issues

**Issue 1**: LicenseLedger missing ActiveFilters display
- [ ] Add ActiveFilters component
- [ ] Wire up to current filters state
- [ ] Test all 12 filters display correctly
- [ ] Test individual remove buttons
- [ ] Test Clear All button

**Issue 2**: MasterList filter persistence
- [ ] Verify filterPersistence utility working
- [ ] Test filter state retained on refresh
- [ ] Test filter state cleared when appropriate
- [ ] Create regression test

**Issue 3**: ItemReport MultiSelect filter accuracy
- [ ] Verify count includes all selected items
- [ ] Verify displays actual items (not just count)
- [ ] Add display of individual items in ActiveFilters

---

## Phase 3: Systematic Filter Testing

### Test Organization

**Filters by Category**:

1. **MasterList Filters** (6 variations: licenses, allotments, BOE, trades, incentive, masters)
   - Search (text input)
   - Date range filters (varies by entity)
   - Status filters
   - FK relationship filters
   - Choice filters
   - Exclude filters

2. **Report Filters** (11 reports)
   - ItemReport: 12 filters
   - PlannedReport: 12 filters (shared)
   - ItemPivotReport: 8 filters
   - Others: 2-3 filters each

3. **Admin Filters**
   - UserList: 3 filters
   - ActivityLog: 5+ filters

4. **Ledger/Overview Filters**
   - LicenseLedger: 12 filters
   - LedgerDetail: 3+ filters
   - LicenseOverview: 3+ filters

5. **Other Filters**
   - Reconciliation: 5+ filters
   - AllotmentAction: 2 filters
   - LicensePlanning: 1 filter

---

### Test Execution by Page (Priority Order)

#### HIGH PRIORITY (Business-Critical)

##### 1. LicenseLedger — `/license-ledger`

**Component**: `frontend/src/pages/LicenseLedger.tsx`

**Filters to Test**: 12

```
Filter 1: Company (AsyncSelect)
  - Test 1.1: Select company → Verify API includes company param
  - Test 1.2: Change company → Verify data reloads
  - Test 1.3: Clear company → Verify removed from API call
  - Test 1.4: ActiveFilters displays company name
  - Test 1.5: × button on ActiveFilters removes filter
  - Test 1.6: Works with pagination
  - Test 1.7: Export includes filtered data

Filter 2: Min Balance (Number Input)
  - Test 2.1: Enter value → API includes min_balance param
  - Test 2.2: Change value → Filters immediately
  - Test 2.3: Clear value → Removed from API
  - Test 2.4: ActiveFilters shows balance value
  - Test 2.5: Empty results state shows when no licenses above threshold
  - Test 2.6: Decimal values work correctly

Filter 3: License Type (Select)
  - Test 3.1: Select type → API includes license_type param
  - Test 3.2: ALL selects all types
  - Test 3.3: Type options: DFIA, RODTEP, ROSTL, MEIS, ALL_INCENTIVE
  - Test 3.4: ActiveFilters displays type
  - Test 3.5: Multiple selections not possible (single select)

Filter 4: Norm (AsyncSelect, DFIA only)
  - Test 4.1: Only visible when license_type = DFIA or ALL
  - Test 4.2: Loads SION classes from API
  - Test 4.3: Select norm → API includes param
  - Test 4.4: Clear → Removed from API
  - Test 4.5: Help text "(DFIA only)" present

Filter 5: Purchase Status (AsyncSelect, DFIA only)
  - Test 5.1: Only visible when license_type = DFIA or ALL
  - Test 5.2: Loads purchase statuses from API
  - Test 5.3: Select status → API includes param
  - Test 5.4: ActiveFilters shows status label
  - Test 5.5: Help text present

Filter 6: Sort (Select)
  - Test 6.1: Options: Latest, Oldest, High Balance, Low Balance
  - Test 6.2: Default: Latest
  - Test 6.3: Sort + other filters work together
  - Test 6.4: Sort order persisted in results

Filter 7: Search (Text Input)
  - Test 7.1: Debounce delay working
  - Test 7.2: Search by license number → Finds match
  - Test 7.3: Search by exporter → Finds match
  - Test 7.4: Multiple words → Works as "contains"
  - Test 7.5: Clear search → Shows all again
  - Test 7.6: Case-insensitive

Filter 8: Active Only (Toggle Switch)
  - Test 8.1: Off (default) → Shows all licenses
  - Test 8.2: On ��� Shows only active licenses
  - Test 8.3: Toggle visual state changes
  - Test 8.4: API includes active_only param when on
  - Test 8.5: ActiveFilters shows "Active Only"

Filter 9: Include License Numbers (Text Area)
  - Test 9.1: Enter comma-separated list → API param built correctly
  - Test 9.2: Spaces ignored
  - Test 9.3: Duplicates ignored
  - Test 9.4: Partial matches work
  - Test 9.5: API builds include__in param
  - Test 9.6: ActiveFilters shows count

Filter 10: Exclude License Numbers (Text Area)
  - Test 10.1: Enter list → API param built correctly
  - Test 10.2: Excludes matching licenses from results
  - Test 10.3: Spaces/duplicates ignored
  - Test 10.4: Combine with Include → Include takes precedence
  - Test 10.5: API builds exclude__in param

Filter 11: Purchase Bill Status (Button Group)
  - Test 11.1: Options: ALL, WITH_PURCHASE_BILL, NO_PURCHASE_BILL
  - Test 11.2: Default: ALL
  - Test 11.3: Button visual state reflects selection
  - Test 11.4: API includes purchase_bill param
  - Test 11.5: ActiveFilters shows selected value

Filter 12: Purchase Date Range (Date Picker)
  - Test 12.1: Select from date → API includes date__gte param
  - Test 12.2: Select to date → API includes date__lte param
  - Test 12.3: Both dates → Range filter works
  - Test 12.4: Presets: Current FY, Previous FY
  - Test 12.5: Default: Current FY
  - Test 12.6: Clear button removes date filters
  - Test 12.7: ActiveFilters shows date range

**Combination Tests**:
- [ ] Company + Min Balance → Filters licenses by both criteria
- [ ] Type + Status + Sort → Correct ordering in filtered set
- [ ] Include + Exclude License Numbers → Correct precedence
- [ ] All 12 filters together → Complex filter works
- [ ] Add filter → Pagination resets to page 1
- [ ] Remove filter → Data reloads

**State Tests**:
- [ ] Refresh page → Filters NOT persisted (verify expected behavior)
- [ ] Navigate away and back → Filters NOT persisted
- [ ] Clear All → All filters reset to defaults

**API Verification**:
- [ ] Inspect network tab for each filter
- [ ] Verify query params format: `?min_balance=200&company=5&...`
- [ ] Verify gte/lte suffixes on range params
- [ ] Verify comma-separated values in include/exclude

**Export Tests**:
- [ ] Apply filters → Click Export PDF
- [ ] Verify PDF only contains filtered licenses
- [ ] Verify PDF header shows filter summary
- [ ] Export Excel → Verify filtered data matches UI

**Responsive Tests** (5 breakpoints):
- [ ] 1440×900: All inputs visible, Clear buttons reachable
- [ ] 1366×768: Layout wraps correctly
- [ ] 1024×768: Touch-friendly spacing maintained
- [ ] 768×1024: Mobile-friendly layout
- [ ] 390×844: Vertical scrolling acceptable

**Accessibility Tests**:
- [ ] All inputs have <label> tags
- [ ] ARIA labels: aria-label on custom selects
- [ ] Tab order: left-to-right, top-to-bottom
- [ ] Keyboard: Can tab through all inputs, activate buttons
- [ ] Screen reader: Announces filter changes
- [ ] Color: Not sole indicator of filter state

**Error Handling Tests**:
- [ ] Disconnect network → Error toast shows
- [ ] Server timeout → Error handling graceful
- [ ] Invalid date → Error or validation message
- [ ] Very large list (1000+ in include) → Handles without crash

**Performance Tests**:
- [ ] Type in search → Debounce prevents excessive API calls
- [ ] Select dropdown → Opens within 300ms
- [ ] Rapid filter changes → No race condition, shows latest data
- [ ] Export with filtered data → Completes in reasonable time

---

#### MEDIUM PRIORITY (Common Filters)

##### 2. ItemReport — `/reports/item-report`

**Filters to Test**: 12

Tests similar to LicenseLedger but specific to ItemReport:
- [ ] Min Balance (CIF) — ₹ currency formatting
- [ ] Min Available Qty — Quantity units
- [ ] License Status — active/expiring_soon/expired/all
- [ ] Expiry Date Range
- [ ] Include Companies — MultiSelect
- [ ] Exclude Companies — MultiSelect
- [ ] Is Restricted — Tri-state
- [ ] Purchase Status — MultiSelect
- [ ] Norms — MultiSelect
- [ ] Notifications — MultiSelect
- [ ] Product Description — Full-width search
- [ ] HSN Code — Full-width search

**ActiveFilters Verification**:
- [ ] Shows all active filters in chip badges
- [ ] Individual × buttons work
- [ ] Clear All button functional
- [ ] Count accurate for multi-selects

---

##### 3. AdminUsers — `/admin/users`

**Filters to Test**: 3

```
Filter 1: Search
  - Test API includes search param
  - Debounce working
  - Matches username or email

Filter 2: Role
  - Test API includes role param
  - Shows all role options
  - Default "All Roles"

Filter 3: is_active
  - Test API includes is_active param
  - Options: All/Active/Inactive
  - Default "All Status"
```

**Combination Tests**:
- [ ] Search + Role filter
- [ ] Search + is_active filter
- [ ] All three together

---

##### 4. ActivityLog — `/admin/activity-log`

**Filters to Test**: 5+

```
Filter 1: Username (superuser only)
  - Test field hidden for non-superusers
  - Debounce on username input

Filter 2: Action
  - Test dropdown shows all actions
  - API includes action param

Filter 3: Search
  - Test API param
  - Debounce working

Filter 4: Module
  - Test text input
  - Debounce working

Filter 5: Date Range
  - Test from/to dates
  - Test presets: Today, Last 7/30 days
```

---

#### LOWER PRIORITY (Less Complex)

##### 5. PlannedReport, ItemPivotReport, LicensePlanningWorkspace, Reconciliation, etc.

(Each tested similarly to above, abbreviated format)

---

## Phase 4: Bug Documentation & Fixes

### Bug Template

```markdown
## Bug #N: [Title]

**Route**: [Route]
**Page**: [Component]
**Filter**: [Filter Name]
**Severity**: [Critical | High | Medium | Low]
**Status**: [New | Investigating | Fixed | Closed]

### Reproduction Steps
1. Step 1
2. Step 2
3. Step 3

### Expected Behavior
What should happen

### Actual Behavior
What happens instead

### Impact
Business impact or user impact

### Proposed Fix
Suggested solution

### Regression Test
How to prevent this recurring
```

---

## Phase 5: Regression Test Suite

(Created after bugs are fixed)

- [ ] Filter state persistence test
- [ ] ActiveFilters display test
- [ ] Clear All functionality test
- [ ] Individual remove button test
- [ ] API param format test
- [ ] Filter combination test
- [ ] Pagination with filter test
- [ ] Export with filter test
- [ ] Empty result state test
- [ ] Error handling test

---

## Execution Checklist

### Before Testing
- [ ] Fresh install/clean build
- [ ] Backend running and healthy
- [ ] Frontend running
- [ ] Browser DevTools console open
- [ ] Network tab visible
- [ ] Test data populated

### During Testing
- [ ] Document each test result
- [ ] Screenshot failures
- [ ] Capture console errors
- [ ] Note API response times
- [ ] Record browser performance

### After Testing
- [ ] Compile bug list
- [ ] Prioritize by severity
- [ ] Create regression tests
- [ ] Verify all fixes
- [ ] Final report

---

## Success Criteria

- ✅ ALL filters tested (0 untested filters)
- ✅ ALL ActiveFilters components implemented (40+ pages)
- ✅ 100% Clear All functionality working
- ✅ 100% Individual filter remove buttons working
- ✅ 0 API parameter errors
- ✅ All filters responsive at 5 breakpoints
- ✅ WCAG AA compliance on all filter UI
- ✅ < 100ms debounce on text filters
- ✅ 0 race conditions on rapid changes
- ✅ Graceful error handling on all error scenarios
- ✅ All identified bugs fixed or documented
- ✅ Regression test suite passes

---

## Timeline

| Phase | Target Completion |
|-------|------------------|
| Discovery & Inventory | ✓ Complete |
| Implementation (ActiveFilters) | 2026-09-25 EOD |
| LicenseLedger Testing | 2026-09-25 EOD |
| Reports Testing | 2026-09-26 |
| Admin/Other Testing | 2026-09-26 |
| Bug Fix & Verification | 2026-09-26 |
| Regression Suite | 2026-09-26 |
| Final Report | 2026-09-26 |

---

## Status Updates

(Updated throughout mission execution)

```
2026-09-25 10:00 - Discovery phase complete, 40+ filterable pages identified
2026-09-25 10:30 - ActiveFilters component created
2026-09-25 11:00 - Test planning complete
[Tests will be logged as executed]
```

---

**Next Step**: Start Phase 2 implementation of ActiveFilters on LicenseLedger
