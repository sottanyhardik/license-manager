# Route Migration Queue - UI Consistency Hotfix

**Mission**: Migrate all pages in the License Manager frontend to use consistent PageHeader component and unified UI patterns for buttons, filters, cards, and tables.

**Status**: Initiating Phase 1 - Complete Route Inventory

---

## PHASE 1: Complete Route Inventory

### All Detected Routes (Total: 34 distinct routes)

#### Core Routes (AppRoutes.tsx)

| Route Path | Component | File | Priority | Status | UI Issues |
|---|---|---|---|---|---|
| `/login` | Login | pages/Login.tsx | N/A | ✓ | Public page |
| `/forgot-password` | PasswordReset | pages/auth/PasswordReset.tsx | N/A | ✓ | Public page |
| `/dashboard` | Dashboard | pages/Dashboard.tsx | **P0** | ✓ DONE | Uses PageHeader ✓ |
| `/licenses` | MasterList (licenses) | pages/masters/MasterList.tsx | **P0** | ⚠️ NEEDS FIX | Raw page-header div, inconsistent button styling |
| `/licenses/create` | MasterForm | pages/masters/MasterForm.tsx | P1 | ⚠️ NEEDS FIX | Header consistency |
| `/licenses/:id/edit` | MasterForm | pages/masters/MasterForm.tsx | P1 | ⚠️ NEEDS FIX | Header consistency |
| `/licenses/:id/overview` | LicenseOverviewPage | pages/license-overview/LicenseOverviewPage.tsx | P1 | ⚠️ NEEDS FIX | Header structure |
| `/licenses/:id/balance` | RedirectToLicenseOverview | N/A | N/A | ✓ | Redirect, no UI work |
| `/planning` | LicensePlanningWorkspace | pages/planning/LicensePlanningWorkspace.tsx | P1 | ⚠️ NEEDS FIX | Complex header/layout |
| `/allotments` | MasterList (allotments) | pages/masters/MasterList.tsx | **P0** | ⚠️ NEEDS FIX | Raw page-header div, card layout |
| `/allotments/create` | MasterForm | pages/masters/MasterForm.tsx | P1 | ⚠️ NEEDS FIX | Header consistency |
| `/allotments/:id/edit` | MasterForm | pages/masters/MasterForm.tsx | P1 | ⚠️ NEEDS FIX | Header consistency |
| `/allotments/:id/allocate` | AllotmentAction | pages/AllotmentAction.tsx | P1 | ⚠️ NEEDS FIX | Header/form styling |
| `/reports/parle/sion-e1` | SionE1 | pages/reports/SionE1.tsx | P1 | ⚠️ NEEDS FIX | Report header inconsistency |
| `/reports/parle/sion-e5` | SionE5 | pages/reports/SionE5.tsx | P1 | ⚠️ NEEDS FIX | Report header inconsistency |
| `/reports/parle/sion-e126` | SionE126 | pages/reports/SionE126.tsx | P1 | ⚠️ NEEDS FIX | Report header inconsistency |
| `/reports/parle/sion-e132` | SionE132 | pages/reports/SionE132.tsx | P1 | ⚠️ NEEDS FIX | Report header inconsistency |
| `/reports/expiring-licenses` | ExpiringLicenses | pages/reports/ExpiringLicenses.tsx | P1 | ⚠️ NEEDS FIX | Report header inconsistency |
| `/reports/active-licenses` | ActiveLicenses | pages/reports/ActiveLicenses.tsx | P1 | ⚠️ NEEDS FIX | Report header inconsistency |
| `/reports/download-license` | DownloadLicense | pages/reports/DownloadLicense.tsx | P1 | ⚠️ NEEDS FIX | Report header inconsistency |
| `/reports/item-pivot` | ItemPivotReport | pages/reports/ItemPivotReport.tsx | **P0** | ⚠️ CRITICAL | Raw page-header div, sticky header issues, filter panel styling |
| `/reports/item-report` | ItemReport | pages/reports/ItemReport.tsx | P1 | ⚠️ NEEDS FIX | Report header inconsistency |
| `/reports/planned-report` | PlannedReport | pages/reports/PlannedReport.tsx | P1 | ⚠️ NEEDS FIX | Report header inconsistency |
| `/reports/license-purchase-profit` | LicensePurchaseProfitReport | pages/reports/LicensePurchaseProfitReport.tsx | P1 | ⚠️ NEEDS FIX | Report header inconsistency |
| `/bill-of-entries` | MasterList (bill-of-entries) | pages/masters/MasterList.tsx | **P0** | ⚠️ NEEDS FIX | Raw page-header div, entity card styling |
| `/bill-of-entries/create` | MasterForm | pages/masters/MasterForm.tsx | P1 | ⚠️ NEEDS FIX | Header consistency |
| `/bill-of-entries/:id/edit` | MasterForm | pages/masters/MasterForm.tsx | P1 | ⚠️ NEEDS FIX | Header consistency |
| `/bill-of-entries/:id/generate-transfer-letter` | BOETransferLetter | pages/BOETransferLetter.tsx | P1 | ⚠️ NEEDS FIX | Header consistency |
| `/trades` | MasterList (trades) | pages/masters/MasterList.tsx | P1 | ⚠️ NEEDS FIX | Raw page-header div, trades list view |
| `/trades/create` | TradeForm | pages/TradeForm.tsx | P1 | ⚠️ NEEDS FIX | Form header styling |
| `/trades/:id/edit` | TradeForm | pages/TradeForm.tsx | P1 | ⚠️ NEEDS FIX | Form header styling |
| `/reconciliation` | ReconciliationPanel | pages/ReconciliationPanel.tsx | P1 | ⚠️ NEEDS FIX | Complex header/tabs |
| `/reconciliation-issues` | ReconciliationIssues | pages/ReconciliationIssues.tsx | P1 | ⚠️ NEEDS FIX | Header consistency |
| `/incentive-licenses` | MasterList (incentive-licenses) | pages/masters/MasterList.tsx | **P0** | ⚠️ NEEDS FIX | Raw page-header div, empty state height issue |
| `/incentive-licenses/create` | MasterForm | pages/masters/MasterForm.tsx | P1 | ⚠️ NEEDS FIX | Header consistency |
| `/incentive-licenses/:id/edit` | MasterForm | pages/masters/MasterForm.tsx | P1 | ⚠️ NEEDS FIX | Header consistency |
| `/ledger-upload` | LedgerUpload | pages/LedgerUpload.tsx | P1 | ⚠️ NEEDS FIX | Header consistency |
| `/license-ledger` | LicenseLedger | pages/LicenseLedger.tsx | **P1** | ⚠️ NEEDS FIX | Raw page-header, table styling, responsive issues |
| `/license-ledger/download-requests` | LicenseDownloadRequests | pages/LicenseDownloadRequests.tsx | P1 | ⚠️ NEEDS FIX | Header consistency |
| `/license-ledger/download-requests/:requestId` | LicenseDownloadRequestDetail | pages/LicenseDownloadRequestDetail.tsx | P1 | ⚠️ NEEDS FIX | Header consistency |
| `/license-ledger/package-readiness/:jobId` | LicenseLedgerPackageReadiness | pages/LicenseLedgerPackageReadiness.tsx | P1 | ⚠️ NEEDS FIX | Header consistency |
| `/license-ledger/:licenseId` | LicenseLedgerDetail | pages/LicenseLedgerDetail.tsx | P1 | ⚠️ NEEDS FIX | Header consistency, tables, responsive |
| `/license-ledger/:licenseId/:itemId` | LicenseLedgerDetail | pages/LicenseLedgerDetail.tsx | P1 | ⚠️ NEEDS FIX | Header consistency, tables, responsive |
| `/pdf-viewer` | PDFViewer | pages/PDFViewer.tsx | P2 | ⚠️ | Minimal UI, low priority |
| `/settings` | Settings | pages/Settings.tsx | P2 | ⚠️ NEEDS FIX | Superuser page, header consistency |
| `/profile` | Profile | pages/Profile.tsx | P2 | ⚠️ NEEDS FIX | User profile, header consistency |
| `/masters/:entity` | MasterList | pages/masters/MasterList.tsx | P1 | ⚠️ NEEDS FIX | Raw page-header div |
| `/masters/:entity/create` | MasterForm | pages/masters/MasterForm.tsx | P1 | ⚠️ NEEDS FIX | Header consistency |
| `/masters/:entity/:id/edit` | MasterForm | pages/masters/MasterForm.tsx | P1 | ⚠️ NEEDS FIX | Header consistency |
| `/admin/users` | UserList | pages/admin/UserList.tsx | P2 | ⚠️ NEEDS FIX | Admin page, header consistency |
| `/admin/users/create` | UserForm | pages/admin/UserForm.tsx | P2 | ⚠️ NEEDS FIX | Admin form, header consistency |
| `/admin/users/:id/edit` | UserForm | pages/admin/UserForm.tsx | P2 | ⚠️ NEEDS FIX | Admin form, header consistency |
| `/admin/activity-log` | ActivityLog | pages/admin/ActivityLog.tsx | P2 | ⚠️ NEEDS FIX | Admin page, header consistency |

