# REMAINING ROUTES CHECKLIST - License Manager UI Rebrand
**Created**: 2026-09-25  
**Status**: READY FOR PHASE 3+ EXECUTION  
**Total Remaining Routes**: 48 (of 57 total)

---

## QUICK REFERENCE

### Routes Already Complete (9)
- ✅ `/dashboard`
- ✅ `/licenses` (+ create, edit)
- ✅ `/allotments` (+ create, edit)
- ✅ `/bill-of-entries` (+ create, edit)
- ✅ `/trades`
- ✅ `/incentive-licenses` (+ create, edit)
- ✅ `/reports/item-pivot`
- ✅ `/license-ledger`
- ✅ `/masters/:entity` (+ create, edit)

---

## PHASE 3: FORM PAGES (9 ROUTES)

### Critical: MasterForm.tsx - Serves 9 Routes
**File**: `frontend/src/pages/masters/MasterForm.tsx`  
**Status**: ⏹️ NOT STARTED  
**Effort**: 4-5 hours  
**Impact**: HIGH - Affects all entity CRUD operations  

**Routes Affected**:
- [ ] `/licenses/create` - Create License form
- [ ] `/licenses/:id/edit` - Edit License form
- [ ] `/allotments/create` - Create Allotment form
- [ ] `/allotments/:id/edit` - Edit Allotment form
- [ ] `/bill-of-entries/create` - Create BOE form
- [ ] `/bill-of-entries/:id/edit` - Edit BOE form
- [ ] `/incentive-licenses/create` - Create Incentive License form
- [ ] `/incentive-licenses/:id/edit` - Edit Incentive License form
- [ ] `/masters/:entity/create` - Create Master Data form
- [ ] `/masters/:entity/:id/edit` - Edit Master Data form

**Design System Changes Needed**:
- [ ] PageHeader component usage
- [ ] Button styling (primary, secondary, outline, ghost)
- [ ] Input field styling and dark mode
- [ ] Form layout and spacing
- [ ] Color system (backgrounds, borders, text)
- [ ] Typography hierarchy
- [ ] Responsive form layout
- [ ] Validation message styling

**Testing Checklist**:
- [ ] All form fields render correctly
- [ ] Buttons display with correct variants
- [ ] Dark mode contrast AA
- [ ] Mobile responsive (sm breakpoint)
- [ ] Form submission works
- [ ] Error messages styled correctly
- [ ] No console errors

**Quality Gates**:
- [ ] `npm run lint` passes
- [ ] `npm run typecheck` passes
- [ ] `npm run build` passes

---

### TradeForm.tsx - Serves 2 Routes
**File**: `frontend/src/pages/TradeForm.tsx`  
**Status**: ⏹️ NOT STARTED  
**Effort**: 1.5-2 hours  
**Impact**: MEDIUM - Trade CRUD operations  

**Routes Affected**:
- [ ] `/trades/create` - Create Trade form
- [ ] `/trades/:id/edit` - Edit Trade form

**Design System Changes Needed**:
- [ ] PageHeader component usage
- [ ] Button styling
- [ ] Input field styling
- [ ] Form layout
- [ ] Color system
- [ ] Typography

**Testing Checklist**:
- [ ] Form renders correctly
- [ ] All inputs styled consistently
- [ ] Dark mode works
- [ ] Mobile responsive
- [ ] No console errors

**Quality Gates**:
- [ ] `npm run lint` passes
- [ ] `npm run typecheck` passes
- [ ] `npm run build` passes

---

### AllotmentAction.tsx - Serves 1 Route
**File**: `frontend/src/pages/AllotmentAction.tsx`  
**Status**: ⏹️ NOT STARTED  
**Effort**: 1 hour  
**Impact**: LOW - Specialized allotment action page  

**Routes Affected**:
- [ ] `/allotments/:id/allocate` - Allocate allotment

**Design System Changes Needed**:
- [ ] PageHeader component
- [ ] Button styling
- [ ] Card styling
- [ ] Form styling

**Testing Checklist**:
- [ ] Page header renders correctly
- [ ] Allocation form displays properly
- [ ] Buttons styled correctly
- [ ] Dark mode works

