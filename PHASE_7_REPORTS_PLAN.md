# Phase 7: Reports MUI DataGrid Migration

## Executive Summary

**Objective**: Convert all 11 report pages to Material UI with MUI DataGrid  
**Duration**: 7-10 days  
**Status**: Planning (Awaiting MUI DataGrid Library)  
**Risk Level**: Medium (Complex filter/calculation logic + export functionality)

---

## 11 Reports to Migrate

### Group 1: SION Norm Reports (4 pages)
**Entry Points**: `/reports/parle/sion-e1|e5|e126|e132`  
**Current Files**:
- `frontend/src/pages/reports/SionE1.tsx`
- `frontend/src/pages/reports/SionE5.tsx`
- `frontend/src/pages/reports/SionE126.tsx`
- `frontend/src/pages/reports/SionE132.tsx`
- `frontend/src/pages/reports/SionNormReport.tsx` (shared component)
- `frontend/src/pages/reports/NormCardGrid.tsx` (grid component)

**Current State**: Tailwind/shadcn UI wrapper, HTML tables for data
**Deliverable**: MUI DataGrid + MUI TextField/Select/DatePicker filters

### Group 2: License Reports (2 pages)
**Entry Points**: `/reports/expiring-licenses`, `/reports/active-licenses`  
**Current Files**:
- `frontend/src/pages/reports/ExpiringLicenses.tsx`
- `frontend/src/pages/reports/ActiveLicenses.tsx`
- `frontend/src/components/reports/LicenseExportPanel.tsx` (shared component)

**Current State**: Shared panel with minimal filters, direct Excel export
**Deliverable**: MUI form controls + export functionality preserved

### Group 3: Item Reports (2 pages)
**Entry Points**: `/reports/item-pivot`, `/reports/item-report`  
**Current Files**:
- `frontend/src/pages/reports/ItemPivotReport.tsx` (complex pivot logic)
- `frontend/src/pages/reports/ItemReport.tsx`
- `frontend/src/pages/reports/ItemPivotFilters.tsx` (filters)
- `frontend/src/pages/reports/itemReport/ItemReportFilters.tsx`
- `frontend/src/pages/reports/itemReport/ItemReportTable.tsx`
- `frontend/src/pages/reports/itemReport/ItemReportTotalsBar.tsx`

**Current State**: Tailwind+shadcn, custom table rendering with sticky columns
**Deliverable**: MUI DataGrid + all pivot/calculation logic preserved

### Group 4: Planning/Financial Reports (3 pages)
**Entry Points**: `/reports/planned-report`, `/reports/license-purchase-profit`, `/reports/download-license`  
**Current Files**:
- `frontend/src/pages/reports/PlannedReport.tsx`
- `frontend/src/pages/reports/LicensePurchaseProfitReport.tsx`
- `frontend/src/pages/reports/DownloadLicense.tsx`
- `frontend/src/pages/reports/licensePurchaseProfitReport/ExcludeLicenseNumberInput.tsx`
- `frontend/src/pages/reports/licensePurchaseProfitReport/ItemUtilizationMatrix.tsx`
- `frontend/src/pages/reports/licensePurchaseProfitReport/useLicensePurchaseProfitReportFilters.ts`

**Current State**: Tailwind/shadcn, HTML tables
**Deliverable**: MUI DataGrid + financial calculations preserved

---

## Critical Dependency: MUI DataGrid Library

### Status
- ❌ `@mui/x-data-grid` NOT currently installed
- ❌ Requires npm install or yarn add

### Required Installation
```bash
npm install @mui/x-data-grid @mui/x-data-grid-pro # (if pro features needed for licensing)
```

### Features Needed
- **Core DataGrid**: Column definition, sorting, filtering, pagination
- **Row Selection**: Multi-select checkboxes
- **Aggregations**: Totals rows, subtotals
- **Export**: CSV/Excel export (native or via utils)
- **Responsive**: Column resizing, scrollable
- **Dark Mode**: Theme-aware styling

### Implementation Strategy
1. Install `@mui/x-data-grid` (community edition sufficient)
2. Configure columns for each report
3. Create reusable report table wrapper
4. Migrate sort/filter/export logic to DataGrid equivalents