---

## PHASE 2: High-Priority Pages (Execute First)

### GROUP A: Pages that render `page-header` raw divs (CRITICAL FIX)

These pages use the old Tabler-style `page-header` div structure instead of the `PageHeader` component. They need immediate migration:

#### 1. Dashboard (Already Fixed ✓)
- **Path**: `/dashboard`
- **Component**: `Dashboard.tsx`
- **Status**: ✓ Already uses `PageHeader` component
- **Notes**: Best practice example

#### 2. Licenses Page (MasterList)
- **Path**: `/licenses`
- **Component**: `MasterList.tsx`
- **Current Status**: Raw `page-header` div (line 807)
- **Issues**:
  - Uses raw div with `page-pretitle`, `page-actions` CSS classes
  - Header not responsive at mobile breakpoints
  - Button styling inconsistent with Dashboard
  - Export/PDF buttons not using unified button variants
- **Estimated Complexity**: Medium
- **Migration Steps**:
  1. Replace raw `page-header` div with `PageHeader` component
  2. Standardize button variants (outline, primary, ghost)
  3. Move actions into `actions` prop
  4. Test responsive behavior
  5. Verify filter panel alignment

#### 3. Incentive Licenses Page
- **Path**: `/incentive-licenses`
- **Component**: `MasterList.tsx` (same component)
- **Current Status**: Raw `page-header` div
- **Issues**:
  - Same as Licenses
  - Empty state has spacing issues (mentioned in brief)