**Quality Gates**:
- [ ] `npm run lint` passes
- [ ] `npm run typecheck` passes
- [ ] `npm run build` passes

---

## PHASE 4: REPORT PAGES (10 ROUTES)

### Batch 1: SION Reports (4 routes)
**Pattern**: All SION reports follow similar structure  
**Total Effort**: 1.5-2 hours  
**Impact**: MEDIUM  

#### SionE1.tsx
**File**: `frontend/src/pages/reports/SionE1.tsx`  
**Status**: ⏹️ NOT STARTED  
**Route**: `/reports/parle/sion-e1`
- [ ] PageHeader component
- [ ] Table styling
- [ ] Button styling
- [ ] Color system
- [ ] Responsive tables

#### SionE5.tsx
**File**: `frontend/src/pages/reports/SionE5.tsx`  
**Status**: ⏹️ NOT STARTED  
**Route**: `/reports/parle/sion-e5`
- [ ] PageHeader component
- [ ] Table styling
- [ ] Button styling
- [ ] Color system
- [ ] Responsive tables

#### SionE126.tsx
**File**: `frontend/src/pages/reports/SionE126.tsx`  
**Status**: ⏹️ NOT STARTED  
**Route**: `/reports/parle/sion-e126`
- [ ] PageHeader component
- [ ] Table styling
- [ ] Button styling
- [ ] Color system
- [ ] Responsive tables

#### SionE132.tsx
**File**: `frontend/src/pages/reports/SionE132.tsx`  
**Status**: ⏹️ NOT STARTED  
**Route**: `/reports/parle/sion-e132`
- [ ] PageHeader component
- [ ] Table styling
- [ ] Button styling
- [ ] Color system
- [ ] Responsive tables

---

### Batch 2: License Reports (3 routes)
**Pattern**: Similar to SION reports  
**Total Effort**: 1-1.5 hours  
**Impact**: MEDIUM  

#### ExpiringLicenses.tsx
**File**: `frontend/src/pages/reports/ExpiringLicenses.tsx`  
**Status**: ⏹️ NOT STARTED  
**Route**: `/reports/expiring-licenses`
- [ ] PageHeader component
- [ ] Table styling
- [ ] Filters styling
- [ ] Button styling

#### ActiveLicenses.tsx
**File**: `frontend/src/pages/reports/ActiveLicenses.tsx`  
**Status**: ⏹️ NOT STARTED  
**Route**: `/reports/active-licenses`
- [ ] PageHeader component
- [ ] Table styling
- [ ] Filters styling
- [ ] Button styling

#### DownloadLicense.tsx
**File**: `frontend/src/pages/reports/DownloadLicense.tsx`  
**Status**: ⏹️ NOT STARTED  
**Route**: `/reports/download-license`
- [ ] PageHeader component
- [ ] Form styling
- [ ] Button styling

---

### Batch 3: Business Reports (3 routes)
**Pattern**: Complex reports with multiple sections  
**Total Effort**: 1.5-2 hours  
**Impact**: MEDIUM  

#### ItemReport.tsx
**File**: `frontend/src/pages/reports/ItemReport.tsx`  
**Status**: ⏹️ NOT STARTED  
**Route**: `/reports/item-report`
- [ ] PageHeader component
- [ ] Table styling
- [ ] Filters styling
- [ ] Card styling

#### PlannedReport.tsx
**File**: `frontend/src/pages/reports/PlannedReport.tsx`  
**Status**: ⏹️ NOT STARTED  
**Route**: `/reports/planned-report`
- [ ] PageHeader component
- [ ] Table styling
- [ ] Filters styling
- [ ] Card styling

#### LicensePurchaseProfitReport.tsx
**File**: `frontend/src/pages/reports/LicensePurchaseProfitReport.tsx`  
**Status**: ⏹️ NOT STARTED  
**Route**: `/reports/license-purchase-profit`
- [ ] PageHeader component
- [ ] Table/Chart styling
- [ ] Filters styling
- [ ] Color system

---

## PHASE 5: DETAIL/OVERVIEW PAGES (5 ROUTES)