---

## Implementation Sequence

### Phase 7.1: Foundation (Days 1-2)
**Goal**: Set up MUI DataGrid infrastructure and utilities

**Tasks**:
- [x] Verify MUI theme is complete (colors, typography, spacing)
- [ ] Install `@mui/x-data-grid`
- [ ] Create reusable report filter components:
  - `ReportDateRangeFilter.tsx` (MUI DatePicker)
  - `ReportMultiSelect.tsx` (MUI Select with multi-select)
  - `ReportTextField.tsx` (MUI TextField wrapper)
- [ ] Create reusable DataGrid wrapper:
  - `ReportDataGrid.tsx` (standardized columns, styling, export)
  - Support for totals row
  - Support for custom formatters (currency, date)
- [ ] Create export utilities:
  - CSV export (using existing ExcelJS or new util)
  - Excel export (preserve current functionality)
  - PDF export (preserve current functionality)
- [ ] Test dark mode with DataGrid

**Files to Create**:
- `frontend/src/components/reports/ReportDateRangeFilter.tsx`
- `frontend/src/components/reports/ReportMultiSelect.tsx`
- `frontend/src/components/reports/ReportTextField.tsx`
- `frontend/src/components/reports/ReportDataGrid.tsx`
- `frontend/src/utils/reportExport.ts` (centralized export logic)

**Dependencies**: MUI DataGrid must be installed

### Phase 7.2: Simple Reports (Days 3-4)
**Goal**: Migrate License (Expiring/Active) reports first as they have minimal complexity

**Tasks**:
1. **ExpiringLicenses.tsx**
   - Convert LicenseExportPanel filters to MUI TextField/Select
   - Preserve Excel export logic
   - Test: Filter + export combo

2. **ActiveLicenses.tsx**
   - Same as ExpiringLicenses (nearly identical)
   - Test: Filter + export combo

**Success Criteria**:
- [ ] Filters render with MUI styling
- [ ] Export functionality identical to original
- [ ] Dark mode works
- [ ] Responsive on mobile (375px, 768px)
- [ ] No TypeScript errors
- [ ] Lint passes

**Files Modified**:
- `frontend/src/pages/reports/ExpiringLicenses.tsx`
- `frontend/src/pages/reports/ActiveLicenses.tsx`
- `frontend/src/components/reports/LicenseExportPanel.tsx`

### Phase 7.3: SION Reports (Days 5-6)
**Goal**: Migrate SION Norm reports (E1, E5, E126, E132)

**Strategy**:
- All 4 SION reports use `SionNormReport` component (shared)
- Specific normalization varies (E1/E5/E126/E132)
- Current: HTML `<table>` with complex headers (rowSpan, colSpan)
- Target: MUI DataGrid with equivalent column structure

**Tasks**:
1. **SionNormReport.tsx (shared)**
   - Convert filters to MUI components
   - Replace `<table>` with `ReportDataGrid`
   - Preserve all calculations (no changes to `formatNumber`, `formatDate`)
   - Preserve filter logic (is_expired, is_null)
   - Test all filter combinations

2. **SionE1/E5/E126/E132.tsx (thin wrappers)**
   - Pass correct normalization to `SionNormReport`
   - No other changes needed

**Calculation Logic Preserved** (zero changes):
- `formatReportNumber(num, decimals)` → column formatter
- `formatDate(dateStr)` → column formatter
- Filter logic: `is_expired`, `is_null`, `sion_norm`
- Grouping: By license DFIA No
- Totals: Per-group totals

**Success Criteria**:
- [ ] All 4 reports load and render identically
- [ ] Filters work: single + combo
- [ ] Sorting works on all columns
- [ ] Calculations match old reports (spot-check 5 rows)
- [ ] Responsive + dark mode
- [ ] TypeScript green

**Files Modified**:
- `frontend/src/pages/reports/SionNormReport.tsx`
- `frontend/src/pages/reports/sionNormReportUtils.ts` (if needed)
- No changes to SionE1/E5/E126/E132.tsx required

### Phase 7.4: Item Reports (Days 7-8)
**Goal**: Migrate Item Pivot and Item Reports (complex pivot logic)

