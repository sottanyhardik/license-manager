# Filter Discovery Document

**Generated:** 2026-09-25  
**Purpose:** Document every filter implementation across the License Manager

## Discovered Filter Implementations

### 1. MasterList (Generic CRUD pages)

**Routes:** `/licenses`, `/allotments`, `/bill-of-entries`, `/trades`, `/incentive-licenses`, `/masters/:entity`

**Component:** `frontend/src/pages/masters/MasterList.tsx`

**Filter Component:** `AdvancedFilter`

**Filters Implemented:**
- Search (text input, icontains)
- Date range filters (varies by entity)
- Status filters (varies by entity)
- FK relationship filters
- Choice/select filters
- Exclude filters
- Button group filters
- Range filters

**Active Filters Display:** MISSING ❌

**Notes:**
- Uses `filterPersistence` to save/restore filter state
- Dynamic filter configuration per entity
- Pagination (default 25 per page)

---

### 2. LicenseLedger

**Route:** `/license-ledger`

**Component:** `frontend/src/pages/LicenseLedger.tsx`

**Filters Implemented:**
- Company (AsyncSelectField)
- Min Balance (number input)
- License Type (DFIA, RODTEP, ROSTL, MEIS, etc.)
- Norm (AsyncSelectField, DFIA only)
- Purchase Status (AsyncSelectField, DFIA only)
- Sort (Latest/Oldest/High Balance/Low Balance)
- Search (license number, exporter)
- Active Only (toggle switch)
- Include License Numbers (text)
- Exclude License Numbers (text)
- Purchase Bill Status (button group)
- Purchase Date Range (date picker)

**Active Filters Display:** MISSING ❌

**Notes:**
- Complex filter logic with conditional requirements (DFIA-only filters)
- Multiple filter UI patterns (select, input, toggle, button group, date range)
- Summary cards that update based on filters
- Export functionality affected by filters

---

### 3. UserList

**Route:** `/admin/users`

**Component:** `frontend/src/pages/admin/UserList.tsx`

**Filters Implemented:**
- Search (text input: username, email)
- Role (Select dropdown)
- is_active (Select dropdown: All/Active/Inactive)

**Active Filters Display:** MISSING ❌

**Notes:**
- Uses `useSmoothListFilters` hook
- Immediate filter application
- Summary cards (Total Users, Active, Superusers)

---

### 4. ActivityLog

**Route:** `/admin/activity-log`

**Component:** `frontend/src/pages/admin/ActivityLog.tsx`

**Filters Implemented:**
- Username (text input, superuser only)
- Action (Select dropdown)
- Search (text input: IP, description)
- Module (text input)
- Date Range (date picker)
- Limit (select: 200, 500, etc.)

**Active Filters Display:** MISSING ❌

**Notes:**
- Uses `useSmoothListFilters` hook
- Mixed debounced and immediate filters
- Abort controller for request cleanup
- Refresh button to manual refresh

---

### 5. ItemReport

**Route:** `/reports/item-report`

**Component:** `frontend/src/pages/reports/ItemReport.tsx`

**Filter Component:** `frontend/src/pages/reports/itemReport/ItemReportFilters.tsx`

**Filters Implemented:**
- Min Balance (CIF) - Select: 100, 200, 500, 1000, 5000, 10000
- Min Available Qty - Select: 0, 100, 500, 1000, 5000, 10000
- License Status - Select: Active/Expiring Soon/Expired/All
- Expiry Date Range - Date picker
- Include Companies - MultiSelect (AsyncSelectField)
- Exclude Companies - MultiSelect (AsyncSelectField)
- Is Restricted - Select: All/Restricted/Not Restricted
- Purchase Status - MultiSelect (ReactSelect)
- Norms - MultiSelect (ReactSelect)
- Notification - MultiSelect (ReactSelect)
- Product Description - Text input (full-width)
- HSN Code - Text input (full-width)
- Item Names - MultiSelect (ReactSelect, with portal menu)

**Active Filters Display:** YES ✓ (Inline chips/badges)

**Display Implementation:**
- Shows counts for multi-select filters
- Shows human-readable values for text filters
- Shows date ranges when set
- Located at bottom of filter panel (lines 347-368)
- Issues: Shows counts, not individual items; No individual remove buttons

---

### 6. PlannedReport

**Route:** `/reports/planned-report`

**Component:** `frontend/src/pages/reports/PlannedReport.tsx`

**Filter Component:** `frontend/src/pages/reports/itemReport/ItemReportFilters.tsx` (shared)

**Filters:** Same as ItemReport (12 filters)

**Active Filters Display:** YES ✓ (Inline, same as ItemReport)

---

### 7. ItemPivotReport

**Route:** `/reports/item-pivot`

**Component:** `frontend/src/pages/reports/ItemPivotReport.tsx`

**Filter Component:** `frontend/src/pages/reports/ItemPivotFilters.tsx`