### LicenseOverviewPage.tsx - Serves 1 Route
**File**: `frontend/src/pages/license-overview/LicenseOverviewPage.tsx`  
**Status**: ⏹️ NOT STARTED  
**Effort**: 1.5-2 hours  
**Impact**: HIGH - Dashboard for license details  
**Complexity**: HIGH - Multiple sections, tabs, cards

**Routes Affected**:
- [ ] `/licenses/:id/overview` - License overview/dashboard

**Design System Changes Needed**:
- [ ] PageHeader component
- [ ] Card styling
- [ ] Tab styling
- [ ] Table styling
- [ ] Button styling
- [ ] Grid/layout system
- [ ] Color system

**Testing Checklist**:
- [ ] All sections render correctly
- [ ] Tabs switch properly
- [ ] Cards styled consistently
- [ ] Dark mode works
- [ ] Mobile responsive
- [ ] No console errors

**Quality Gates**:
- [ ] `npm run lint` passes
- [ ] `npm run typecheck` passes
- [ ] `npm run build` passes

---

### LicensePlanningWorkspace.tsx - Serves 1 Route
**File**: `frontend/src/pages/planning/LicensePlanningWorkspace.tsx`  
**Status**: ⏹️ NOT STARTED  
**Effort**: 1.5-2 hours  
**Impact**: MEDIUM - Planning interface  
**Complexity**: HIGH - Complex layout

**Routes Affected**:
- [ ] `/planning` - License planning workspace

**Design System Changes Needed**:
- [ ] PageHeader component
- [ ] Button styling
- [ ] Table styling
- [ ] Grid layout
- [ ] Color system
- [ ] Responsive design

**Testing Checklist**:
- [ ] Workspace loads correctly
- [ ] Planning interface functional
- [ ] Tables display properly
- [ ] Dark mode works
- [ ] Mobile responsive

**Quality Gates**:
- [ ] `npm run lint` passes
- [ ] `npm run typecheck` passes
- [ ] `npm run build` passes

---

### LicenseLedgerDetail.tsx - Serves 2 Routes
**File**: `frontend/src/pages/LicenseLedgerDetail.tsx`  
**Status**: ⏹️ NOT STARTED  
**Effort**: 1.5-2 hours  
**Impact**: MEDIUM - Ledger detail views  

**Routes Affected**:
- [ ] `/license-ledger/:licenseId` - License ledger detail
- [ ] `/license-ledger/:licenseId/:itemId` - License ledger item detail

**Design System Changes Needed**:
- [ ] PageHeader component
- [ ] Table styling
- [ ] Card styling
- [ ] Navigation/breadcrumbs
- [ ] Color system
- [ ] Responsive tables

**Testing Checklist**:
- [ ] Both route variants render correctly
- [ ] Tables display properly
- [ ] Dark mode works
- [ ] Mobile responsive (horizontal scroll for tables)
- [ ] No console errors

**Quality Gates**:
- [ ] `npm run lint` passes
- [ ] `npm run typecheck` passes
- [ ] `npm run build` passes

---

### BOETransferLetter.tsx - Serves 1 Route
**File**: `frontend/src/pages/BOETransferLetter.tsx`  
**Status**: ⏹️ NOT STARTED  
**Effort**: 1 hour  
**Impact**: LOW - Specialized letter generation page  

**Routes Affected**:
- [ ] `/bill-of-entries/:id/generate-transfer-letter` - BOE transfer letter

**Design System Changes Needed**:
- [ ] PageHeader component
- [ ] Form styling
- [ ] Preview styling
- [ ] Button styling
- [ ] Color system

**Testing Checklist**:
- [ ] Page header displays correctly
- [ ] Form renders properly
- [ ] Preview section styled correctly
- [ ] Print/export buttons work
- [ ] Dark mode works

**Quality Gates**:
- [ ] `npm run lint` passes
- [ ] `npm run typecheck` passes
- [ ] `npm run build` passes

---

## PHASE 6: LEDGER PAGES (6 ROUTES)

