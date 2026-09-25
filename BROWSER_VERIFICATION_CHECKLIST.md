# Browser Verification Checklist — Complete Route QA

**Status:** READY FOR EXECUTION  
**Total Routes:** 48 (including parameterized variants)  
**Critical Routes:** 15  
**Test Coverage:** 100% of routes

---

## CRITICAL PATH TESTING (Must Verify First)

### Route 1: /login
- [ ] Page loads
- [ ] Form renders (username, password, remember-me)
- [ ] Invalid credentials show error
- [ ] Valid credentials proceed to /dashboard
- [ ] "Forgot Password" link present

### Route 2: /dashboard
- [ ] User redirected after login
- [ ] Dashboard cards load
- [ ] Navigation sidebar visible
- [ ] Key metrics display
- [ ] No console errors

### Route 3: /licenses (MasterList)
- [ ] Table loads with license data
- [ ] Filters present and functional
- [ ] **ActiveFilters component visible** (when filters applied)
- [ ] Search works
- [ ] Pagination works
- [ ] Create License button present
- [ ] Responsive at all breakpoints

### Route 4: /license-ledger
- [ ] Ledger loads with transaction data
- [ ] Filters render
- [ ] **ActiveFilters component present** (when filters applied)
- [ ] Apply filter → Verify results update
- [ ] Remove individual filter (×) → Results update
- [ ] Clear All → All filters removed
- [ ] Export buttons visible

### Route 5: /allotments (MasterList)
- [ ] Table loads
- [ ] Filters functional
- [ ] **ActiveFilters component present**
- [ ] Create button works
- [ ] No type errors

### Route 6: /reports/item-report
- [ ] Report loads with data
- [ ] Filters present (12 expected)
- [ ] **ActiveFilters component present**
- [ ] Apply multiple filters
- [ ] Individual removal works
- [ ] Clear All works

---

## STANDARD ROUTE CHECKLIST TEMPLATE

For each route below, verify:

```
☐ Page loads without error
☐ No console errors or warnings
☐ Layout renders correctly
☐ All expected UI elements present
☐ Filters present (if applicable)
☐ ActiveFilters visible (if filters applied)
☐ Individual filter removal works (× button)
☐ Clear All works (if applicable)
☐ Search/sort/pagination works (if applicable)
☐ Responsive at 1440px
☐ Responsive at 1024px
☐ Responsive at 768px
☐ Responsive at 390px
```

---

## FULL ROUTE INVENTORY (48 routes)

### PUBLIC ROUTES (7)
- [ ] /login
- [ ] /forgot-password
- [ ] / (redirects to /dashboard)
- [ ] /401
- [ ] /403
- [ ] /404
- [ ] /pdf-viewer

### CORE NAVIGATION (3)
- [ ] /dashboard
- [ ] /profile
- [ ] /settings (admin)

### LICENSE MANAGEMENT (6)
- [ ] /licenses
- [ ] /licenses/create
- [ ] /licenses/:id/edit
- [ ] /licenses/:id/overview
- [ ] /licenses/:id/balance (redirects)
- [ ] /license-ledger
- [ ] /license-ledger/:id
- [ ] /license-ledger/download-requests
- [ ] /license-ledger/download-requests/:id

### ALLOTMENT MANAGEMENT (6)
- [ ] /allotments
- [ ] /allotments/create
- [ ] /allotments/:id/edit
- [ ] /allotments/:id/overview
- [ ] /allotments/:id/allocate (AllotmentAction)
- [ ] /allotments/:id/balance (redirects)

### BILL OF ENTRY (6)
- [ ] /bill-of-entries
- [ ] /bill-of-entries/create
- [ ] /bill-of-entries/:id/edit
- [ ] /bill-of-entries/:id/overview
- [ ] /bill-of-entries/:id/items (detail)

### TRADES (6)
- [ ] /trades
- [ ] /trades/create
- [ ] /trades/:id/edit
- [ ] /trades/:id/overview
- [ ] /trades/:id/items (detail)