**Filters Implemented:**
- Selected Companies - MultiSelect
- Exclude Companies - MultiSelect
- Min Balance - number
- License Status - Select
- Expiry Date From - Date picker
- Expiry Date To - Date picker
- Purchase Status - MultiSelect
- Min Qty - number (implied from component)

**Active Filters Display:** PARTIAL ✓ (Badge saying "Active")

**Display Implementation:**
- Shows Badge with "Active" text (not count or details)
- Shows conditionally when filters active
- Missing: Details of which filters are active

---

### 8. ItemPivotFilters

**Component:** `frontend/src/pages/reports/ItemPivotFilters.tsx`

**Notes:**
- Tests reference `hasActiveFilters` property
- Accepts `handleClearFilters` callback
- Used by ItemPivotReport

---

### 9. AllotmentFilters (AllotmentAction page)

**Route:** `/allotments/:id/allocate`

**Component:** `frontend/src/pages/AllotmentAction.tsx`

**Filter Component:** `frontend/src/pages/AllotmentFilters.tsx`

**Filters Implemented:**
- Item ID - AsyncSelect (dynamic based on plan mode)
- Purchase Status - MultiSelect (ReactSelect)
- Plan Mode toggle switch

**Active Filters Display:** MISSING ❌

**Notes:**
- Context-aware filters (changes for planning mode vs actual mode)
- Uses custom ReactSelect implementation

---

### 10. LicenseLedgerDetail

**Route:** `/license-ledger/:licenseId` or `/license-ledger/:licenseId/:itemId`

**Component:** `frontend/src/pages/LicenseLedgerDetail.tsx`

**Filters:** Likely has transaction/item filters (TBD - need to verify)

**Active Filters Display:** TBD

---

### 11. LicenseOverviewPage

**Route:** `/licenses/:id/overview`

**Component:** `frontend/src/pages/license-overview/LicenseOverviewPage.tsx`

**Filters:** Likely has tab-based filters and embedded table filters (TBD - need to verify)

**Active Filters Display:** TBD

---

### 12. LicensePlanningWorkspace

**Route:** `/planning`

**Component:** `frontend/src/pages/planning/LicensePlanningWorkspace.tsx`

**Filters Implemented:**
- Norm Search - Text input

**Active Filters Display:** MISSING ❌

**Notes:**
- Uses useMemo with search filter

---

### 13. ReconciliationPanel

**Route:** `/reconciliation`

**Component:** `frontend/src/pages/ReconciliationPanel.tsx`

**Filters:** Tab-based filters + sub-filters per tab (TBD - need to verify)

**Active Filters Display:** TBD

---

### 14. ReconciliationIssues

**Route:** `/reconciliation-issues`

**Component:** `frontend/src/pages/ReconciliationIssues.tsx`

**Filters:** Status/tab filters (TBD - need to verify)

**Active Filters Display:** TBD

---

### 15. SION Reports (SionE1, SionE5, SionE126, SionE132)

**Routes:** `/reports/parle/sion-e*`

**Components:** `frontend/src/pages/reports/SionE*.tsx`

**Filters:** Company filters likely (TBD - need to verify)

**Active Filters Display:** TBD

---

### 16. Other Reports (ExpiringLicenses, ActiveLicenses, DownloadLicense)

**Routes:** `/reports/expiring-licenses`, etc.

**Filters:** Company filters likely (TBD - need to verify)

**Active Filters Display:** TBD

---

### 17. LicensePurchaseProfitReport

**Route:** `/reports/license-purchase-profit`

**Component:** `frontend/src/pages/reports/LicensePurchaseProfitReport.tsx`

**Filters Implemented:**
- License Number exclusion input
- Date range (implied)

**Active Filters Display:** MISSING ❌

---

## Filter Statistics

| Category | Count |
|----------|-------|
| Total Filterable Routes | 40+ |
| Routes with ActiveFilters Display | 2 (ItemReport, PlannedReport) |
| Routes Needing ActiveFilters | 38+ |
| Total Unique Filter Types | 15+ |
| Pages with Complex Multi-Filter UI | 8+ |

---

## Filter UI Component Types

1. **Text Input** (search, debounced)
2. **Number Input** (balance, quantity)
3. **Select (Single)** (status, type, sort)
4. **MultiSelect** (companies, items, norms)
5. **Async Select** (companies, masters)
6. **Async MultiSelect** (companies, items)
7. **Date Picker** (single date)
8. **Date Range** (from/to)
9. **Toggle Switch** (boolean: active/active only)
10. **Button Group** (multiple choice as buttons)
11. **Tab-based Filter** (reconciliation tabs)
12. **Inline Toggle/Visibility** (SION sections)

---

## Next Steps

1. **Verify Missing Filters** in TBD pages
2. **Create ActiveFilters Component**
   - Reusable, generic component
   - Display filter name, value, count
   - Individual remove buttons (×)
   - Clear All functionality
   - Responsive design
3. **Implement ActiveFilters on All Pages**
4. **Test All Filters Systematically**
5. **Document Bugs Found**
6. **Create Regression Test Suite**