### LedgerUpload.tsx - Serves 1 Route
**File**: `frontend/src/pages/LedgerUpload.tsx`  
**Status**: ⏹️ NOT STARTED  
**Effort**: 1 hour  
**Impact**: MEDIUM - Data upload interface  

**Routes Affected**:
- [ ] `/ledger-upload` - Ledger file upload

**Design System Changes Needed**:
- [ ] PageHeader component
- [ ] Form styling
- [ ] Upload area styling
- [ ] Table styling
- [ ] Button styling

**Testing Checklist**:
- [ ] Upload interface displays correctly
- [ ] Form fields styled properly
- [ ] Dark mode works
- [ ] Mobile responsive

**Quality Gates**:
- [ ] `npm run lint` passes
- [ ] `npm run typecheck` passes
- [ ] `npm run build` passes

---

### LicenseDownloadRequests.tsx - Serves 1 Route
**File**: `frontend/src/pages/LicenseDownloadRequests.tsx`  
**Status**: ⏹️ NOT STARTED  
**Effort**: 1 hour  
**Impact**: MEDIUM - Request list page  

**Routes Affected**:
- [ ] `/license-ledger/download-requests` - Download requests list

**Design System Changes Needed**:
- [ ] PageHeader component
- [ ] Table styling
- [ ] Button styling
- [ ] Status badge styling
- [ ] Color system

**Testing Checklist**:
- [ ] Table displays correctly
- [ ] Status badges styled properly
- [ ] Buttons functional
- [ ] Dark mode works
- [ ] Mobile responsive

**Quality Gates**:
- [ ] `npm run lint` passes
- [ ] `npm run typecheck` passes
- [ ] `npm run build` passes

---

### LicenseDownloadRequestDetail.tsx - Serves 1 Route
**File**: `frontend/src/pages/LicenseDownloadRequestDetail.tsx`  
**Status**: ⏹️ NOT STARTED  
**Effort**: 1 hour  
**Impact**: MEDIUM - Request detail page  

**Routes Affected**:
- [ ] `/license-ledger/download-requests/:requestId` - Request detail

**Design System Changes Needed**:
- [ ] PageHeader component
- [ ] Card styling
- [ ] Details layout
- [ ] Button styling
- [ ] Status styling

**Testing Checklist**:
- [ ] Detail information displays correctly
- [ ] Cards styled properly
- [ ] Dark mode works
- [ ] Responsive layout

**Quality Gates**:
- [ ] `npm run lint` passes
- [ ] `npm run typecheck` passes
- [ ] `npm run build` passes

---

### LicenseLedgerPackageReadiness.tsx - Serves 1 Route
**File**: `frontend/src/pages/LicenseLedgerPackageReadiness.tsx`  
**Status**: ⏹️ NOT STARTED  
**Effort**: 1 hour  
**Impact**: LOW - Status tracking page  

**Routes Affected**:
- [ ] `/license-ledger/package-readiness/:jobId` - Package readiness status

**Design System Changes Needed**:
- [ ] PageHeader component
- [ ] Progress visualization styling
- [ ] Status display
- [ ] Table styling (if any)
- [ ] Button styling

**Testing Checklist**:
- [ ] Status display renders correctly
- [ ] Progress visualization styled properly
- [ ] Dark mode works
- [ ] Responsive layout

**Quality Gates**:
- [ ] `npm run lint` passes
- [ ] `npm run typecheck` passes
- [ ] `npm run build` passes

---

## PHASE 7: RECONCILIATION PAGES (2 ROUTES)

### ReconciliationPanel.tsx - Serves 1 Route
**File**: `frontend/src/pages/ReconciliationPanel.tsx`  
**Status**: ⏹️ NOT STARTED  
**Effort**: 1.5-2 hours  
**Impact**: MEDIUM - Complex reconciliation interface  
**Complexity**: HIGH - Multiple tabs, tables

**Routes Affected**:
- [ ] `/reconciliation` - Reconciliation panel

**Design System Changes Needed**:
- [ ] PageHeader component
- [ ] Tab styling
- [ ] Table styling
- [ ] Button styling
- [ ] Form styling
- [ ] Card styling
- [ ] Color system

