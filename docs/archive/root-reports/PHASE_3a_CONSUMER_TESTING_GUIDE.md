# Phase 3a — DataTable Consumer Testing Guide

**Date**: 2026-09-18  
**Purpose**: Detailed testing notes for verifying DataTable improvements don't break consumers

---

## CONSUMER TESTING MATRIX

### 1. ReconciliationIssues.tsx
**File**: `frontend/src/pages/ReconciliationIssues.tsx`  
**Usage Pattern**: Heavy custom cell rendering + row styling  
**Risk Level**: 🟡 MEDIUM

**DataTable Usage**:
```jsx
<DataTable
    data={data ?? []}
    columns={columns}           // Dynamic per tab
    loading={isLoading}
    customCellRender={cellRender}  // Custom rendering for links, formatting
    getRowStyle={rowStyle}       // Yellow highlight for non-zero differences
/>
```

**Special Features**:
- Custom cell renderers for:
  - `LicenseLinks` — Comma-separated license numbers as clickable links
  - `fmtNum()` — Formatted numeric values (CIF, quantity)
  - `cellText()` — Text formatting with fallback
  - `cellDate()` — Date formatting

- Row styling:
  - `DIFF_ROW_STYLE` — Yellow background (`--tb-warning-soft`) + left border accent (`--tb-warning`)
  - Applied when `difference` field is non-zero

**Columns per Tab**:
- **Missing BOE**: invoice_number, counterparty, invoice_date, cif_fc, qty_kg, license (6 cols)
- **Missing Invoice**: bill_of_entry_number, bill_of_entry_date, total_cif_fc, total_quantity, license (5 cols)
- **Duplicate Debits**: debit_line_number, license, amount, ... (variable)
- **Duplicate BOEs**: bill_of_entry_number, boe_date, total_quantity, ... (variable)
- **CIF Comparison**: Shows difference calculations
- **Qty Comparison**: Shows quantity differences

**Test Checklist**:
- [ ] All tabs load correctly with new spacing
- [ ] Table headers are readable and prominent
- [ ] Links in license column work
- [ ] Numeric values are right-aligned
- [ ] Row styling (yellow highlight) still works
- [ ] Custom cell rendering intact
- [ ] No text overflow or wrapping issues
- [ ] Hover states visible on rows
- [ ] Empty state displays correctly (when no issues found)
- [ ] Loading state displays correctly
- [ ] Mobile responsive at 768px and 390px

**Numeric Columns to Verify**:
- `cif_fc` — Currency value, should be right-aligned
- `qty_kg` — Quantity value, should be right-aligned
- `total_cif_fc` — Total currency, should be right-aligned
- `total_quantity` — Total quantity, should be right-aligned
- `amount` — Debit amount, should be right-aligned

**Links to Verify**:
- License links navigate to `/licenses/:id/balance` or `/licenses?search=...`
- Links are underlined on hover
- Links use primary color

---

### 2. DuplicateBoesTab.tsx
**File**: `frontend/src/pages/reconciliation/DuplicateBoesTab.tsx`  
**Usage Pattern**: Simple table with custom cell rendering  
**Risk Level**: 🟢 LOW

**DataTable Usage**:
- Likely similar to other reconciliation tabs
- Custom cell rendering for formatted values
- No row styling

**Test Checklist**:
- [ ] Table displays all columns
- [ ] Data is readable
- [ ] No layout issues
- [ ] Custom rendering works

---

### 3. MissingInvoiceTab.tsx
**File**: `frontend/src/pages/reconciliation/MissingInvoiceTab.tsx`  
**Usage Pattern**: Simple table with custom cell rendering  
**Risk Level**: 🟢 LOW

**DataTable Usage**:
- Similar to DuplicateBoesTab
- Custom cell rendering

**Test Checklist**:
- [ ] Table displays correctly
- [ ] Data is readable

---

### 4. ComparisonTab.tsx
**File**: `frontend/src/pages/reconciliation/ComparisonTab.tsx`  
**Usage Pattern**: Comparison table with calculation results  
**Risk Level**: 🟢 LOW

**DataTable Usage**:
- Shows comparison data (CIF, quantity, etc.)
- Custom rendering for differences

**Test Checklist**:
- [ ] Comparison data displays correctly
- [ ] Numeric alignment is correct

---

### 5. DuplicateDebitsTab.tsx
**File**: `frontend/src/pages/reconciliation/DuplicateDebitsTab.tsx`  
**Usage Pattern**: Simple table with debit information  
**Risk Level**: 🟢 LOW

**DataTable Usage**:
- Shows duplicate debit records
- Simple cell rendering

**Test Checklist**:
- [ ] Table displays correctly

---

### 6. MultiLinkTab.tsx
**File**: `frontend/src/pages/reconciliation/MultiLinkTab.tsx`  
**Usage Pattern**: Table showing multi-linked trades  
**Risk Level**: 🟢 LOW

**DataTable Usage**:
- Shows records with multiple links
- Custom rendering

**Test Checklist**:
- [ ] Multi-link data displays correctly

---

### 7. MissingBoeTab.tsx
**File**: `frontend/src/pages/reconciliation/MissingBoeTab.tsx`  
**Usage Pattern**: Simple table with BOE information  
**Risk Level**: 🟢 LOW