- **Estimated Complexity**: Medium
- **Migration Steps**:
  1. Apply same PageHeader migration as Licenses
  2. Fix empty state height/spacing
  3. Test card layout responsiveness

#### 4. Item Pivot Report (MOST CRITICAL)
- **Path**: `/reports/item-pivot`
- **Component**: `ItemPivotReport.tsx`
- **Current Status**: Raw `page-header` div with sticky positioning (line 583)
- **Issues**:
  - Raw page-header div with custom sticky styling
  - Responsive button wrapping issues (see lines 625-647)
  - Filter panel button inconsistency
  - Page-actions uses `flex flex-col gap-2 sm:flex-row` workaround
  - Sticky header backdrop blur styling is fragile
  - Inline style overrides for button spacing
- **Estimated Complexity**: High (complex sticky header + responsive actions)
- **Migration Steps**:
  1. Replace raw page-header with PageHeader component
  2. Use PageHeader's built-in sticky positioning
  3. Simplify button action layout
  4. Migrate filter panel toggle button
  5. Test horizontal scroll + sticky header interaction
  6. Verify filter collapse/expand UX at mobile

#### 5. License Ledger Page
- **Path**: `/license-ledger`
- **Component**: `LicenseLedger.tsx`
- **Current Status**: Raw `page-header` div
- **Issues**:
  - Header consistency
  - Table styling
  - Responsive table overflow
- **Estimated Complexity**: Medium
- **Migration Steps**:
  1. Replace with PageHeader component
  2. Verify table card styling
  3. Test responsive overflow