**Testing Checklist**:
- [ ] All tabs display correctly
- [ ] Tables render properly
- [ ] Form inputs styled correctly
- [ ] Dark mode works
- [ ] Mobile responsive
- [ ] No console errors

**Quality Gates**:
- [ ] `npm run lint` passes
- [ ] `npm run typecheck` passes
- [ ] `npm run build` passes

---

### ReconciliationIssues.tsx - Serves 1 Route
**File**: `frontend/src/pages/ReconciliationIssues.tsx`  
**Status**: ⏹️ NOT STARTED  
**Effort**: 1 hour  
**Impact**: MEDIUM - Issue discovery page  

**Routes Affected**:
- [ ] `/reconciliation-issues` - Reconciliation issues list

**Design System Changes Needed**:
- [ ] PageHeader component
- [ ] Table styling
- [ ] Filter styling
- [ ] Badge styling
- [ ] Button styling

**Testing Checklist**:
- [ ] Table displays issues correctly
- [ ] Filters work properly
- [ ] Badges styled correctly
- [ ] Dark mode works
- [ ] Mobile responsive

**Quality Gates**:
- [ ] `npm run lint` passes
- [ ] `npm run typecheck` passes
- [ ] `npm run build` passes

---

## PHASE 8: ADMIN & USER PAGES (6 ROUTES)

### UserForm.tsx - Serves 2 Routes
**File**: `frontend/src/pages/admin/UserForm.tsx`  
**Status**: ⏹️ NOT STARTED  
**Effort**: 1 hour  
**Impact**: LOW - Superuser only  

**Routes Affected**:
- [ ] `/admin/users/create` - Create user form
- [ ] `/admin/users/:id/edit` - Edit user form

**Design System Changes Needed**:
- [ ] PageHeader component
- [ ] Form styling
- [ ] Input styling
- [ ] Button styling
- [ ] Card styling

**Testing Checklist**:
- [ ] Form fields render correctly
- [ ] All inputs styled properly
- [ ] Dark mode works
- [ ] Form submission functional

**Quality Gates**:
- [ ] `npm run lint` passes
- [ ] `npm run typecheck` passes
- [ ] `npm run build` passes

---

### UserList.tsx - Serves 1 Route
**File**: `frontend/src/pages/admin/UserList.tsx`  
**Status**: ⏹️ NOT STARTED  
**Effort**: 1 hour  
**Impact**: LOW - Superuser only  

**Routes Affected**:
- [ ] `/admin/users` - User list

**Design System Changes Needed**:
- [ ] PageHeader component
- [ ] Table styling
- [ ] Button styling
- [ ] Filter styling
- [ ] Color system

**Testing Checklist**:
- [ ] Table displays users correctly
- [ ] Buttons styled properly
- [ ] Dark mode works
- [ ] Mobile responsive

**Quality Gates**:
- [ ] `npm run lint` passes
- [ ] `npm run typecheck` passes
- [ ] `npm run build` passes

---

### ActivityLog.tsx - Serves 1 Route
**File**: `frontend/src/pages/admin/ActivityLog.tsx`  
**Status**: ⏹️ NOT STARTED  
**Effort**: 1 hour  
**Impact**: LOW - Superuser only  

**Routes Affected**:
- [ ] `/admin/activity-log` - Activity log

**Design System Changes Needed**:
- [ ] PageHeader component
- [ ] Table styling
- [ ] Filter styling
- [ ] Badge styling
- [ ] Button styling

**Testing Checklist**:
- [ ] Table displays activities correctly
- [ ] Timestamps format properly
- [ ] Filters work
- [ ] Dark mode works
- [ ] Mobile responsive

**Quality Gates**:
- [ ] `npm run lint` passes
- [ ] `npm run typecheck` passes
- [ ] `npm run build` passes

---

### Settings.tsx - Serves 1 Route
**File**: `frontend/src/pages/Settings.tsx`  
**Status**: ⏹️ NOT STARTED  
**Effort**: 1 hour  
**Impact**: LOW - Superuser only  

**Routes Affected**:
- [ ] `/settings` - Application settings