**DataTable Usage**:
- Shows BOE records missing links
- Simple rendering

**Test Checklist**:
- [ ] Table displays correctly

---

### 8. MasterList.tsx
**File**: `frontend/src/pages/masters/MasterList.tsx`  
**Usage Pattern**: Imported but may not be primary table component  
**Risk Level**: 🟡 MEDIUM (import exists)

**Status**: Based on grep, this file imports DataTable but may use other components (AccordionTable, etc.)

**Test Checklist** (if used):
- [ ] If DataTable is used, verify display
- [ ] If not used, no changes needed

---

## TESTING WORKFLOW

### 1. Pre-Implementation Verification
- [ ] Git status clean
- [ ] Current branch: feature/ui-modernization-premium-sas
- [ ] All previous commits present

### 2. CSS Implementation
- [ ] Update tabler.css table styles
- [ ] Update header styling (font-size, weight, padding)
- [ ] Update cell padding
- [ ] Update hover states

### 3. Build Verification
- [ ] Run `npm run build` in frontend directory
- [ ] No build errors
- [ ] No new warnings
- [ ] Build time < 1 second

### 4. TypeCheck Verification
- [ ] Run `npm run typecheck`
- [ ] No new type errors
- [ ] All existing types valid

### 5. Consumer Testing (Per Consumer)
- [ ] Navigate to page
- [ ] Verify table renders
- [ ] Verify data displays
- [ ] Verify custom rendering works
- [ ] Verify row styling works (if applicable)
- [ ] Check mobile responsive at 768px
- [ ] Check mobile responsive at 390px

### 6. Visual QA
- [ ] Light mode appearance
- [ ] Dark mode appearance
- [ ] Header prominence (bold weight visible)
- [ ] Cell padding (breathing room visible)
- [ ] No content clipping
- [ ] No unintended side effects

### 7. Functional QA
- [ ] Links work correctly
- [ ] Numeric values align properly
- [ ] Empty state displays correctly
- [ ] Loading state displays correctly
- [ ] Hover states visible
- [ ] Keyboard navigation works

### 8. Regression Testing
- [ ] No console errors
- [ ] No console warnings
- [ ] No layout shift on hover
- [ ] Scroll performance smooth
- [ ] No accessibility issues
- [ ] Focus states visible

---

## TESTING SEQUENCE

**Recommended Order** (by risk):

1. **ReconciliationIssues** (🟡 MEDIUM) — Highest complexity, custom rendering
2. **All Reconciliation Tabs** (🟢 LOW) — Verify consistency across all tabs
3. **MasterList** (🟡 MEDIUM) — Verify import doesn't break

---

## VISUAL VERIFICATION CHECKLIST

### Header Styling
- [ ] Headers are noticeably bolder (weight increase visible)
- [ ] Headers have adequate padding (breathing room around text)
- [ ] Headers stand out from body (contrast adequate)
- [ ] Text is fully visible (no clipping)

### Cell Styling
- [ ] Cells have comfortable padding
- [ ] Text is vertically centered
- [ ] No text is cramped or overflow
- [ ] Numeric values are right-aligned
- [ ] Data is scannable

### Row Styling
- [ ] Hover state is obvious but subtle
- [ ] Row background changes smoothly
- [ ] Highlighted rows (yellow) are visible
- [ ] Text contrast maintained in highlighted rows

### Responsive Behavior
- [ ] 1440px: Full table with good spacing
- [ ] 1280px: All columns visible
- [ ] 1024px: Still desktop layout
- [ ] 768px: Mobile responsive
- [ ] 390px: Properly stacked

### Dark Mode
- [ ] Headers visible in dark mode
- [ ] Text contrast adequate in dark mode
- [ ] Hover state visible in dark mode
- [ ] Highlighted rows visible in dark mode
- [ ] Border colors appropriate in dark mode

---

## ROLLBACK PLAN

If testing reveals issues:

1. Revert CSS changes (git revert or git reset)
2. Identify the problematic change
3. Adjust CSS values
4. Re-test before committing

---

## SIGN-OFF CHECKLIST

- [ ] All 8 consumers tested and working
- [ ] Build passes
- [ ] TypeCheck passes
- [ ] Visual QA passed (light and dark mode)
- [ ] Responsive testing passed
- [ ] Functional testing passed
- [ ] Regression testing passed
- [ ] Ready to commit

---

## CONSUMER PRIORITY FOR TESTING

**MUST TEST** (affects user workflow):
1. ReconciliationIssues — Portfolio-wide issue discovery
2. All Reconciliation Tabs — Data accuracy critical

**SHOULD TEST** (affects data management):
3. MasterList — Master data visibility

**NICE TO VERIFY** (confirms no regressions):
- Build system
- Type system
- Browser DevTools

---

## NOTES FOR QA

- Phase 3a focuses on CSS styling improvements only
- No functional changes to DataTable
- All data binding, filtering, sorting, editing remain unchanged
- Custom cell rendering must continue to work
- Row styling must continue to work
- All props must be backward compatible

---

**Testing Ready**: ✅ **PHASE 3a.1 COMPLETE**

**Next Step**: Implement CSS changes per PHASE_3a1_DATATABLE_MODERNIZATION_PLAN.md

---

*This guide ensures comprehensive testing of DataTable changes across all consumers.*