### GROUP B: Report Pages (SionE1/E5/E126/E132, ExpiringLicenses, ActiveLicenses, etc)

#### 6. SionE1, SionE5, SionE126, SionE132 Reports
- **Paths**: `/reports/parle/sion-e1`, etc.
- **Components**: `SionE1.tsx`, `SionE5.tsx`, etc.
- **Current Status**: Likely raw page-header divs (common pattern)
- **Estimated Complexity**: Low (similar pattern)
- **Batch Migration**: Can be done together

#### 7. ExpiringLicenses, ActiveLicenses Reports
- **Paths**: `/reports/expiring-licenses`, `/reports/active-licenses`
- **Estimated Complexity**: Low
- **Batch Migration**: Can be done together

#### 8. ItemReport
- **Path**: `/reports/item-report`
- **Component**: `ItemReport.tsx`
- **Estimated Complexity**: Medium

#### 9. PlannedReport
- **Path**: `/reports/planned-report`
- **Estimated Complexity**: Medium

#### 10. LicensePurchaseProfitReport
- **Path**: `/reports/license-purchase-profit`
- **Estimated Complexity**: Medium

---

## PHASE 3: Form Pages (MasterForm, TradeForm)

### 11. MasterForm (Create/Edit all entities)
- **Paths**: `/licenses/create`, `/licenses/:id/edit`, `/allotments/create`, etc.
- **Component**: `MasterForm.tsx`
- **Current Status**: Likely inconsistent with new PageHeader pattern
- **Estimated Complexity**: High (large complex form)
- **Notes**: Shared component for all CRUD operations

### 12. TradeForm
- **Path**: `/trades/create`, `/trades/:id/edit`
- **Component**: `TradeForm.tsx`
- **Estimated Complexity**: Medium-High

---

## PHASE 4: Collection Pages (MasterList variants)

### 13. Bill of Entries List
- **Path**: `/bill-of-entries`
- **Component**: `MasterList.tsx`
- **Current Status**: Raw page-header + EntityCard layout
- **Estimated Complexity**: High (complex entity card layout)
- **Special Issues**: Entity cards with inline edit, dispute handling

### 14. Trades List
- **Path**: `/trades`
- **Component**: `MasterList.tsx`
- **Current Status**: Raw page-header + TradesListView
- **Estimated Complexity**: Medium-High (linked trades presentation)

### 15. Allotments List
- **Path**: `/allotments`
- **Component**: `MasterList.tsx`
- **Current Status**: Raw page-header + AllotmentsTable
- **Estimated Complexity**: Medium

---

## PHASE 5: Detail/Overview Pages

### 16. License Overview Page
- **Path**: `/licenses/:id/overview`
- **Component**: `LicenseOverviewPage.tsx`
- **Estimated Complexity**: High (many sub-sections, tabs)

### 17. License Ledger Detail
- **Path**: `/license-ledger/:licenseId`
- **Component**: `LicenseLedgerDetail.tsx`
- **Estimated Complexity**: High (detailed ledger tables)

### 18. License Planning Workspace
- **Path**: `/planning`
- **Component**: `LicensePlanningWorkspace.tsx`
- **Estimated Complexity**: High (complex planning interface)

---

## PHASE 6: Reconciliation Pages

### 19. ReconciliationPanel
- **Path**: `/reconciliation`
- **Component**: `ReconciliationPanel.tsx`
- **Estimated Complexity**: High (multiple tabs, complex data)

### 20. ReconciliationIssues
- **Path**: `/reconciliation-issues`
- **Component**: `ReconciliationIssues.tsx`
- **Estimated Complexity**: Medium

---

## PHASE 7: Supporting Pages

### 21. LedgerUpload
### 22. LicenseDownloadRequests
### 23. LicenseDownloadRequestDetail
### 24. LicenseLedgerPackageReadiness
### 25. BOETransferLetter
### 26. AllotmentAction
### 27. Settings (Superuser)
### 28. Profile
### 29. Admin/UserList
### 30. Admin/UserForm
### 31. Admin/ActivityLog

---

## PHASE 8: Master Data Pages