**Design System Changes Needed**:
- [ ] PageHeader component
- [ ] Form styling
- [ ] Input styling
- [ ] Toggle/switch styling
- [ ] Button styling
- [ ] Card styling

**Testing Checklist**:
- [ ] Form displays correctly
- [ ] All settings inputs styled properly
- [ ] Dark mode works
- [ ] Settings save correctly

**Quality Gates**:
- [ ] `npm run lint` passes
- [ ] `npm run typecheck` passes
- [ ] `npm run build` passes

---

### Profile.tsx - Serves 1 Route
**File**: `frontend/src/pages/Profile.tsx`  
**Status**: ⏹️ NOT STARTED  
**Effort**: 1 hour  
**Impact**: MEDIUM - All users  

**Routes Affected**:
- [ ] `/profile` - User profile

**Design System Changes Needed**:
- [ ] PageHeader component
- [ ] Avatar styling
- [ ] Form styling
- [ ] Input styling
- [ ] Button styling
- [ ] Card styling

**Testing Checklist**:
- [ ] Profile displays correctly
- [ ] Avatar renders properly
- [ ] Form fields styled correctly
- [ ] Dark mode works
- [ ] Form submission functional

**Quality Gates**:
- [ ] `npm run lint` passes
- [ ] `npm run typecheck` passes
- [ ] `npm run build` passes

---

## PHASE 9: MINIMAL PAGES (2 ROUTES)

### PDFViewer.tsx - Serves 1 Route
**File**: `frontend/src/pages/PDFViewer.tsx`  
**Status**: ⏹️ NOT STARTED  
**Effort**: 30 min  
**Impact**: LOW - Rarely used  

**Routes Affected**:
- [ ] `/pdf-viewer` - PDF viewer

**Design System Changes Needed**:
- [ ] Minimal styling updates
- [ ] Color system for controls

**Testing Checklist**:
- [ ] PDF viewer loads correctly
- [ ] Controls styled properly
- [ ] Dark mode works

**Quality Gates**:
- [ ] `npm run lint` passes
- [ ] `npm run typecheck` passes
- [ ] `npm run build` passes

---

### NotFound.tsx - Serves 1 Route
**File**: `frontend/src/pages/errors/NotFound.tsx`  
**Status**: ⏹️ NOT STARTED  
**Effort**: 30 min  
**Impact**: LOW - Error page  

**Routes Affected**:
- [ ] `*` (404) - Not found error

**Design System Changes Needed**:
- [ ] PageHeader component (optional)
- [ ] Text styling
- [ ] Button styling
- [ ] Color system

**Testing Checklist**:
- [ ] Error page displays correctly
- [ ] Button styled properly
- [ ] Dark mode works

**Quality Gates**:
- [ ] `npm run lint` passes
- [ ] `npm run typecheck` passes
- [ ] `npm run build` passes

---

## ADDITIONAL WORK: TABLE & EMPTYSTATE (PARALLEL TO MAIN PHASES)

### DataTable.tsx - Affects 15+ Pages
**File**: `frontend/src/components/DataTable.tsx`  
**Status**: ⏹️ NOT STARTED  
**Effort**: 5 min  
**Impact**: HIGH - Standardizes empty states  

**Changes**:
- [ ] Replace inline empty state with EmptyState component

**Testing**:
- [ ] Empty states display correctly
- [ ] Dark mode works
- [ ] No visual regression

---

### AllotmentsTable.tsx
**File**: TBD  
**Status**: ⏹️ NOT STARTED  
**Effort**: 5 min  

---

### IncentiveLicensesTable.tsx
**File**: TBD  
**Status**: ⏹️ NOT STARTED  
**Effort**: 5 min  

---

### AccordionTable.tsx
**File**: TBD  
**Status**: ⏹️ NOT STARTED  
**Effort**: 5 min  

---

## SUMMARY BY PHASE

