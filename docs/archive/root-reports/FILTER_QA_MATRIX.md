# Filter QA Test Matrix

**Mission Start:** 2026-09-25  
**Objective:** Test every filter on every filterable route

## Test Coverage Summary

| Route | Page | Component | Filter Count | Tests Planned | Tests Completed | Status |
|-------|------|-----------|--------------|---------------|-----------------|--------|
| `/licenses` | Licenses (MasterList) | AdvancedFilter | 6+ | ✓ | — | Queued |
| `/allotments` | Allotments (MasterList) | AdvancedFilter | 6+ | ✓ | — | Queued |
| `/bill-of-entries` | BOE (MasterList) | AdvancedFilter | 6+ | ✓ | — | Queued |
| `/trades` | Trades (MasterList) | AdvancedFilter | 6+ | ✓ | — | Queued |
| `/incentive-licenses` | Incentive Licenses (MasterList) | AdvancedFilter | 6+ | ✓ | — | Queued |
| `/masters/:entity` | Generic Masters (MasterList) | AdvancedFilter | 6+ | ✓ | — | Queued |
| `/license-ledger` | License Ledger | Custom | 12+ | ✓ | — | Queued |
| `/license-ledger/:licenseId` | Ledger Detail | Custom | 3+ | ✓ | — | Queued |
| `/reports/item-report` | Item Report | ItemReportFilters | 12+ | ✓ | — | Queued |
| `/reports/planned-report` | Planned Report | ItemReportFilters | 12+ | ✓ | — | Queued |
| `/reports/item-pivot` | Item Pivot Report | ItemPivotFilters | 8+ | ✓ | — | Queued |
| `/admin/users` | User Management | Custom | 3 | ✓ | — | Queued |
| `/admin/activity-log` | Activity Log | Custom | 5+ | ✓ | — | Queued |
| `/planning` | License Planning | Custom | 1+ | ✓ | — | Queued |
| `/allotments/:id/allocate` | Allotment Action | AllotmentFilters | 2+ | ✓ | — | Queued |
| `/reconciliation` | Reconciliation | Custom (tabs) | 5+ | ✓ | — | Queued |
| `/reconciliation-issues` | Reconciliation Issues | Custom | 3+ | ✓ | — | Queued |
| `/reports/parle/sion-e1` | SION E1 Report | Custom | 2+ | ✓ | — | Queued |
| `/reports/parle/sion-e5` | SION E5 Report | Custom | 2+ | ✓ | — | Queued |
| `/reports/parle/sion-e126` | SION E126 Report | Custom | 2+ | ✓ | — | Queued |
| `/reports/parle/sion-e132` | SION E132 Report | Custom | 2+ | ✓ | — | Queued |
| `/reports/expiring-licenses` | Expiring Licenses | Custom | 2+ | ✓ | — | Queued |
| `/reports/active-licenses` | Active Licenses | Custom | 2+ | ✓ | — | Queued |
| `/reports/download-license` | Download License | Custom | 2+ | ✓ | — | Queued |
| `/reports/license-purchase-profit` | License Purchase Profit | Custom | 2+ | ✓ | — | Queued |
| `/licenses/:id/overview` | License Overview | Custom (tabs) | 3+ | ✓ | — | Queued |

---

## Individual Filter Tests

### Template for Each Filter

```
Filter: [Name]
Route: [Route]
Page: [Component]
Type: [Text Input | Select | MultiSelect | Date Range | etc.]
Default: [Default Value]
Test Cases:
  ✓ Apply filter → Verify API call with correct param
  ✓ Apply multiple filters → Verify correct combination
  ✓ Remove filter → Verify API call without param
  ✓ Clear All → Verify all params cleared
  ✓ Filter with pagination → Verify consistency
  ✓ Filter with sort → Verify combination works
  ✓ Filter persistence (refresh) → Verify state retained or cleared as expected
  ✓ Filter with export → Verify export includes filtered data
  ✓ Empty results → Verify empty state message
  ✓ API error → Verify error handling
  ✓ Responsive → Verify UI at 5 breakpoints
  ✓ Accessibility → Verify ARIA labels, keyboard nav
Status: Not Started
Issues Found: None
```

---

## Test Categories

### Category 1: Individual Filter Tests (Per Filter)

For EVERY discovered filter:
- [ ] Apply single filter
- [ ] Verify API request includes filter param
- [ ] Verify dataset is filtered correctly
- [ ] Remove filter individually
- [ ] Verify data reloads without filter

### Category 2: Filter Combination Tests

- [ ] Apply 2 filters simultaneously
- [ ] Apply 3+ filters simultaneously
- [ ] Verify API combines all filter params
- [ ] Verify dataset filtered by all criteria

### Category 3: Clear/Reset Tests

- [ ] Click "Clear All" or equivalent
- [ ] Verify all filters cleared
- [ ] Verify API called without filter params
- [ ] Verify full dataset returned

### Category 4: Active Filters Display Tests

