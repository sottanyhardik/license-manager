# 20. Missing features and functional gaps

**Agent:** F (documentation, technical debt and missing features audit)
**Evidence snapshot:** branch `version-v1`, working tree as of 2026-11-01 (uncommitted changes included).
**Method:** compared the feature claims in `docs/01-project-overview.md` (Core Capabilities), `docs/03-features.md` (F-01..F-14), `docs/07-user-flows.md` and the operational claims against URL registrations, models, permission classes, frontend routes and git history. Read-only. No product scope was decided here. Where scope is unclear, a candidate question is listed in section 5 for the lead.
**Finding labels:** ISS-075..ISS-079 (this file's range).

---

## 1. Summary

- Most documented capabilities are implemented and routed: licence ledger, BOE, allotments, trade, transfer letters, ledger upload, master data, tasks, user and role management, SION planning, and the reports.
- Four documented items are partial or absent in code: the self-service password-reset confirmation step (ISS-075), the positive package-generation path in tests and the readiness link (ISS-076), commission and accounting (ISS-077), and several operational capabilities (ISS-078).
- The audit trail is HTTP-level only and partly described beyond what it does (ISS-079; DOC-03 in file 16).
- Two claims in the v1 record need correcting before they are relied on: the "Download Merged PDF removed in commit 79a08ac2" provenance (DOC-07), and the statement that the package flow has no positive coverage (partly true: the worker orchestration is not exercised, but item assembly is tested).
- The documented dashboard trend charts are not in the code (DOCUMENTED_BUT_NOT_BUILT).
- Notifications: no notification subsystem exists. The only outbound email is the password-reset message. This is confirmed, not assumed.

---

## 2. Status key

| Status | Meaning |
|---|---|
| IMPLEMENTED | Code path exists end to end (route or action, back end, UI entry where a UI is claimed). Test depth is noted separately where relevant |
| PARTIAL | Some of the documented behaviour exists; a named part is missing, unrouted, untested or defective |
| MISSING | Required or obviously expected capability has no code path, and the docs do not claim it as built |
| DOCUMENTED_BUT_NOT_BUILT | A document describes the capability as present or as the working flow, and the code does not contain it |

---

## 3. Feature status table

### 3.1 Core capabilities (`docs/01-project-overview.md:26-39`)

| # | Capability | Status | Code evidence | Note |
|---|---|---|---|---|
| C1 | License ledger (live balance per licence and importer) | IMPLEMENTED | `backend/apps/license/urls.py:33` (`license-ledger`); `frontend/src/pages/LicenseLedger.tsx` | |
| C2 | BOE management: upload, parse, link | IMPLEMENTED | `backend/apps/bill_of_entry/urls.py:10,13` (`bill-of-entries`, `parse-pdf`); `RowDetails` links to licence items (`docs/03-features.md:97-98`) | |
| C3 | Allotment tracking | IMPLEMENTED | `backend/apps/allotment/urls.py:10-11`; `frontend/src/pages/AllotmentAction.tsx` (routed) | Documented entry component not wired (F-04 below) |
| C4 | Trade invoicing (DFIA purchase and sale; incentive invoicing) | PARTIAL | `backend/apps/trade/urls.py:11-13`; `trade/models.py:138, 581`; no general ledger or bank layer (D5) | See 4.4 |
| C5 | Transfer letters | IMPLEMENTED | `backend/apps/bill_of_entry/views/boe.py:225`; `backend/apps/trade/views.py:617`; `backend/apps/core/urls.py:31` (`transfer-letters`); `frontend/src/components/TransferLetterForm.tsx:164-167` | |
| C6 | PDF and OCR parsing | IMPLEMENTED | `backend/apps/license/parsers/dfia_pdf.py` (pytesseract OCR); `backend/apps/license/urls.py:48` (`licenses/parse-pdf/`); `backend/apps/bill_of_entry/urls.py:13` | |
| C7 | Excel exports | IMPLEMENTED | `backend/apps/license/views/license.py:892` (`bulk-balance-excel`); exporters in `backend/apps/license/services/exporters/`; item pivot Excel in `views/item_pivot_report.py` | Route name is hyphenated (DOC-05) |
| C8 | Multi-server sync | PARTIAL | `scripts/maintenance/sync-masters.sh` (one-way master sync; calls `audit_masters` and `auto_import_masters`); peer sync `backend/apps/core/sync/` routed at `backend/lmanagement/urls.py:52` | Script exists; operation not evidenced. Peer layer undocumented (DOC-06) |
| C9 | Task management | IMPLEMENTED | `backend/apps/tasks/urls.py:9` (`tasks`), `TaskRemark` model; `frontend/src/components/TaskDrawer.tsx`, `TaskFAB.tsx` | |
| C10 | Role-based access (15 roles) | IMPLEMENTED | `backend/apps/accounts/views/user_management.py:13-29`; permission classes in `backend/apps/accounts/permissions.py` | ACCOUNT_ACCESS capability understated in docs (DOC-02) |
| C11 | Activity audit log | PARTIAL | `backend/apps/core/middleware.py:138-150` (HTTP-level, authenticated `/api/` only); `backend/apps/core/models.py:832` | See ISS-079 |
| C12 | Dashboard with KPI summary and trend charts | PARTIAL | `frontend/src/pages/Dashboard.tsx` (KPI); `backend/apps/license/urls.py:46` (`dashboard/`); no chart component (see 3.3, row O12) | Trend charts DOCUMENTED_BUT_NOT_BUILT |

### 3.2 Documented feature set (`docs/03-features.md`, F-01..F-14)

| # | Feature | Status | Code evidence | Note |
|---|---|---|---|---|
| F-01 | License management (DFIA) | IMPLEMENTED | `backend/apps/license/urls.py:28` (`licenses`); `views/license.py:213` `LicenseDetailsViewSet` | |
| F-02 | Incentive licence management (RODTEP, ROSTL, MEIS) | IMPLEMENTED | `backend/apps/license/urls.py:40`; `frontend/src/routes/AppRoutes.tsx:214-224` | |
| F-03 | Bill of Entry management | IMPLEMENTED | `backend/apps/bill_of_entry/urls.py:10-13` | Transfer letter action at `views/boe.py:225` |
| F-04 | Allotment management | IMPLEMENTED | `backend/apps/allotment/urls.py:10-11` | Documented creation form `AllotmentFormModal` is not wired (DOCUMENTED_BUT_NOT_BUILT as a sub-item, see 4.8) |
| F-05 | Trade invoicing | PARTIAL | `backend/apps/trade/models.py:138-650`, `:681-739` (invoice document and token models) | Commission and payments partial (see 4.4) |
| F-06 | License ledger | IMPLEMENTED | `backend/apps/license/views/ledger.py:643` (export action); `frontend/src/pages/LicenseLedger.tsx` | Export file path in docs is stale (DOC-05) |
| F-07 | Ledger upload (async CSV or HTM) | IMPLEMENTED | `backend/apps/license/urls.py:51, 53`; `backend/apps/license/views/ledger_upload.py:22-70` (CSV and HTM detection); `frontend/src/pages/LedgerUpload.tsx` (polls every 1 s, `:164-186`) | |
| F-08 | Transfer letter generation | IMPLEMENTED | Actions for BOE, trade and allotment (see C5) | |
| F-09 | Master data management | IMPLEMENTED | `backend/apps/core/urls.py:21-35` (generic master viewsets); `frontend/src/pages/masters/MasterList.tsx`; export action `backend/apps/core/views/master_view.py:673` | UI import not claimed by docs and not present (see 3.3, O7) |
| F-10 | Dashboard and reporting | IMPLEMENTED | Reports: `backend/apps/license/urls.py:37-61` (item pivot, item report, expiring, active, inventory balance, planned, licence purchase profit) | Dashboard trend charts DOCUMENTED_BUT_NOT_BUILT (C12) |
| F-11 | Task management | IMPLEMENTED | As C9 | |
| F-12 | Activity log and audit trail | PARTIAL | As C11 | See ISS-079 |
| F-13 | User and role management | IMPLEMENTED | `backend/apps/accounts/urls.py:18` (`users`), `views/user_management.py:61-62` (admin reset); `frontend/src/pages/admin/UserForm.tsx` | Self-service reset PARTIAL (O2) |
| F-14 | SION planning (auto plan) | IMPLEMENTED | `backend/apps/license/urls.py:32` (`sion-planning-rules`); editors in `frontend/src/pages/planning/` | Plan action not individually traced |

### 3.3 Operational and cross-cutting capabilities

| # | Capability | Status | Code evidence | Note |
|---|---|---|---|---|
| O1 | Self-service password reset: request | IMPLEMENTED | `backend/apps/accounts/urls.py:27`; `backend/apps/accounts/views/password.py:53-59` (email); `frontend/src/pages/auth/PasswordReset.tsx:23` | |
| O2 | Self-service password reset: confirmation | PARTIAL | Back end `backend/apps/accounts/urls.py:28` (`password-reset-confirm`, `PasswordResetConfirmView` in `views/password.py:78`). No frontend route or caller (see 4.1, ISS-075) | Most user-impacting gap in this table |
| O3 | Admin password reset | IMPLEMENTED | `backend/apps/accounts/views/user_management.py:61-62`; `frontend/src/pages/admin/UserForm.tsx:120-284` | |
| O4 | Notifications (in-app or email, beyond password reset) | MISSING | Only `send_mail` in the codebase: `backend/apps/accounts/views/password.py:59`. `NotificationNumber` in `core` is a DGFT reference master, not a user notification. No notification model or endpoint | Confirmed absent. Expiring licences exist as a report only (`backend/apps/license/urls.py:35`) |
| O5 | Audit trail coverage | PARTIAL | See ISS-079 | HTTP-level; no per-record history for balance rows |
| O6 | Bulk operations | PARTIAL | `bill_of_entry/views/boe.py:261` (bulk product names); `license/views_actions.py:184` (bulk licence transfer); `license/views/item_plan.py:159` (bulk upsert); bulk export `license/views/license.py:892`; ledger upload (bulk import) | No bulk delete or bulk edit found in a general form (not exhaustively searched) |
| O7 | Master data import and export | PARTIAL | Export: `backend/apps/core/views/master_view.py:673-674` (XLSX or PDF). Import: command line only (`auto_import_masters`, called by `scripts/maintenance/sync-masters.sh:77`). No UI import: the only import panel is for BOE PDFs (`frontend/src/pages/masters/BoeParsePanel.tsx:12`) | Docs do not claim UI import |
| O8 | Scheduled master sync | PARTIAL | `scripts/maintenance/sync-masters.sh` with cron example (header line 16) | Operation not evidenced; path stale (DOC-12) |
| O9 | Backup and restore | PARTIAL | Tooling: `scripts/database/db-tools.sh` (backup, restore, sync). Runbook and verified restore MISSING (DOC-13) | |
| O10 | Health and MDS status | IMPLEMENTED | `backend/lmanagement/urls.py:33-34` (`api/health/`, `api/mds/status/`) | |
| O11 | Rate limiting and throttle management | IMPLEMENTED | `backend/apps/core/throttling.py`; `backend/apps/core/urls.py:39-43` (throttle status, reset, stats, health) | Depth not verified |
| O12 | Dashboard trend charts | DOCUMENTED_BUT_NOT_BUILT | `docs/01-project-overview.md:39` says "KPI summary with trend charts". `Dashboard.tsx` has no chart; `recharts` appears only in a test mock (`src/pages/Dashboard.test.tsx:14`) and the Vite chunk list | See ISS-070 |
| O13 | Protected media and document download | IMPLEMENTED | `backend/lmanagement/urls.py:43` (`api/media/...`) | Security design out of scope here |

---

## 4. Partial-feature list

### 4.1 Self-service password reset (O2)
- **Built:** request endpoint and form (`accounts/urls.py:27`, `PasswordReset.tsx:23`), email with a link `FRONTEND_URL/reset-password/{uid}/{token}/` (`accounts/views/password.py:53`), confirmation endpoint (`accounts/urls.py:28`, `views/password.py:78`).
- **Missing:** a frontend route for `/reset-password/:uid/:token`, and any frontend call to `password-reset-confirm`. The only route is `/forgot-password` (`AppRoutes.tsx:80`). The catch-all route (`AppRoutes.tsx:335`) renders NotFound for the emailed link.
- **Status:** PARTIAL. ISS-075.

### 4.2 Package generation and readiness (ISS-076)
- **Built:** job pipeline in `backend/apps/license/tasks.py` (`enqueue_license_ledger_package_job` line 314, `build_license_ledger_package_item` line 413, `finalize_license_ledger_package_job` line 476). Endpoint `POST /api/license-ledger/download-package/` (202 on accept) and status, covered by `backend/apps/license/tests/test_license_ledger_package_jobs.py`.
- **Tested:** request acceptance (202), duplicate-ID handling, owner scoping of status and downloads, idempotency key, exposure of safe artefact metadata for a manually set `server_ready` item, and the item-section assembly with real PDF bytes and A4 page checks (`test_license_ledger_package_jobs.py` around lines 86-110; `test_license_ledger_package.py`, 5 tests).
- **Not tested:** the three Celery tasks are never invoked directly (the job tests patch `enqueue_license_ledger_package_job.delay`). No test drives an item from queued to `server_ready` through the real builder and finalizer, and no test downloads a finalized ZIP. The only E2E package spec covers the blocked path (`frontend/e2e/package-download.spec.ts:20`).
- **Known partial item:** the positive generation flow is not covered end to end. The claim in the brief is therefore correct, with the qualifier that item assembly is tested.
- **Readiness link (ISS-018):** `frontend/src/pages/LicenseLedger.tsx:618` passes `packageJob.job_id`, which is correct. `frontend/src/pages/LicenseDownloadRequestDetail.tsx:7` passes `r.request_key`, which the readiness route does not accept. Runtime evidence in `docs/v1/system-audit/evidence/runtime-verification-2026-11-01.md` shows readiness returns 404 for `request_key` and 200 for the job key. The detail page's own readiness call was not inspected in that run; this pass shows the link source.

### 4.3 Merged PDF and downloads
- **Claim in v1 docs:** "Download Merged PDF" control removed in commit `79a08ac2` (DOC-07).
- **Git:** the control's text first appears in `a4ce8d44`. `79a08ac2` adds e2e assertions that click "Download Merged PDF (1)" and adds the package back end. HEAD `frontend/src` no longer has the string. The removing commit was not isolated.
- **Still present:** per-licence merged documents (`backend/apps/license/views/license.py:965`, `GET /api/licenses/:id/merged-documents/`), opened from `frontend/src/pages/masters/tables/LicensesTable.tsx:1028-1147`, `components/AccordionTable.tsx:489`, `components/LicenseBalanceModal.tsx:449`. Package build `LicenseLedgerPackageService.build_merged_pdf` is called from `backend/apps/license/views/ledger.py:428`.
- **Status:** PARTIAL. The multi-select toolbar control is gone from HEAD; per-licence merged documents and the package ZIP remain.

### 4.4 Commission, invoices, payments and accounting (ISS-077)
- **Commission built:** direction values `COMMISSION_PURCHASE` and `COMMISSION_SALE` (`backend/apps/trade/models.py:79-90`) and their document number formats; ledger treatment `commission_treatment: EXCLUDED` for commission types (`backend/apps/license/domain/transaction_semantics.py:93, 111, 126`); `is_commission` flag on ledger rows (`backend/apps/license/serializers/ledger.py:70`).
- **Commission not built:** no commission rate, amount, agent or payable fields in models (grep of `commission_rate`, `commission_amount` and similar: no matches). No commission accounting entries.
- **Invoices built:** `TradeInvoiceDocument` (`trade/models.py:681`), `InvoiceDocumentAccessToken` (`:711`), `InvoiceDocumentAuditEvent` (`:739`), public token view `trade/urls.py:9`. Generation path and UI entry point were not traced; the only frontend reference to the invoice-document endpoint is in a test (`LicenseLedgerDetail.summary.test.tsx`).
- **Payments built:** `LicenseTradePayment` (`trade/models.py:650`), registered viewset (`trade/views.py:671-696`), nested in the trade form payload (`frontend/src/pages/tradeFormHelpers.ts:40`). No standalone payment screen and no bank matching.
- **Accounting not built:** `docs/guides/COMMISSION_ACCOUNTING_GUIDE.md` describes Debit and Credit entries for commission. `backend/apps/accounting/` is residue (file 19, ISS-071). `docs/v1/00-executive-overview/decisions-required.md:9, 32-34` (D5) records "full GL/bank domain not found" and an open owner decision.
- **Status:** commission PARTIAL; invoices PARTIAL; payments PARTIAL; accounting DOCUMENTED_BUT_NOT_BUILT (guide) and MISSING (general ledger, bank).

### 4.5 Excel export (C7)
- **Built and routed:** `POST /api/licenses/bulk-balance-excel/` (`views/license.py:892`), `frontend/src/pages/reports/DownloadLicense.tsx`; ledger export action (`views/ledger.py:643`); item pivot Excel (`views/item_pivot_report.py`); active-licence report Excel (`views/active_licenses_report.py:300`).
- **Test evidence:** the E2E financial-ledger spec now checks the Excel export in place of the merged-PDF check (`docs/v1/execution-log.md:141`).
- **Status:** IMPLEMENTED. The docs path `ledgerExport.ts` is stale (DOC-05).

### 4.6 Data Readiness link (ISS-018)
- See 4.2. The defect is in the link source (`LicenseDownloadRequestDetail.tsx:7`), not in the readiness view. Status PARTIAL. Existing register item ISS-018; this file does not assign a new ID for it.

### 4.7 Reconciliation surfaces
- **Built:** `ReconciliationPanel` at `/reconciliation` (`AppRoutes.tsx:198-201`, roles BOE_MANAGER, TRADE_MANAGER, ACCOUNT_ACCESS) and `ReconciliationIssues` at `/reconciliation-issues` (`AppRoutes.tsx:204-209`, adds TRADE_VIEWER, BOE_VIEWER, TL_GENERATE). Back end `backend/apps/reconciliation/urls.py:10`.
- **Overlap:** same domain, shared helpers and components, different role gates. `ReconciliationIssues` calls itself a read-only companion (`AppRoutes.tsx:204-206`).
- **Status:** PARTIAL (duplicated surfaces; product intent for one or two screens is not recorded). Question Q11.

### 4.8 Allotment creation form
- `docs/03-features.md:120, 143` says the allotment item is "entered manually in `AllotmentFormModal`". The component has no importer (file 19). The routed page `AllotmentAction.tsx` handles allotment work.
- **Status:** DOCUMENTED_BUT_NOT_BUILT for the modal; IMPLEMENTED for allotment management through the page.

### 4.9 Activity log (C11, F-12) and audit coverage (O5)
- See ISS-079.

---

## 5. Candidate questions for the lead

Questions are product questions. They were not put to the product owner. Each names the evidence and the impact if the answer differs from the current code.

| # | Category | Question | Impact | Evidence |
|---|---|---|---|---|
| Q1 | Scope, accounting | Is commission accounting (Debit and Credit entries, commission rates, agent amounts) part of V1, or is commission limited to trade direction and exclusion from licence balance? | High. Changes whether ISS-077 is a gap or a scope statement | ISS-077; `docs/guides/COMMISSION_ACCOUNTING_GUIDE.md`; D5 |
| Q2 | Access, security | Should ACCOUNT_ACCESS be read-only as documented, or may it edit BOE invoice numbers as coded? | High. Permission model and any access review depend on it | DOC-02; `accounts/permissions.py:150-156`; `bill_of_entry/views/boe.py:131-132` |
| Q3 | Authentication | Must a user complete a password reset through the emailed link in V1, or is an administrator-initiated reset the intended V1 path? | High. Determines whether ISS-075 is a blocker | ISS-075; `accounts/views/password.py:53-59` |
| Q4 | Audit | Is HTTP-level activity logging sufficient as the V1 audit trail, or must balance-changing records keep per-record change history? | High. Compliance question; links to open decision D6 | ISS-079; `decisions-required.md:10` |
| Q5 | Architecture, sync | Is peer-to-peer sync (`apps/core/sync`) an intended V1 mechanism across the three servers, or is the one-way master-sync script the only intended path? | High. Decides whether DOC-06 is a documentation gap or a scope gap | DOC-06; file 19 section 3 |
| Q6 | Operations | What recovery point and recovery time objectives apply to V1, and must a restore be rehearsed before sign-off? | High. Gate for the v1 backup-and-recovery record | DOC-13; `docs/v1/07-quality-and-operations/backup-and-recovery.md` |
| Q7 | Notifications | Is any user-facing notification in V1 (for example expiring licences, task assignment, allotment changes), or is only the password-reset email intended? | Medium. The expiring-licence report exists but has no alert | ISS-078; `license/urls.py:35` |
| Q8 | Master data | Should master data import be available in the UI for V1, or is operator-run command-line import intended? | Medium. Changes whether O7 is a gap | ISS-078; `scripts/maintenance/sync-masters.sh:77` |
| Q9 | Downloads | Should a single merged-licence PDF download be restored in the ledger UI, or is the package ZIP the intended download? | Medium. Affects ISS-076 and the v1 E2E narrative | DOC-07; section 4.3 |
| Q10 | Dashboard | Are dashboard trend charts a V1 requirement (`docs/01-project-overview.md:39`), or is a KPI-only dashboard the intended scope? | Low. Affects whether ISS-070's unused `recharts` is removed or used | O12; ISS-070 |
| Q11 | Reconciliation | Should the work-queue reconciliation screen and the read-only reconciliation-issues screen stay separate, and should they share role gates? | Medium. Affects user confusion and permission review | Section 4.7; ISS-072 |
| Q12 | Master data | Is the deprecated Item Head master (`core/models.py:307-308`) to be retired or kept for V1? | Medium. Affects data migration and master sync | File 19 section 9 |
| Q13 | Terminology | Which spelling, "licence" or "license", is the user-facing standard for V1? | Low. Affects UI text and documentation consistency | File 19 section 7 |
| Q14 | Allotment flow | Is the routed allotment page the intended entry point, with `AllotmentFormModal` retired? | Low. Confirms DOC-05 correction direction | Section 4.8 |
| Q15 | Deployment | Is the three-server topology (canonical plus two followers) the intended V1 target, and which host runs the Celery worker and beat? | Medium. Required for any deployment runbook (DOC-13) | `docs/01-project-overview.md:73-92` (not verifiable from code) |

Categories: scope and accounting (Q1), security and access (Q2, Q4), authentication (Q3), architecture (Q5), operations (Q6, Q15), product features (Q7, Q9, Q10), master data (Q8, Q12), UX and terminology (Q11, Q13, Q14).

---

## 6. Findings ISS-075 to ISS-079

### ISS-075: Password-reset confirmation step is missing from the UI (High)
- **Status:** PARTIAL. Back end complete; front end incomplete.
- **Evidence.**
  - Back end sends the link `${FRONTEND_URL}/reset-password/{uid}/{token}/` (`backend/apps/accounts/views/password.py:53`) and exposes `password-reset-confirm/` (`backend/apps/accounts/urls.py:28`, `PasswordResetConfirmView` at `views/password.py:78`).
  - Front end has one reset-related route, `/forgot-password` (`frontend/src/routes/AppRoutes.tsx:80`), backed by `pages/auth/PasswordReset.tsx`, which only requests the email (line 23).
  - No frontend route matches `/reset-password/...` and no frontend module calls `password-reset-confirm` (grep across `frontend/src` and `frontend/e2e`).
  - The catch-all route (`AppRoutes.tsx:335`) renders NotFound for the emailed link.
- **Effect.** A user who requests a reset can receive a working token that no screen accepts. The admin reset (`UserForm.tsx`) is the only working reset path.
- **Direction.** Record only. Owner question Q3 decides whether this is a V1 blocker.

### ISS-076: Package generation has no end-to-end test; merged-PDF history and readiness link are inaccurate (Medium)
- **Status:** PARTIAL.
- **Evidence.**
  - Worker tasks `backend/apps/license/tasks.py:314, 413, 476` are not invoked by any test; job tests patch `.delay` (`backend/apps/license/tests/test_license_ledger_package_jobs.py:20-44, 56-72`).
  - The only package E2E spec covers the blocked path (`frontend/e2e/package-download.spec.ts:20`).
  - Merged PDF: DOC-07 (provenance of removal not supported by `79a08ac2`; per-licence merged documents remain).
  - Readiness link: `frontend/src/pages/LicenseDownloadRequestDetail.tsx:7` passes `request_key` to the readiness route, which the runtime evidence shows returns 404 (`docs/v1/system-audit/evidence/runtime-verification-2026-11-01.md`, ISS-018 section). ISS-018 is the existing register item for this defect.
- **Effect.** No automated proof that a licence package reaches a downloadable state. The detail page's readiness link is broken for users who open it from a download request.
- **Direction.** Record only. Test scope and the merged-PDF question (Q9) are for the owner and the test plan; the readiness link is a defect already registered as ISS-018.

### ISS-077: Commission, invoices, payments and accounting are partial or absent (High)
- **Status:** PARTIAL (commission, invoices, payments); DOCUMENTED_BUT_NOT_BUILT and MISSING (accounting).
- **Evidence.**
  - Commission: directions (`backend/apps/trade/models.py:79-90`) and exclusion semantics (`backend/apps/license/domain/transaction_semantics.py:93, 111, 126`) exist. No amount, rate, agent or payable fields exist on any model.
  - Accounting: `docs/guides/COMMISSION_ACCOUNTING_GUIDE.md` describes Debit and Credit entries. `backend/apps/accounting/` contains only bytecode (file 19). No general-ledger or bank model, route or screen exists. D5 (`docs/v1/00-executive-overview/decisions-required.md:9, 32-34`) is open.
  - Invoices: models and a token view exist (`trade/models.py:681, 711, 739`; `trade/urls.py:9`); generation and UI entry not traced.
  - Payments: `LicenseTradePayment` is nested in the trade form only; no bank matching.
- **Effect.** Business rules in the commission guide cannot be executed as written. The V1 commercial evidence boundary depends on D5.
- **Direction.** Record only. Owner question Q1 and decision D5.

### ISS-078: Notifications, bulk operations, master import and dashboard charts are missing or partial (Medium)
- **Status:** MISSING (notifications; UI master import); PARTIAL (bulk operations); DOCUMENTED_BUT_NOT_BUILT (dashboard trend charts).
- **Evidence.**
  - Notifications: the only outbound email is the password-reset message (`backend/apps/accounts/views/password.py:59`). No notification model, endpoint or screen. `NotificationNumber` is a DGFT reference master.
  - Bulk operations: three bulk actions exist (`bill_of_entry/views/boe.py:261`, `license/views_actions.py:184`, `license/views/item_plan.py:159`). No general bulk delete or bulk edit was found; not exhaustively searched.
  - Master import: command-line only (`auto_import_masters`, `scripts/maintenance/sync-masters.sh:77`). Export exists (`core/views/master_view.py:673`). No UI import.
  - Dashboard charts: `docs/01-project-overview.md:39` promises trend charts; `Dashboard.tsx` has none (ISS-070).
- **Effect.** Operators depend on the command line for master import. Expiring licences are visible only in a report, with no alert.
- **Direction.** Record only. Owner questions Q7, Q8 and Q10.

### ISS-079: Audit trail is HTTP-level and does not cover balance-bearing records (High)
- **Status:** PARTIAL.
- **Evidence.**
  - `ActivityLogMiddleware` writes one row per authenticated `/api/` request, except OPTIONS (`backend/apps/core/middleware.py:138-150`), in a daemon thread (`middleware.py:98-111`). Logging is disabled when the `TESTING` environment variable is set (`middleware.py:91-94`); the function's comment also names pytest and `manage.py test`.
  - `ActivityLog` has no request body or before and after values (`backend/apps/core/models.py:832`). The docs claim a body (DOC-03).
  - `AuditModel` (`backend/apps/core/models.py:96`) is inherited by 38 model classes (grep). 47 `models.Model` declarations do not inherit it; this count includes abstract helpers such as `AuditModel` itself, so about 45 concrete models are plain. They include balance-bearing `LicenseImportItemsModel` (`backend/apps/license/models/core.py:902`), `LicenseExportItemModel` (`:860`), `LicenseReplanRequest` (`:1194`), `LicenseDocumentModel` (`:1859`), and reconciliation records `ReconciliationLog` and `IgnoredWarning` (`backend/apps/reconciliation/models.py:95, 518`).
  - Changes made by management commands, Celery tasks or signals are not HTTP requests and are not logged by this middleware (by design of the middleware).
  - Decision D6 (`docs/v1/00-executive-overview/decisions-required.md:10`) records asynchronous daemon logging as an open durability question.
- **Effect.** The audit trail cannot establish who changed a balance-bearing record, what it was before, or changes made outside HTTP. Not verified: whether other mechanisms (for example `AuditModel` on related records, or ledger snapshots) provide that history for these models.
- **Direction.** Record only. Owner question Q4 and decision D6.

---

## 7. Limits

- Static review only. Routes, models and permissions were read from code; no request was sent, no test was run and no browser was used.
- Feature rows marked IMPLEMENTED reflect code presence and a routed entry point. Behavioural correctness was not tested.
- "Not exhaustively searched" items (O6 bulk operations, C12 and O13 depth) are stated where the search was partial.
- The merged-PDF removal commit was not isolated; section 4.3 reports what git shows for `a4ce8d44` and `79a08ac2`.
- The readiness defect is evidenced by code and by the existing runtime record; this pass did not re-run the probe.
- Product questions were not asked of the owner. Section 5 is the input to the lead.
- Line numbers refer to the working tree on 2026-11-01. Other agents are writing files in `docs/v1/` concurrently.
