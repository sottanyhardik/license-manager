# COMPLETE ROUTE INVENTORY & TEST TRACKING

Generated: 2026-09-25  
Total Routes: 48 (including parameterized variants)

---

## PUBLIC ROUTES

| Route | Component | Auth Required | Test Status | Evidence |
|-------|-----------|---------------|------------|----------|
| `/login` | Login | No | ❌ UNTESTED | |
| `/forgot-password` | PasswordReset | No | ❌ UNTESTED | |
| `/` | Navigate to /dashboard | Yes | ❌ UNTESTED | |
| `/401` | Unauthorized | N/A | ❌ UNTESTED | |
| `/403` | Forbidden | N/A | ❌ UNTESTED | |
| `/*` (404) | NotFound | N/A | ❌ UNTESTED | |
| `/pdf-viewer` | PDFViewer | Yes | ❌ UNTESTED | |

---

## CORE NAVIGATION

| Route | Component | Auth Required | Test Status | Evidence |
|-------|-----------|---------------|------------|----------|
| `/dashboard` | Dashboard | Yes | ✅ PASSED | Browser loads |
| `/profile` | Profile | Yes | ❌ UNTESTED | |
| `/settings` | Settings | Yes (admin) | ❌ UNTESTED | |

---

## LICENSE MANAGEMENT

| Route | Component | Auth Required | Test Status | Evidence |
|-------|-----------|---------------|------------|----------|
| `/licenses` | MasterList (licenses) | Yes (LICENSE_MANAGER/VIEWER) | ✅ LOADED | HTTP 200 |
| `/licenses/create` | MasterForm (create) | Yes (LICENSE_MANAGER) | ❌ UNTESTED | |
| `/licenses/:id/edit` | MasterForm (edit) | Yes (LICENSE_MANAGER) | ❌ UNTESTED | |
| `/licenses/:id/overview` | LicenseOverviewPage | Yes (multiple roles) | ❌ UNTESTED | |
| `/licenses/:id/balance` | RedirectToLicenseOverview | Yes | ❌ UNTESTED | |
| `/planning` | LicensePlanningWorkspace | Yes (LICENSE_MANAGER) | ❌ UNTESTED | |

---

## ALLOTMENT MANAGEMENT

| Route | Component | Auth Required | Test Status | Evidence |
|-------|-----------|---------------|------------|----------|
| `/allotments` | MasterList (allotments) | Yes (ALLOTMENT_MANAGER/VIEWER) | ❌ UNTESTED | |
| `/allotments/create` | MasterForm (create) | Yes (ALLOTMENT_MANAGER) | ❌ UNTESTED | |
| `/allotments/:id/edit` | MasterForm (edit) | Yes (ALLOTMENT_MANAGER) | ❌ UNTESTED | |
| `/allotments/:id/allocate` | AllotmentAction | Yes (ALLOTMENT_MANAGER) | ❌ UNTESTED | |

---

## BILL OF ENTRY (BOE)

| Route | Component | Auth Required | Test Status | Evidence |
|-------|-----------|---------------|------------|----------|
| `/bill-of-entries` | MasterList (BOE) | Yes (BOE_MANAGER/VIEWER+) | ❌ UNTESTED | |
| `/bill-of-entries/create` | MasterForm (create) | Yes (BOE_MANAGER) | ❌ UNTESTED | |
| `/bill-of-entries/:id/edit` | MasterForm (edit) | Yes (BOE_MANAGER) | ❌ UNTESTED | |
| `/bill-of-entries/:id/generate-transfer-letter` | BOETransferLetter | Yes (BOE_MANAGER/VIEWER/TL_GENERATE) | ❌ UNTESTED | |

---

## TRADE MANAGEMENT

| Route | Component | Auth Required | Test Status | Evidence |
|-------|-----------|---------------|------------|----------|
| `/trades` | MasterList (trades) | Yes (TRADE_MANAGER/VIEWER) | ❌ UNTESTED | |
| `/trades/create` | TradeForm | Yes (TRADE_MANAGER) | ❌ UNTESTED | |
| `/trades/:id/edit` | TradeForm | Yes (TRADE_MANAGER) | ❌ UNTESTED | |

---

## INCENTIVE LICENSES

| Route | Component | Auth Required | Test Status | Evidence |
|-------|-----------|---------------|------------|----------|
| `/incentive-licenses` | MasterList (incentive) | Yes (INCENTIVE_LICENSE_MANAGER/VIEWER) | ❌ UNTESTED | |
| `/incentive-licenses/create` | MasterForm (create) | Yes (INCENTIVE_LICENSE_MANAGER) | ❌ UNTESTED | |
| `/incentive-licenses/:id/edit` | MasterForm (edit) | Yes (INCENTIVE_LICENSE_MANAGER) | ❌ UNTESTED | |

