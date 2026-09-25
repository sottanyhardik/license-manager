# QA MATRIX - LIVE TRACKING

**Last Updated:** 2026-09-25  
**Status:** IN PROGRESS - PHASE 1

## ROUTE MATRIX

| Route | Page | Auth | Perms | Load | Interact | Forms | API | Negative | Responsive | Accessibility | Status |
|-------|------|------|-------|------|-----------|-------|-----|----------|------------|----------------|--------|
| /login | Login | No | - | PASS | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | IN_PROGRESS |
| /forgot-password | PasswordReset | No | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| / | Redirect | Yes | - | NOT_TESTED | NOT_TESTED | - | - | NOT_TESTED | - | - | NOT_TESTED |
| /401 | ErrorPage | - | - | NOT_TESTED | - | - | - | - | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /403 | ErrorPage | - | - | NOT_TESTED | - | - | - | - | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /dashboard | Dashboard | Yes | Multi | PASS | NOT_TESTED | - | PASS | NOT_TESTED | NOT_TESTED | NOT_TESTED | IN_PROGRESS |
| /profile | Profile | Yes | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /settings | Settings | Yes | Admin | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /licenses | List | Yes | LIC_M/V | PASS | NOT_TESTED | - | PASS | NOT_TESTED | NOT_TESTED | NOT_TESTED | IN_PROGRESS |
| /licenses/create | Create | Yes | LIC_M | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /licenses/:id/edit | Edit | Yes | LIC_M | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /licenses/:id/overview | Overview | Yes | Multi | NOT_TESTED | NOT_TESTED | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /licenses/:id/balance | Redirect | Yes | Multi | NOT_TESTED | - | - | - | - | - | - | NOT_TESTED |
| /planning | Workspace | Yes | LIC_M | NOT_TESTED | NOT_TESTED | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /allotments | List | Yes | ALLOT_M/V | PASS | NOT_TESTED | - | PASS | NOT_TESTED | NOT_TESTED | NOT_TESTED | IN_PROGRESS |
| /allotments/create | Create | Yes | ALLOT_M | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /allotments/:id/edit | Edit | Yes | ALLOT_M | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /allotments/:id/allocate | Action | Yes | ALLOT_M | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /bill-of-entries | List | Yes | BOE_M/V+ | PASS | NOT_TESTED | - | PASS | NOT_TESTED | NOT_TESTED | NOT_TESTED | IN_PROGRESS |
| /bill-of-entries/create | Create | Yes | BOE_M | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /bill-of-entries/:id/edit | Edit | Yes | BOE_M | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /bill-of-entries/:id/generate-transfer-letter | PDF | Yes | BOE_M/V/TL | NOT_TESTED | NOT_TESTED | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /trades | List | Yes | TRADE_M/V | PASS | NOT_TESTED | - | PASS | NOT_TESTED | NOT_TESTED | NOT_TESTED | IN_PROGRESS |
| /trades/create | Create | Yes | TRADE_M | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /trades/:id/edit | Edit | Yes | TRADE_M | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /incentive-licenses | List | Yes | INCENT_M/V | NOT_TESTED | NOT_TESTED | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /incentive-licenses/create | Create | Yes | INCENT_M | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /incentive-licenses/:id/edit | Edit | Yes | INCENT_M | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /ledger-upload | Upload | Yes | LIC_M/LEDGER_M | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /license-ledger | List | Yes | Multi | PASS | NOT_TESTED | - | PASS | NOT_TESTED | NOT_TESTED | NOT_TESTED | IN_PROGRESS |
| /license-ledger/:licenseId | Detail | Yes | Multi | NOT_TESTED | NOT_TESTED | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /license-ledger/:licenseId/:itemId | ItemDetail | Yes | Multi | NOT_TESTED | NOT_TESTED | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /license-ledger/download-requests | List | Yes | Multi | NOT_TESTED | NOT_TESTED | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /license-ledger/download-requests/:requestId | Detail | Yes | Multi | NOT_TESTED | NOT_TESTED | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /license-ledger/package-readiness/:jobId | Status | Yes | Multi | NOT_TESTED | NOT_TESTED | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /reports/parle/sion-e1 | Report | Yes | REPORT | NOT_TESTED | NOT_TESTED | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /reports/parle/sion-e5 | Report | Yes | REPORT | NOT_TESTED | NOT_TESTED | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /reports/parle/sion-e126 | Report | Yes | REPORT | NOT_TESTED | NOT_TESTED | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /reports/parle/sion-e132 | Report | Yes | REPORT | NOT_TESTED | NOT_TESTED | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /reports/expiring-licenses | Report | Yes | REPORT | NOT_TESTED | NOT_TESTED | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /reports/active-licenses | Report | Yes | REPORT | PASS | NOT_TESTED | - | PASS | NOT_TESTED | NOT_TESTED | NOT_TESTED | IN_PROGRESS |
| /reports/download-license | Report | Yes | REPORT | NOT_TESTED | NOT_TESTED | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /reports/item-pivot | Report | Yes | REPORT | PASS | NOT_TESTED | - | PASS | NOT_TESTED | NOT_TESTED | NOT_TESTED | IN_PROGRESS |
| /reports/item-report | Report | Yes | REPORT | PASS | NOT_TESTED | - | PASS | NOT_TESTED | NOT_TESTED | NOT_TESTED | IN_PROGRESS |
| /reports/planned-report | Report | Yes | REPORT | NOT_TESTED | NOT_TESTED | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /reports/license-purchase-profit | Report | Yes | REPORT | NOT_TESTED | NOT_TESTED | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /reconciliation | Panel | Yes | Multi | PASS | NOT_TESTED | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | IN_PROGRESS |
| /reconciliation-issues | List | Yes | Multi | NOT_TESTED | NOT_TESTED | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /admin/users | List | Yes | USER_M | PASS | NOT_TESTED | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | IN_PROGRESS |
| /admin/users/create | Create | Yes | USER_M | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /admin/users/:id/edit | Edit | Yes | USER_M | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /admin/activity-log | Log | Yes | USER_M | NOT_TESTED | NOT_TESTED | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /masters/:entity | List | Yes | USER_M | NOT_TESTED | NOT_TESTED | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /masters/:entity/create | Create | Yes | USER_M | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /masters/:entity/:id/edit | Edit | Yes | USER_M | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| /pdf-viewer | Viewer | Yes | - | NOT_TESTED | NOT_TESTED | - | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |

---

## WORKFLOW COVERAGE

| Workflow | Steps | Status |
|----------|-------|--------|
| Login Flow | login → dashboard | NOT_TESTED |
| License Lifecycle | create → read → edit → view balance → ledger | NOT_TESTED |
| Allotment Flow | create → allocate → verify balance impact | NOT_TESTED |
| Trade Flow | create → link BOE → verify ledger | NOT_TESTED |
| Report Generation | load → filter → search → export → PDF | NOT_TESTED |
| Ledger Upload | select file → upload → process → verify | NOT_TESTED |

---

## FORM COVERAGE

| Form | Route | Valid | Empty | Invalid | Duplicate | Status |
|------|-------|-------|-------|---------|-----------|--------|
| License Create | /licenses/create | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| License Edit | /licenses/:id/edit | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| Allotment Create | /allotments/create | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |

---

## EXPORT/PDF COVERAGE

| Report/Export | Format | Download | Content | Data Match | Status |
|---------------|--------|----------|---------|------------|--------|
| License Ledger | PDF | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| SION E1 | Excel | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| Item Pivot | Excel | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |
| Active Licenses | Excel | NOT_TESTED | NOT_TESTED | NOT_TESTED | NOT_TESTED |

---

## BUG TRACKING

| ID | Route | Issue | Severity | Status |
|----|-------|-------|----------|--------|
| NONE_YET | - | - | - | - |

---

## SUMMARY

- Routes Tested: 10/48
- Routes PASS: 10/48
- Routes FAIL: 0/48
- Routes IN_PROGRESS: 10/48
- Routes NOT_TESTED: 28/48

- Workflows Tested: 0/6
- Forms Tested: 0/10+
- PDFs Tested: 0/5+
- Exports Tested: 0/5+

- Bugs Found: 0
- Bugs Fixed: 0

**NEXT:** Continue Phase 1 - test remaining 38 routes, then move to Phase 2 (workflows)