### REPORTS (12)
- [ ] /reports/item-report
- [ ] /reports/item-pivot
- [ ] /reports/planned-report
- [ ] /reports/parle/sion-e1
- [ ] /reports/parle/sion-e2
- [ ] /reports/parle/sion-e5
- [ ] /reports/parle/sion-e132
- [ ] /reports/download-license
- [ ] /reports/license-purchase-profit
- [ ] /reports/expiring-licenses
- [ ] /reports/active-licenses
- [ ] /reports/sion-norm

### ADMIN ROUTES (5)
- [ ] /admin/users
- [ ] /admin/activity-log
- [ ] /admin/settings
- [ ] /admin/masters/:entity

### PLANNING (1)
- [ ] /planning

### MASTERS (2)
- [ ] /masters/company
- [ ] /masters/incentive-licenses

### RECONCILIATION (2)
- [ ] /reconciliation
- [ ] /reconciliation-issues

---

## FILTER VERIFICATION (CRITICAL)

For each filterable page, test:

1. **Initial State**
   - [ ] "Active Filters: 0" or hidden

2. **Apply Single Filter**
   - [ ] "Active Filters: 1" displays
   - [ ] Filter label shows (e.g., "Company: XYZ")
   - [ ] × button visible

3. **Remove Individual Filter**
   - [ ] Click × button
   - [ ] Filter count decreases
   - [ ] Results update
   - [ ] "Active Filters: 0" or hidden

4. **Apply Multiple Filters**
   - [ ] All filters display
   - [ ] "Active Filters: N" shows correct count
   - [ ] Each × button works independently

5. **Clear All**
   - [ ] Click "Clear All" or equivalent
   - [ ] All filters removed at once
   - [ ] "Active Filters: 0" or hidden

---

## ACCESSIBILITY VERIFICATION

For each page:
- [ ] Keyboard navigation works (Tab through all controls)
- [ ] Focus rings visible on all interactive elements
- [ ] Filter remove buttons have aria-labels
- [ ] Text contrast ≥4.5:1
- [ ] Icons have aria-labels or text alternatives
- [ ] Form labels associated with inputs
- [ ] Dialog/modal semantics correct
- [ ] Screen reader can identify all controls

---

## RESPONSIVE VERIFICATION

Test at these breakpoints:
- [ ] 1440 × 900 (Desktop)
- [ ] 1366 × 768 (Laptop)
- [ ] 1024 × 768 (iPad landscape)
- [ ] 768 × 1024 (iPad portrait)
- [ ] 390 × 844 (iPhone)

Verify for each:
- [ ] No horizontal overflow
- [ ] All controls visible and clickable
- [ ] Filters don't wrap awkwardly
- [ ] Tables don't overflow (use scroll if needed)
- [ ] Modals/dialogs fit on screen

---

## REGRESSION CHECKS

After filter or navigation changes:
- [ ] Dashboard still loads
- [ ] Login still works
- [ ] All master list pages work
- [ ] All reports load
- [ ] No 404 errors
- [ ] No API errors in console
- [ ] LocalStorage persists correctly
- [ ] Cached queries still work

---

## VISUAL VERIFICATION (Deep Slate Color System)

Verify consistent use of:
```
Background:      #0F172A (dark)
Sidebar:         #111827 (darker)
Surface:         #1E293B (lighter dark)
Border:          #334155

Primary Text:    #E2E8F0 (light)
Secondary Text:  #94A3B8 (muted light)
Muted Text:      #64748B (darker muted)

Accent:          #0EA5E9 (sky/primary)
```

Check:
- [ ] No bright neon colors
- [ ] No glassmorphism effects
- [ ] No excessive gradients
- [ ] No glowing shadows
- [ ] Professional enterprise look
- [ ] Consistent across all pages

---

## SIGN-OFF GATES

**Before marking complete:**
1. All 48 routes verified in browser
2. All filters work and display ActiveFilters
3. No console errors or warnings
4. Responsive at all 5 breakpoints
5. Accessibility keyboard nav works
6. Visual design consistent (Deep Slate)
7. No regressions from previous version

**Final approval:**
- [ ] Lead engineer review
- [ ] QA sign-off
- [ ] Production deployment approved