### 32-51. Master CRUD Pages
- **Paths**: `/masters/:entity`, `/masters/:entity/create`, `/masters/:entity/:id/edit`
- **Component**: `MasterList.tsx`, `MasterForm.tsx`
- **Estimated Complexity**: Medium (generic pattern)

---

## Execution Priority

### PRIORITY 1 (Execute Now - Week 1)
1. ✓ Dashboard (already done)
2. Licenses Page (MasterList)
3. Item Pivot Report (most complex)
4. Incentive Licenses
5. License Ledger

**Estimated Time**: 2-3 hours

### PRIORITY 2 (Week 1 - Final)
6. Bill of Entries
7. Trades List
8. Allotments
9. All Report Pages (batch migration)

**Estimated Time**: 2-3 hours

### PRIORITY 3 (Week 2)
10. MasterForm
11. TradeForm
12. All detail/overview pages
13. Reconciliation pages

**Estimated Time**: 4-6 hours

### PRIORITY 4 (Week 2 - Final)
14. Supporting pages
15. Admin pages
16. Master data pages

**Estimated Time**: 2-3 hours

---

## UI/UX Consistency Checklist

For each page migration, verify:

- [ ] Header uses `PageHeader` component (no raw divs)
- [ ] Breadcrumb pretitle is consistent
- [ ] Main title is H1, properly sized
- [ ] Description/subtitle is rendered correctly
- [ ] Action buttons use standard variants (outline, primary, secondary, ghost)
- [ ] Button sizes are consistent (sm, md)
- [ ] Button icons use lucide-react only
- [ ] Filter panel uses FilterPanel component (if applicable)
- [ ] Cards use `Card` component from shadcn/ui
- [ ] Tables use consistent styling
- [ ] Empty states are consistent
- [ ] Loading states show spinners
- [ ] Responsive behavior works at mobile (sm), tablet (md), desktop (lg)
- [ ] Dark mode contrast is good (AA minimum)
- [ ] No hardcoded colors (use Tailwind + theme tokens)
- [ ] Spacing follows grid (8px base unit)
- [ ] Typography hierarchy is maintained

---

## Known Component Patterns

### PageHeader Component
**File**: `frontend/src/components/PageHeader.tsx`
**Usage**:
```tsx
<PageHeader 
  pretitle="Home" 
  title="Dashboard" 
  description="Your description here"
  actions={<div>...</div>}
/>
```

### Card Component
**From**: `@/components/ui/card`
**Usage**:
```tsx
<Card>
  <CardHeader className="border-b">...</CardHeader>
  <CardContent>...</CardContent>
</Card>
```

### Button Component
**From**: `@/components/ui/button`
**Variants**: outline, primary, secondary, ghost, destructive
**Sizes**: sm, md, lg

### AdvancedFilter Component
**File**: `frontend/src/components/AdvancedFilter.tsx`
**Used by**: MasterList for filtering

---

## Progress Tracking

- [ ] Phase 1: Complete Route Inventory (START HERE)
- [ ] Phase 2: High-Priority Pages Migrated
- [ ] Phase 3: Form Pages Migrated
- [ ] Phase 4: Collection Pages Migrated
- [ ] Phase 5: Detail Pages Migrated
- [ ] Phase 6: Reconciliation Pages Migrated
- [ ] Phase 7: Supporting Pages Migrated
- [ ] Phase 8: Master Data Pages Migrated
- [ ] Final: All quality gates passing (lint, typecheck, build)
- [ ] All pages visually consistent
- [ ] Responsive tests passing
- [ ] Dark mode tests passing

---

## Notes

- **MasterList.tsx is heavily reused**: It renders 6 different entity types (licenses, allotments, bill-of-entries, trades, incentive-licenses, masters/:entity). Fixing it once fixes many pages.
- **ItemPivotReport is complex**: Sticky header + horizontal scroll + responsive actions = high risk. Test thoroughly.
- **Reports can be batch-migrated**: They follow similar patterns.
- **Forms may need special attention**: MasterForm is large and complex; coordinate changes carefully.

---

**Created**: 2026-09-25
**Phase**: 1 Complete
**Next**: Execute Phase 2 High-Priority Fixes