**Strategy**:
- ItemPivotReport: Complex pivot table with conditional styling
- ItemReport: Detailed item data with filters and totals
- Both have sophisticated calculation logic that MUST NOT change

**Tasks**:
1. **ItemPivotReport.tsx**
   - Convert filters (ItemPivotFilters.tsx) to MUI components
   - Keep pivot calculation logic UNCHANGED
   - Replace custom table with MUI DataGrid
   - Preserve:
     - Item background color coding
     - Purchase status badges
     - Condition/Transfer/Note action pills
     - Per-item pivot calculations
     - Totals row
   - Test: Filter combinations, sorting, export

2. **ItemReport.tsx**
   - Convert filters (ItemReportFilters.tsx) to MUI components
   - Replace ItemReportTable.tsx with MUI DataGrid
   - Preserve:
     - All item calculations
     - Totals bar (ItemReportTotalsBar.tsx)
     - Filter logic (license, item, status, etc.)
   - Test: All filter combos, sorting

3. **Helper Files**:
   - Update ItemPivotFilters.tsx to use MUI (or inline in ItemPivotReport)
   - Update itemReport/ItemReportFilters.tsx to use MUI
   - Update itemReport/ItemReportTable.tsx to use MUI DataGrid
   - Keep ItemReportTotalsBar.tsx as-is (it's logic, not table)

**Calculation Logic to Preserve**:
```
// Item Pivot
pivotNumber(num, norm) → column formatter
isPositivePivotIssue(val) → conditional styling
itemBgColor(idx) → background tint (use MUI sx)

// Item Report
reportTable generation, biscuit/confectionery conversions
All formulas in itemPivotReportUtils.ts
```

**Success Criteria**:
- [ ] ItemPivotReport: Pivot calculations match old report exactly
- [ ] ItemReport: Item totals match old report exactly
- [ ] Filters work (all combinations tested)
- [ ] Sorting works
- [ ] Responsive + dark mode
- [ ] Action pills (Condition, Transfer, Note) still functional
- [ ] Export works
- [ ] TypeScript green

**Files Modified**:
- `frontend/src/pages/reports/ItemPivotReport.tsx`
- `frontend/src/pages/reports/ItemPivotFilters.tsx`
- `frontend/src/pages/reports/ItemReport.tsx`
- `frontend/src/pages/reports/itemReport/ItemReportFilters.tsx`
- `frontend/src/pages/reports/itemReport/ItemReportTable.tsx`
- `frontend/src/pages/reports/itemReport/ItemReportTotalsBar.tsx` (keep, update styling if needed)

### Phase 7.5: Planning/Financial Reports (Days 9)
**Goal**: Migrate PlannedReport, LicensePurchaseProfitReport, DownloadLicense

**Tasks**:
1. **PlannedReport.tsx**
   - Convert filters to MUI
   - Replace table with MUI DataGrid
   - Preserve allocation calculations
   - Test: Filter combos, sorting

2. **LicensePurchaseProfitReport.tsx**
   - Convert filters (useLicensePurchaseProfitReportFilters.ts) to MUI
   - Replace table with MUI DataGrid
   - Preserve:
     - Profit calculations
     - ItemUtilizationMatrix.tsx (keep as-is or migrate if it's a table)
     - ExcludeLicenseNumberInput.tsx (update to MUI if needed)
   - Test: Financial accuracy, filter combos

3. **DownloadLicense.tsx**
   - This is just a download button (no table)
   - Update button styling to MUI if needed
   - Preserve download logic

**Success Criteria**:
- [ ] All financial calculations match old reports
- [ ] Filters work
- [ ] Export works
- [ ] Responsive + dark mode
- [ ] TypeScript green

**Files Modified**:
- `frontend/src/pages/reports/PlannedReport.tsx`
- `frontend/src/pages/reports/LicensePurchaseProfitReport.tsx`
- `frontend/src/pages/reports/licensePurchaseProfitReport/ExcludeLicenseNumberInput.tsx`
- `frontend/src/pages/reports/licensePurchaseProfitReport/ItemUtilizationMatrix.tsx`
- `frontend/src/pages/reports/DownloadLicense.tsx` (if styling update needed)

### Phase 7.6: QA & Validation (Days 10)
**Goal**: Full regression testing across all 11 reports

**Tasks**:
1. **Lint & TypeCheck**: `npm run lint && npm run typecheck` (all green)
2. **Build**: `npm run build` (succeeds, no warnings)
3. **Functionality Test**: Each report
   - Load data
   - Apply filters (single + multi + combinations)
   - Sort columns
   - Export (CSV/Excel/PDF)
   - Check calculations (spot-check 10 rows per report)
4. **Dark Mode**: All 11 reports in light + dark
5. **Responsive**: Mobile (375px), Tablet (768px), Desktop (1440px)
6. **Performance**: No N+1s, no layout shifts, export speed acceptable
7. **Accessibility**: Keyboard nav, screen reader labels, contrast

**Blockers/Fixes**: Address any issues discovered

---

## Quality Gates (Non-Negotiable)

### Code Quality
- [ ] TypeScript: Zero errors (strict mode)
- [ ] Lint: eslint passes with no warnings
- [ ] Build: `npm run build` succeeds
- [ ] No unused imports or dead code
- [ ] Consistent with `.claude/rules.md`

### Functionality
- [ ] All 11 reports load without errors
- [ ] Filters: Single, multi, and combination filters work
- [ ] Sorting: All columns sortable
- [ ] Export: CSV/Excel/PDF export identical to original
- [ ] Calculations: Spot-check 5-10 rows per report, match exactly
- [ ] Totals/Subtotals: Display correctly, math correct
- [ ] Currency formatting: ₹ symbol, decimal places correct
- [ ] Date formatting: Consistent, readable
- [ ] No console errors or warnings
- [ ] No API call changes (use existing endpoints)

### UX/Styling
- [ ] Dark mode: All reports readable (WCAG AA contrast)
- [ ] Responsive: Works at 375px, 768px, 1440px widths
- [ ] Tables: Sortable headers, scrollable on mobile
- [ ] Filters: Clear active filters display
- [ ] Buttons: MUI styled, consistent sizing
- [ ] Loading states: Spinner shown during data fetch
- [ ] Error states: Toast/alert shown on failure
- [ ] Empty states: Message shown when no data

### Performance
- [ ] Report load time: < 3s (same as before or better)
- [ ] Filter response: < 1s
- [ ] Export generation: < 5s for large reports
- [ ] No layout thrashing on scroll
- [ ] Bundle size: < 1% increase

---

## Critical Constraints

### Business Logic (ZERO CHANGES)
- All calculations, formulas, aggregations must match original exactly
- Filter logic must work identically
- API calls must be unchanged
- Permissions must be preserved
- Export functionality must match original

### Data Integrity
- All rows must display (no hidden/truncated data)
- All columns must be visible (or scrollable)
- Totals must be accurate
- Sorting must not change order incorrectly
- Filtering must not lose rows

### User Experience
- No loss of functionality
- No broken filters
- No missing columns
- No calculation errors
- No slowdowns

---

## Risk Analysis

### High Risk Areas
1. **Pivot Table Logic** (ItemPivotReport)
   - Complex multi-dimensional pivot
   - Many custom calculations
   - Mitigation: Keep calculation functions untouched, only replace UI
   
2. **SION Report Headers** (SionNormReport)
   - Complex multi-level headers (rowSpan/colSpan)
   - Mitigation: Use DataGrid column grouping or nested headers

3. **Export Functionality** (All reports)
   - PDF/Excel export must work identically
   - Mitigation: Keep export logic separate from table rendering

4. **Performance on Large Reports**
   - Some reports may have 1000+ rows
   - Mitigation: Use DataGrid virtualization, pagination

### Low Risk Areas
- Filter UI updates (shadcn → MUI TextField/Select)
- Card/layout styling (Tailwind → MUI Box/Grid)
- Dark mode (already set up in theme)

---

## Implementation Patterns

### Filter Component Pattern
```tsx
// OLD (Tailwind/shadcn)
<Input value={filter} onChange={(e) => setFilter(e.target.value)} />

// NEW (MUI)
<TextField
  value={filter}
  onChange={(e) => setFilter(e.target.value)}
  variant="outlined"
  size="small"
  fullWidth
/>
```

### Table Component Pattern
```tsx
// OLD (HTML table)
<table>
  <thead><tr><th>Header</th></tr></thead>
  <tbody>
    {data.map(row => <tr key={row.id}><td>{row.value}</td></tr>)}
  </tbody>
</table>

// NEW (MUI DataGrid)
<DataGrid
  rows={data}
  columns={[
    { field: 'id', headerName: 'ID', width: 100 },
    { field: 'value', headerName: 'Header', width: 150 }
  ]}
  density="compact"
  disableSelectionOnClick
/>
```

### Calculation Preservation
```tsx
// Keep calculation functions UNCHANGED
const formatNumber = (num) => formatReportNumber(num, 2);
const formatDate = (date) => formatDateUtil(date);

// Use as column formatters
{
  field: 'amount',
  headerName: 'Amount',
  renderCell: (params) => formatNumber(params.value)
}
```

---

## Files Checklist

### Create (New Files)
- [ ] `frontend/src/components/reports/ReportDateRangeFilter.tsx`
- [ ] `frontend/src/components/reports/ReportMultiSelect.tsx`
- [ ] `frontend/src/components/reports/ReportTextField.tsx`
- [ ] `frontend/src/components/reports/ReportDataGrid.tsx`
- [ ] `frontend/src/utils/reportExport.ts`

### Modify (Report Pages)
- [ ] `frontend/src/pages/reports/ExpiringLicenses.tsx`
- [ ] `frontend/src/pages/reports/ActiveLicenses.tsx`
- [ ] `frontend/src/pages/reports/SionNormReport.tsx`
- [ ] `frontend/src/pages/reports/ItemPivotReport.tsx`
- [ ] `frontend/src/pages/reports/ItemPivotFilters.tsx`
- [ ] `frontend/src/pages/reports/ItemReport.tsx`
- [ ] `frontend/src/pages/reports/itemReport/ItemReportFilters.tsx`
- [ ] `frontend/src/pages/reports/itemReport/ItemReportTable.tsx`
- [ ] `frontend/src/pages/reports/PlannedReport.tsx`
- [ ] `frontend/src/pages/reports/LicensePurchaseProfitReport.tsx`
- [ ] `frontend/src/pages/reports/licensePurchaseProfitReport/ExcludeLicenseNumberInput.tsx`
- [ ] `frontend/src/pages/reports/DownloadLicense.tsx` (if needed)

### Keep Unchanged (Utilities/Logic)
- [ ] `frontend/src/pages/reports/sionNormReportUtils.ts`
- [ ] `frontend/src/pages/reports/itemPivotReportUtils.ts`
- [ ] `frontend/src/pages/reports/itemReport/ItemReportTotalsBar.tsx` (keep, maybe update styling)
- [ ] `frontend/src/pages/reports/itemReport/ItemReportTotalsBar.tsx`
- [ ] All calculation/formula files

---

## Success Criteria (Final)

When Phase 7 is complete:
1. ✅ All 11 reports use MUI DataGrid (no HTML tables)
2. ✅ All filters use MUI components (TextField, Select, DatePicker)
3. ✅ All reports render identically to originals (visual check)
4. ✅ All calculations match (spot-check 20 total rows)
5. ✅ All exports work (CSV, Excel, PDF)
6. ✅ Dark mode fully supported
7. ✅ Responsive on all devices
8. ✅ TypeScript: zero errors
9. ✅ Lint: passes
10. ✅ Build: succeeds
11. ✅ No regressions in existing tests
12. ✅ No performance degradation

---

## Next Steps

1. **Immediate**: Install `@mui/x-data-grid` (waiting on approval)
2. **Day 1**: Create shared filter/table components
3. **Days 2-3**: License reports (Expiring/Active)
4. **Days 4-5**: SION reports (E1/E5/E126/E132)
5. **Days 6-7**: Item reports (Pivot/Report)
6. **Days 8-9**: Planning/Financial reports
7. **Day 10**: Full QA + fixes

---

**Status**: Planning → Awaiting MUI DataGrid Library Installation  
**Last Updated**: 2026-09-28