| Phase | Component | Routes | Effort | Priority | Status |
|-------|-----------|--------|--------|----------|--------|
| 1 | Various (Dashboard, MasterList, Reports) | 9 | 45 min | CRITICAL | ✅ DONE |
| 3 | MasterForm | 9 | 4-5 hr | HIGH | ⏹️ QUEUED |
| 3 | TradeForm | 2 | 1.5-2 hr | HIGH | ⏹️ QUEUED |
| 3 | AllotmentAction | 1 | 1 hr | HIGH | ⏹️ QUEUED |
| 4 | SION Reports | 4 | 1.5-2 hr | HIGH | ⏹️ QUEUED |
| 4 | License Reports | 3 | 1-1.5 hr | HIGH | ⏹️ QUEUED |
| 4 | Business Reports | 3 | 1.5-2 hr | HIGH | ⏹️ QUEUED |
| 5 | LicenseOverviewPage | 1 | 1.5-2 hr | HIGH | ⏹️ QUEUED |
| 5 | LicensePlanningWorkspace | 1 | 1.5-2 hr | HIGH | ⏹️ QUEUED |
| 5 | LicenseLedgerDetail | 2 | 1.5-2 hr | HIGH | ⏹️ QUEUED |
| 5 | BOETransferLetter | 1 | 1 hr | HIGH | ⏹️ QUEUED |
| 6 | LedgerUpload | 1 | 1 hr | HIGH | ⏹️ QUEUED |
| 6 | LicenseDownloadRequests | 1 | 1 hr | HIGH | ⏹️ QUEUED |
| 6 | LicenseDownloadRequestDetail | 1 | 1 hr | HIGH | ⏹️ QUEUED |
| 6 | LicenseLedgerPackageReadiness | 1 | 1 hr | HIGH | ⏹️ QUEUED |
| 7 | ReconciliationPanel | 1 | 1.5-2 hr | MEDIUM | ⏹️ QUEUED |
| 7 | ReconciliationIssues | 1 | 1 hr | MEDIUM | ⏹️ QUEUED |
| 8 | UserForm | 2 | 1 hr | LOW | ⏹️ QUEUED |
| 8 | UserList | 1 | 1 hr | LOW | ⏹️ QUEUED |
| 8 | ActivityLog | 1 | 1 hr | LOW | ⏹️ QUEUED |
| 8 | Settings | 1 | 1 hr | LOW | ⏹️ QUEUED |
| 8 | Profile | 1 | 1 hr | MEDIUM | ⏹️ QUEUED |
| 9 | PDFViewer | 1 | 30 min | LOW | ⏹️ QUEUED |
| 9 | NotFound | 1 | 30 min | LOW | ⏹️ QUEUED |
| Parallel | Table/EmptyState | - | 30 min | HIGH | ⏹️ QUEUED |

---

## TRACKING PROGRESS

### Completed Routes (Mark with ✅ when done)
```
✅ Dashboard
✅ Licenses (+ create, edit)
✅ Allotments (+ create, edit)
✅ Bill of Entries (+ create, edit)
✅ Trades
✅ Incentive Licenses (+ create, edit)
✅ Reports/Item Pivot
✅ License Ledger
✅ Masters (+ create, edit)
```

### In Progress (Mark with 🔄 when started)
```
[  ] Licenses/Create
[  ] Licenses/Edit
[  ] Form Pages
[  ] Report Pages
... (add as you progress)
```

### Not Started (Mark with ⏹️)
```
[  ] MasterForm
[  ] TradeForm
[  ] AllotmentAction
[  ] SionE1 - SionE132 Reports
[  ] ExpiringLicenses, etc.
... (all remaining pages)
```

---

## NEXT STEPS

1. **Start Phase 3**: Begin with `MasterForm.tsx` 
   - Highest impact (9 routes)
   - High priority
   - Well-defined pattern

2. **Parallel Work**: While waiting for form pages, start on:
   - Table/EmptyState standardization
   - Report pages batch migration

3. **Daily Check-ins**:
   - Update this checklist with progress
   - Run quality gates after each component
   - Track time spent per phase

4. **Keep Dashboard**: Reference implementation
   - Review PageHeader usage
   - Review button styling
   - Review color system usage

---

**Last Updated**: 2026-09-25  
**Ready For**: Phase 3+ Execution  
**Expected Completion**: 18-24 hours (distributed)

Mark routes as complete with ✅ and date.