- [ ] Verify ActiveFilters component visible when filters applied
- [ ] Verify filter count correct
- [ ] Verify filter names human-readable
- [ ] Verify filter values display correctly
- [ ] Verify × button removes individual filter
- [ ] Verify "Clear All" removes all filters
- [ ] Verify ActiveFilters hidden when no filters applied

### Category 5: Pagination Tests

- [ ] Apply filter with multi-page results
- [ ] Verify pagination works with filtered data
- [ ] Change page → verify filter maintained
- [ ] Apply new filter → verify returns to page 1
- [ ] Change page size → verify filter maintained

### Category 6: Sorting Tests

- [ ] Apply sort with filter
- [ ] Verify sort + filter work together
- [ ] Change sort order → verify filter maintained
- [ ] Apply sort then filter → verify correct order

### Category 7: Search Tests

- [ ] Text-based search/filter
- [ ] Verify debounce timing (if applicable)
- [ ] Search + other filters → verify combination
- [ ] Clear search → verify data reloads
- [ ] Special characters in search → verify handled

### Category 8: Export Tests

- [ ] Export with filter applied
- [ ] Verify exported data matches filtered dataset
- [ ] Export multiple formats (PDF, Excel) with filters
- [ ] Verify export count matches visible count

### Category 9: Responsive Tests

For each filterable page, test at 5 breakpoints:
- [ ] Desktop: 1440×900
- [ ] Laptop: 1366×768
- [ ] Tablet: 1024×768
- [ ] Tablet Portrait: 768×1024
- [ ] Mobile: 390×844

Verify:
- [ ] Filter inputs visible/accessible
- [ ] Filter labels readable
- [ ] Clear/Apply buttons reachable
- [ ] No horizontal scroll
- [ ] Touch targets ≥44px

### Category 10: Accessibility Tests

- [ ] Filter inputs have proper labels
- [ ] ARIA labels present and correct
- [ ] Tab order logical
- [ ] Screen reader announces filter changes
- [ ] Keyboard-only navigation works
- [ ] Color not sole indicator of status
- [ ] Contrast ratios meet WCAG AA

### Category 11: Error Handling Tests

- [ ] API timeout → verify error message
- [ ] Network error → verify error message
- [ ] Invalid filter value → verify handled
- [ ] Rapid filter changes → verify no race condition
- [ ] Server error (500) → verify graceful handling

### Category 12: State Persistence Tests

- [ ] Apply filters → Refresh page → Verify state
- [ ] Clear filters → Refresh → Verify cleared
- [ ] Navigate away → Navigate back → Verify state
- [ ] Browser back button → Verify state

---

## Critical Business Logic Filters

**HIGH PRIORITY** — Test these first as they affect business logic:

1. **License Balance Filters** (min balance, status)
   - Accuracy of balance calculations
   - Correct classification (active/expired/expiring)

2. **Allotment Filters** (status, allocation mode)
   - Correct status transitions
   - Plan mode vs Actual mode

3. **Permission-Based Filters**
   - RBAC filters working correctly
   - Users see only authorized data

4. **Purchase Status Filters**
   - Correct categorization
   - Affects financial calculations

5. **Reconciliation Status Filters**
   - Correct grouping of issues
   - All matching records returned

---

## Known Issues & Bugs

| Issue | Route | Status | Severity |
|-------|-------|--------|----------|
| No ActiveFilters display on LicenseLedger | `/license-ledger` | New | Medium |
| Filter persistence not working correctly | `/licenses` | TBD | Medium |
| MultiSelect filter counts not accurate | `/reports/item-report` | TBD | Medium |
| Responsive filter layout broken on mobile | Multiple | TBD | Medium |
| No individual filter remove buttons | Multiple | TBD | Low |

---

## Test Execution Log

(Updated as tests are run)

```
Test Started: 2026-09-25 [TIME]
Tester: QA Test Engineer
Environment: Development
Browser: Chrome 131.x
OS: macOS 14.x

[Tests will be logged here as they execute]
```

---

## Summary Target Metrics

- [ ] **0 untested filters** (every filter tested)
- [ ] **100% Clear All functionality** working
- [ ] **0 missing ActiveFilters displays** on filterable pages
- [ ] **All × buttons functional** on ActiveFilters
- [ ] **0 API param errors** in filter requests
- [ ] **100% responsive** at all 5 breakpoints
- [ ] **WCAG AA compliance** on all filter UIs
- [ ] **< 100ms debounce delay** on text filters
- [ ] **Zero race conditions** on rapid filter changes
- [ ] **Graceful error handling** for all error scenarios

---

## Regression Test Suite

(To be created after bugs are found and fixed)

- [ ] Filter state persists across refresh
- [ ] Clear All resets to default state
- [ ] API combines filter params correctly
- [ ] Empty results show appropriate message
- [ ] Pagination works with filters
- [ ] Export includes filtered data
- [ ] Individual filter remove works
- [ ] Filter combinations work
- [ ] No console errors on filter change