---

## LEDGER & BALANCE

| Route | Component | Auth Required | Test Status | Evidence |
|-------|-----------|---------------|------------|----------|
| `/ledger-upload` | LedgerUpload | Yes (LICENSE_MANAGER/LEDGER_MANAGER) | ❌ UNTESTED | |
| `/license-ledger` | LicenseLedger | Yes (multiple roles) | ❌ UNTESTED | |
| `/license-ledger/:licenseId` | LicenseLedgerDetail | Yes (multiple roles) | ❌ UNTESTED | |
| `/license-ledger/:licenseId/:itemId` | LicenseLedgerDetail | Yes (multiple roles) | ❌ UNTESTED | |
| `/license-ledger/download-requests` | LicenseDownloadRequests | Yes (multiple roles) | ❌ UNTESTED | |
| `/license-ledger/download-requests/:requestId` | LicenseDownloadRequestDetail | Yes (multiple roles) | ❌ UNTESTED | |
| `/license-ledger/package-readiness/:jobId` | LicenseLedgerPackageReadiness | Yes (LICENSE_MANAGER/TRADE_MANAGER/LEDGER_MANAGER) | ❌ UNTESTED | |

---

## REPORTS

| Route | Component | Auth Required | Test Status | Evidence |
|-------|-----------|---------------|------------|----------|
| `/reports/parle/sion-e1` | SionE1 | Yes (REPORT_ROLES) | ❌ UNTESTED | |
| `/reports/parle/sion-e5` | SionE5 | Yes (REPORT_ROLES) | ❌ UNTESTED | |
| `/reports/parle/sion-e126` | SionE126 | Yes (REPORT_ROLES) | ❌ UNTESTED | |
| `/reports/parle/sion-e132` | SionE132 | Yes (REPORT_ROLES) | ❌ UNTESTED | |
| `/reports/expiring-licenses` | ExpiringLicenses | Yes (REPORT_ROLES) | ❌ UNTESTED | |
| `/reports/active-licenses` | ActiveLicenses | Yes (REPORT_ROLES) | ✅ LOADED | HTTP 200 |
| `/reports/download-license` | DownloadLicense | Yes (REPORT_ROLES) | ❌ UNTESTED | |
| `/reports/item-pivot` | ItemPivotReport | Yes (REPORT_ROLES) | ✅ LOADED | HTTP 200 |
| `/reports/item-report` | ItemReport | Yes (REPORT_ROLES) | ✅ LOADED | HTTP 200 |
| `/reports/planned-report` | PlannedReport | Yes (REPORT_ROLES) | ❌ UNTESTED | |
| `/reports/license-purchase-profit` | LicensePurchaseProfitReport | Yes (REPORT_ROLES) | ❌ UNTESTED | |

---

## RECONCILIATION

| Route | Component | Auth Required | Test Status | Evidence |
|-------|-----------|---------------|------------|----------|
| `/reconciliation` | ReconciliationPanel | Yes (BOE_MANAGER/TRADE_MANAGER/ACCOUNT_ACCESS) | ❌ UNTESTED | |
| `/reconciliation-issues` | ReconciliationIssues | Yes (multiple roles) | ❌ UNTESTED | |

---

## ADMIN & MASTERS

| Route | Component | Auth Required | Test Status | Evidence |
|-------|-----------|---------------|------------|----------|
| `/admin/users` | UserList | Yes (USER_MANAGER) | ❌ UNTESTED | |
| `/admin/users/create` | UserForm | Yes (USER_MANAGER) | ❌ UNTESTED | |
| `/admin/users/:id/edit` | UserForm | Yes (USER_MANAGER) | ❌ UNTESTED | |
| `/admin/activity-log` | ActivityLog | Yes (USER_MANAGER) | ❌ UNTESTED | |
| `/masters/:entity` | MasterList (dynamic) | Yes (multiple) | ❌ UNTESTED | |
| `/masters/:entity/create` | MasterForm (create) | Yes (USER_MANAGER) | ❌ UNTESTED | |
| `/masters/:entity/:id/edit` | MasterForm (edit) | Yes (USER_MANAGER) | ❌ UNTESTED | |

---

## SUMMARY

- **Total Routes:** 48
- **Loaded in Browser:** 4
- **Not Tested:** 44 ❌

---

## NEXT STEPS

1. Test every route with Playwright
2. Verify authentication boundaries
3. Test interactive elements on each page
4. Test forms with actual data
5. Test exports and downloads
6. Verify error states
7. Test API failure injection
