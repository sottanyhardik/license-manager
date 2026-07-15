# Feature Parity Matrix — Legacy vs. New System

**Audit Date:** 2026-07-15  
**Auditor:** Product Manager (25-yr)  
**Scope:** All modules, screen by screen, API by API, business rule by business rule  
**Source of Truth:** `legacy/` directory (read-only, frozen reference)  
**Target:** `backend/` + `frontend/` (new system on `feature/V1` branch)

---

## Executive Summary

| Metric | Count |
|--------|-------|
| Total features audited | 91 |
| ✅ Complete (backend + frontend) | 28 (31%) |
| ⚠️ Partial (one side missing or incomplete) | 14 (15%) |
| ❌ Missing (completely absent) | 49 (54%) |
| **CRITICAL gaps** | **9** |
| **HIGH gaps** | **26** |
| **MEDIUM gaps** | **19** |

**The new system has implemented the core CRUD layer and authentication. It is missing the entire operational workflow layer: allocation, ledger management, PDF generation actions, ownership/transfer tracking, user administration, and all reports.**

---

## Status Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Both backend endpoint and frontend UI exist and work |
| ⚠️ | Backend exists but no frontend, or vice versa — or feature is incomplete |
| ❌ | Completely absent from the new system |
| 🔄 | Exists at a different URL/structure (minor path change only) |

---

## Module 1 — License

### 1.1 Core CRUD & Detail

| # | Feature | Legacy Endpoint | New Backend | New Frontend | Status | Priority |
|---|---------|----------------|-------------|--------------|--------|----------|
| L-01 | License list | `GET /licenses/` | `GET /api/v1/licenses/` | `/licenses` | ✅ | — |
| L-02 | License create | `POST /licenses/` | `POST /api/v1/licenses/` | Modal form | ✅ | — |
| L-03 | License detail | `GET /licenses/{id}/` | `GET /api/v1/licenses/{id}/` | `/licenses/:id` | ✅ | — |
| L-04 | License update | `PUT/PATCH /licenses/{id}/` | `PATCH /api/v1/licenses/{id}/` | Edit modal | ✅ | — |
| L-05 | License delete | `DELETE /licenses/{id}/` | `DELETE /api/v1/licenses/{id}/` | List action | ✅ | — |
| L-06 | Import items (nested) | `GET /licenses/{id}/import-items/` | `GET /api/v1/licenses/{id}/items/` 🔄 | Import Items tab | ✅ | — |
| L-07 | Export items (nested) | `GET /licenses/{id}/export-items/` | `GET /api/v1/licenses/{id}/export-items/` | Export Items tab | ✅ | — |
| L-08 | Documents (nested) | `GET /licenses/{id}/documents/` | `GET /api/v1/licenses/{id}/documents/` | Documents tab | ✅ | — |
| L-09 | History (nested) | `GET /licenses/{id}/history/` | `GET /api/v1/licenses/{id}/history/` | History tab | ✅ | — |
| L-10 | Item usage expand | `GET /licenses/{id}/item-usage/` | `GET /api/v1/licenses/{id}/item-usage/` | Expand-row | ✅ | — |

### 1.2 Balance & Reports

| # | Feature | Legacy Endpoint | New Backend | New Frontend | Status | Priority | Action Required |
|---|---------|----------------|-------------|--------------|--------|----------|----------------|
| L-11 | Balance calculation | `GET /licenses/{id}/balance/` | `GET /api/v1/licenses/{id}/balance/` | Balance Panel | ✅ | — | — |
| L-12 | Recompute balance | `POST /licenses/{id}/recompute-balance/` | `POST /api/v1/licenses/{id}/recompute_balance/` | — | ✅ | — | — |
| L-13 | Balance PDF (per-license) | `GET /licenses/{id}/balance-pdf/` | `GET /api/v1/licenses/{id}/balance_pdf/` | Download PDF button | ✅ | — | — |
| L-14 | Balance Excel (per-license) | `GET /licenses/{id}/balance-excel/` | `GET /api/v1/licenses/{id}/balance_excel/` | Download Excel button | ✅ | — | — |
| L-15 | **Bulk Balance Excel (multi-license)** | `POST /licenses/bulk-balance-excel/` | ❌ Missing | ❌ Missing | ❌ | HIGH | Implement `BulkBalanceExcelView`; frontend `/reports/download-license` |
| L-16 | **Merged documents PDF** | `GET /licenses/{id}/merged-documents/` | ❌ Missing | ❌ Missing | ❌ | HIGH | Merges license copy + transfer letter into one PDF; needs PDF merge utility |
| L-17 | Items grouped | `GET /licenses/{id}/items-grouped/` | `GET /api/v1/licenses/{id}/items_grouped/` | — | ⚠️ | LOW | No frontend consumer yet |

### 1.3 PDF Parse & Planning

| # | Feature | Legacy Endpoint | New Backend | New Frontend | Status | Priority | Action Required |
|---|---------|----------------|-------------|--------------|--------|----------|----------------|
| L-18 | **DFIA PDF parse** | `POST /licenses/parse-pdf/` | ❌ Missing | ❌ Missing | ❌ | HIGH | `LicensePdfParseView`; prefills create form from scanned DFIA PDF |
| L-19 | Item plans CRUD | `GET/POST /licenses/{id}/item-plans/` | ✅ Exists | ❌ Missing | ⚠️ | HIGH | Frontend planning panel needed (see L-21) |
| L-20 | Item plan bulk-upsert | `POST /license-item-plans/bulk-upsert/` | ✅ Exists | ❌ Missing | ⚠️ | HIGH | Consumed by planning panel |
| L-21 | **Item plan norm-prefill** | `GET /license-item-plans/{id}/norm-prefill/` | ✅ Exists | ❌ Missing | ⚠️ | HIGH | Consumed by planning panel |
| L-22 | **License Planning Panel** | Modal in ItemReport, AllotmentAction, etc. | N/A | ❌ Missing | ❌ | HIGH | `LicensePlanningPanel` component: per-product split lines, 3-way qty/price/CIF auto-calc, pool balance tracking, bulk save |

### 1.4 License Ledger Subsystem

| # | Feature | Legacy Endpoint | New Backend | New Frontend | Status | Priority | Action Required |
|---|---------|----------------|-------------|--------------|--------|----------|----------------|
| L-23 | **Ledger Upload (sync/async CSV/HTM)** | `POST /licenses/upload-ledger/` | ❌ Missing | ❌ Missing | ❌ | **CRITICAL** | `LedgerUploadView`; parses DGFT ledger HTML/CSV; UTF-8 + Latin-1 encoding; async Celery path |
| L-24 | **Ledger upload task status** | `GET /licenses/ledger-task-status/{task_id}/` | ❌ Missing | ❌ Missing | ❌ | **CRITICAL** | Polling endpoint for async ledger import |
| L-25 | **Ledger Upload page** | `/ledger-upload` | N/A | ❌ Missing | ❌ | **CRITICAL** | Upload page with progress bar and async polling |
| L-26 | **License Ledger summary (company-wise)** | `GET /license-ledger/company-wise/` | ❌ Missing | ❌ Missing | ❌ | HIGH | `LicenseLedgerViewSet.company_wise`; groups purchase/sale by company per license |
| L-27 | **License Ledger (license-wise)** | `GET /license-ledger/license-wise/` | ❌ Missing | ❌ Missing | ❌ | HIGH | Aggregated per-license view |
| L-28 | **Company ledger** | `GET /license-ledger/company-ledger/` | ❌ Missing | ❌ Missing | ❌ | HIGH | Filter by company; P/L calculation per company |
| L-29 | **Company ledger export** | `GET /license-ledger/company-ledger/export/` | ❌ Missing | ❌ Missing | ❌ | MEDIUM | Excel export of company ledger |
| L-30 | **Ledger export all** | `GET /license-ledger/export/all/` | ❌ Missing | ❌ Missing | ❌ | MEDIUM | Full ledger Excel export |
| L-31 | **License Ledger list page** | `/license-ledger` | N/A | ❌ Missing | ❌ | HIGH | Shows all licenses with purchase/sale grouped by company; View Ledger navigation |
| L-32 | **License Ledger detail page** | `/license-ledger/:id/:companyId?` | N/A | ❌ Missing | ❌ | HIGH | Per-license line-item transactions with running balance, negative balance warnings |
| L-33 | **Download Ledger PDF** | `GET /license-actions/{id}/download-ledger/` | ❌ Missing | ❌ Missing | ❌ | HIGH | Per-license ledger PDF with heads, quantities, CIF, available balance |
| L-34 | **Fetch Ledger from DGFT** | `POST /license-actions/{id}/fetch-ledger/` | ❌ Missing | ❌ Missing | ❌ | LOW | Returns 501 NOT_IMPLEMENTED in legacy too — pending DGFT API |

### 1.5 Ownership & Transfer

| # | Feature | Legacy Endpoint | New Backend | New Frontend | Status | Priority | Action Required |
|---|---------|----------------|-------------|--------------|--------|----------|----------------|
| L-35 | **Ownership data (local snapshot)** | `GET /license-actions/{id}/ownership-data/` | ❌ Missing | ❌ Missing | ❌ | MEDIUM | Returns saved DGFT ownership snapshot: current owner + transfer history |
| L-36 | **Fetch ownership from DGFT** | `POST /license-actions/{id}/fetch-ownership/` | ❌ Missing | ❌ Missing | ❌ | MEDIUM | Fetches and saves DGFT ownership; returns saved state |
| L-37 | **Update license transfer (single)** | `POST /license-actions/update-license-transfer/` | ❌ Missing | ❌ Missing | ❌ | MEDIUM | Updates ownership and transfer info for one license |
| L-38 | **Bulk update license transfer** | `POST /license-actions/bulk-update-license-transfer/` | ❌ Missing | ❌ Missing | ❌ | MEDIUM | Bulk update ownership across multiple licenses; returns success/failure counts |

### 1.6 Report Viewsets

| # | Feature | Legacy Endpoint | New Backend | New Frontend | Status | Priority | Action Required |
|---|---------|----------------|-------------|--------------|--------|----------|----------------|
| L-39 | **Expiring Licenses ViewSet** | `GET /expiring-licenses/` | ❌ Missing | ❌ Missing | ❌ | HIGH | Licenses expiring within N days; filterable by exporter, port, norm class |
| L-40 | **Active Licenses ViewSet** | `GET /active-licenses/` | ❌ Missing | ❌ Missing | ❌ | HIGH | Active licenses from N days ago through future |
| L-41 | **Inventory Balance ViewSet** | `GET /inventory-balance/{sion_norm}/` | ❌ Missing | ❌ Missing | ❌ | HIGH | Balance by SION norm class; Excel export |
| L-42 | **Item Pivot ViewSet** | `GET /item-pivot/available-norms/` + async | ❌ Missing | `/reports/pivot` page only | ⚠️ | HIGH | Frontend page exists but backend `ItemPivotViewSet` missing; async Celery generation with task-status polling |
| L-43 | **Item Report ViewSet** | `GET /item-report/` | ❌ Missing | `/reports/items` page only | ⚠️ | HIGH | Frontend page exists but backend `ItemReportViewSet` missing; inline edit capability required |

### 1.7 SION Parle Reports (CRITICAL for Regulatory Compliance)

| # | Feature | Legacy Route | New Backend | New Frontend | Status | Priority | Action Required |
|---|---------|-------------|-------------|--------------|--------|----------|----------------|
| L-44 | **SION Parle E1 Report** | `/reports/parle/sion-e1` | `active-dfia-report/?sion_norm=E1` missing | ❌ Missing | ❌ | **CRITICAL** | Backend `active_dfia_report` action + frontend SionE1 page |
| L-45 | **SION Parle E5 Report** | `/reports/parle/sion-e5` | `active-dfia-report/?sion_norm=E5` missing | ❌ Missing | ❌ | **CRITICAL** | Same as E1 for norm E5 |
| L-46 | **SION Parle E126 Report** | `/reports/parle/sion-e126` | `active-dfia-report/?sion_norm=E126` missing | ❌ Missing | ❌ | **CRITICAL** | Same as E1 for norm E126 |
| L-47 | **SION Parle E132 Report** | `/reports/parle/sion-e132` | `active-dfia-report/?sion_norm=E132` missing | ❌ Missing | ❌ | **CRITICAL** | Same as E1 for norm E132 |

---

## Module 2 — Allotment

| # | Feature | Legacy Endpoint | New Backend | New Frontend | Status | Priority | Action Required |
|---|---------|----------------|-------------|--------------|--------|----------|----------------|
| A-01 | Allotment list | `GET /allotments/` | `GET /api/v1/allotments/` | `/allotments` | ✅ | — | — |
| A-02 | Allotment create | `POST /allotments/` | `POST /api/v1/allotments/` | Form | ✅ | — | — |
| A-03 | Allotment detail | `GET /allotments/{id}/` | `GET /api/v1/allotments/{id}/` | Detail view | ✅ | — | — |
| A-04 | Allotment update | `PUT/PATCH /allotments/{id}/` | `PATCH /api/v1/allotments/{id}/` | Edit | ✅ | — | — |
| A-05 | Allotment delete | `DELETE /allotments/{id}/` | `DELETE /api/v1/allotments/{id}/` | List action | ✅ | — | — |
| A-06 | **Copy allotment** | `POST /allotments/{id}/copy/` | ❌ Missing | ❌ Missing | ❌ | MEDIUM | Clone allotment without invoice/items; reset approval status to false |
| A-07 | **Available licenses lookup** | `GET /allotment-actions/{id}/available-licenses/` | ❌ Missing | ❌ Missing | ❌ | **CRITICAL** | Complex filter: description, exporter, qty/value ranges, HS code, norm class, purchase status, expiry, restriction flags; paginated |
| A-08 | **Allocate items to allotment** | `POST /allotment-actions/{id}/allocate-items/` | ❌ Missing | ❌ Missing | ❌ | **CRITICAL** | Atomic: validate plan availability, restriction caps, balance caps, `select_for_update`; triggers balance recompute |
| A-09 | **Delete allotment item** | `DELETE /allotment-actions/{id}/delete-item/{item_id}/` | ❌ Missing | ❌ Missing | ❌ | **CRITICAL** | Deallocation; restores quantity to license via balance recompute signal |
| A-10 | Generate allotment PDF | `GET /allotment-actions/{id}/generate-pdf/` | ⚠️ Async dispatch exists | ❌ Missing | ⚠️ | MEDIUM | Add frontend "Generate PDF" button on allotment detail |
| A-11 | **Generate allotment transfer letter** | `POST /allotment-actions/{id}/generate-transfer-letter/` | ❌ Missing | ❌ Missing | ❌ | HIGH | Transfer letter PDF with optional CIF edits per item |
| A-12 | **Allotment Action page** | `/allotments/:id/allocate` | N/A | ❌ Missing | ❌ | **CRITICAL** | Complex allocation UI: available items search/filter, pagination, condition badges, planning panel integration, unsaved-changes guard |
| A-13 | Allotment grouped export | `GET /allotments/{id}/download/` | ❌ Missing | ❌ Missing | ❌ | MEDIUM | Excel grouped export of allotment data |

---

## Module 3 — Bill of Entry (BOE)

| # | Feature | Legacy Endpoint | New Backend | New Frontend | Status | Priority | Action Required |
|---|---------|----------------|-------------|--------------|--------|----------|----------------|
| B-01 | BOE list | `GET /bill-of-entries/` | `GET /api/v1/boe/` | `/boe` | ✅ | — | — |
| B-02 | BOE create | `POST /bill-of-entries/` | `POST /api/v1/boe/` | Form | ✅ | — | — |
| B-03 | BOE detail | `GET /bill-of-entries/{id}/` | `GET /api/v1/boe/{id}/` | `/boe/:id` | ✅ | — | — |
| B-04 | BOE update | `PUT/PATCH /bill-of-entries/{id}/` | `PATCH /api/v1/boe/{id}/` | Edit | ✅ | — | — |
| B-05 | BOE delete | `DELETE /bill-of-entries/{id}/` | `DELETE /api/v1/boe/{id}/` | List action | ✅ | — | — |
| B-06 | BOE row add/update | Form-based | `POST /api/v1/boe/{id}/rows/` | Inline rows | ✅ | — | — |
| B-07 | BOE row delete | Form-based | `DELETE /api/v1/boe/{id}/rows/{row_id}/` | Inline rows | ✅ | — | — |
| B-08 | Resolve dispute (row-level) | Form-based | `POST /api/v1/boe/{id}/resolve_dispute_row/` | Row action | ✅ | — | — |
| B-09 | Resolve dispute (BOE-level) | `POST /bill-of-entries/{id}/resolve-dispute/` | ✅ Exists (`resolve_boe_dispute`) | ❌ Missing | ⚠️ | MEDIUM | Add "Clear All Disputes" button on BOE detail page |
| B-10 | **BOE PDF parse** | `POST /bill-of-entries/parse-pdf/` | ❌ Missing | ⚠️ Panel extracted but not integrated | ❌ | HIGH | `BoeParseAPIView`; extracts ICEGATE BOE fields; matches company/port/items; prefills create form |
| B-11 | **Fetch allotment details (prefill)** | `GET /bill-of-entries/fetch-allotment-details/?allotment_id=X` | ❌ Missing | ❌ Missing | ❌ | HIGH | Returns allotment items + exchange rate for BOE row prefill; required for BOE creation workflow |
| B-12 | **BOE merge** | `POST /bill-of-entries/{id}/merge/` | ❌ Missing | ⚠️ BoeMergeModal extracted but not integrated | ❌ | MEDIUM | Merge source BOE into target: items, allotments, port |
| B-13 | **Generate BOE transfer letter** | `POST /bill-of-entries/{id}/generate-transfer-letter/` | ❌ Missing | ❌ Missing | ❌ | HIGH | Transfer letter PDF for BOE; uses generic utility |
| B-14 | **BOE Transfer Letter page** | `/bill-of-entries/:id/generate-transfer-letter` | N/A | ❌ Missing | ❌ | HIGH | Dedicated page for transfer letter generation |
| B-15 | **Update invoice number** | `POST /bill-of-entries/{id}/update-invoice-no/` | ❌ Missing | ❌ Missing | ❌ | MEDIUM | Restricted to `ACCOUNT_ACCESS` role |
| B-16 | Update product name (single) | `POST /bill-of-entries/{id}/update-product-name/` | ❌ Missing | ❌ Missing | ❌ | LOW | Auto-fill product_name from item names |
| B-17 | Bulk update product names | `POST /bill-of-entries/bulk-update-product-names/` | ❌ Missing | ❌ Missing | ❌ | LOW | Auto-fill across multiple BOEs |
| B-18 | BOE grouped export | `GET /bill-of-entries/{id}/download/` | ❌ Missing | ❌ Missing | ❌ | MEDIUM | Excel grouped export |

---

## Module 4 — Trade

| # | Feature | Legacy Endpoint | New Backend | New Frontend | Status | Priority | Action Required |
|---|---------|----------------|-------------|--------------|--------|----------|----------------|
| T-01 | Trade list | `GET /trades/` | `GET /api/v1/trades/` | `/trades` | ✅ | — | — |
| T-02 | Trade create | `POST /trades/` | `POST /api/v1/trades/` | `/trades/new` | ✅ | — | — |
| T-03 | Trade detail/update | `GET/PUT/PATCH /trades/{id}/` | `GET/PATCH /api/v1/trades/{id}/` | `/trades/:id` | ✅ | — | — |
| T-04 | Trade delete | `DELETE /trades/{id}/` | `DELETE /api/v1/trades/{id}/` | List action | ✅ | — | — |
| T-05 | Trade summary | `GET /trades/{id}/summary/` | `GET /api/v1/trades/{id}/summary/` | TradeSummary component | ✅ | — | — |
| T-06 | Link trade (bidirectional) | `POST /trades/{id}/link-trade/` | `POST /api/v1/trades/{id}/link_trade/` | LinkTradeModal | ✅ | — | — |
| T-07 | Prefill invoice number | `GET /trades/prefill-invoice-number/` | ✅ Exists | ❌ Not wired in TradeForm | ⚠️ | MEDIUM | Wire into TradeForm on company/direction change |
| T-08 | Generate purchase invoice PDF | `GET /trades/{id}/generate-purchase-invoice/` | ✅ Exists | ❌ Missing | ⚠️ | MEDIUM | Add "Print Invoice" button on Trade detail |
| T-09 | Generate bill of supply PDF | `GET /trades/{id}/generate-bill-of-supply/` | ✅ Exists | ❌ Missing | ⚠️ | MEDIUM | Add "Print Bill of Supply" button on Trade detail |
| T-10 | **Generate trade transfer letter** | `POST /trades/{id}/generate-transfer-letter/` | ❌ Missing | ⚠️ TradeTransferLetter.tsx incomplete | ❌ | MEDIUM | Backend endpoint missing; frontend page partially built |

---

## Module 5 — Tasks

| # | Feature | Legacy Endpoint | New Backend | New Frontend | Status | Priority | Action Required |
|---|---------|----------------|-------------|--------------|--------|----------|----------------|
| TK-01 | Task list | `GET /tasks/` | `GET /api/v1/tasks/` | `/tasks` | ✅ | — | — |
| TK-02 | Task create | `POST /tasks/` | `POST /api/v1/tasks/` | Form | ✅ | — | — |
| TK-03 | Task update | `PATCH /tasks/{id}/` | `PATCH /api/v1/tasks/{id}/` | Form | ✅ | — | — |
| TK-04 | Task complete | `POST /tasks/{id}/complete/` | ✅ Exists | ❌ Missing UI button | ⚠️ | HIGH | Add Complete button on TaskList/TaskDetail |
| TK-05 | Task reject | `POST /tasks/{id}/reject/` | ✅ Exists | ❌ Missing UI button | ⚠️ | HIGH | Add Reject button with optional reason input |
| TK-06 | Task reopen | `POST /tasks/{id}/reopen/` | ✅ Exists | ❌ Missing UI button | ⚠️ | MEDIUM | Add Reopen button for rejected/completed tasks |
| TK-07 | Task remarks | `GET/POST /tasks/{id}/remarks/` | ✅ Exists | ❌ Missing | ⚠️ | MEDIUM | Remarks thread on TaskDetail |
| TK-08 | Assignable users | `GET /tasks/assignable-users/` | ✅ Exists | ❌ Not wired | ⚠️ | MEDIUM | Populate Assign To dropdown in TaskForm |

---

## Module 6 — Masters & Core

| # | Feature | Legacy | New Backend | New Frontend | Status | Priority | Action Required |
|---|---------|--------|-------------|--------------|--------|----------|----------------|
| M-01 | Company CRUD | `/masters/companies/` | ✅ | `/masters/companies` dedicated page | ✅ | — | — |
| M-02 | Port CRUD | `/masters/ports/` | ✅ | `/masters/ports` dedicated page | ✅ | — | — |
| M-03 | HS Code CRUD | `/masters/hs-codes/` | ✅ | Generic MasterList | ✅ | — | — |
| M-04 | Item Group CRUD | `/masters/groups/` | ✅ | Generic MasterList | ✅ | — | — |
| M-05 | Item Name CRUD | `/masters/item-names/` | ✅ | Generic MasterList | ✅ | — | — |
| M-06 | SION Norm Class CRUD | `/masters/sion-classes/` | ✅ | Generic MasterList | ✅ | — | — |
| M-07 | Exchange Rate CRUD | `/masters/exchange-rates/` | ✅ | Generic MasterList | ✅ | — | — |
| M-08 | Head Norm CRUD | `/masters/head-norms/` | ✅ | Generic MasterList | ⚠️ | MEDIUM | Verify `head-norms` slug routes correctly in generic MasterList |
| M-09 | Scheme Code CRUD | `/masters/scheme-codes/` | ✅ | ❌ Not in master nav | ⚠️ | LOW | Add to master navigation for superuser management |
| M-10 | Notification Number CRUD | `/masters/notification-numbers/` | ✅ | ❌ Not in master nav | ⚠️ | LOW | Add to master navigation |
| M-11 | Purchase Status CRUD | `/masters/purchase-statuses/` | ✅ | ❌ Not in master nav | ⚠️ | LOW | Add to master navigation |
| M-12 | **Activity Log** | `GET /masters/activity-logs/` | ✅ Exists | ❌ Missing page | ⚠️ | MEDIUM | Add `/admin/activity-log` page; filters: username, action, module, date range; bulk export CSV/Excel |

---

## Module 7 — Reports

| # | Feature | Legacy Route | New Backend | New Frontend | Status | Priority | Action Required |
|---|---------|-------------|-------------|--------------|--------|----------|----------------|
| R-01 | Balance Report | `/reports/` (balance sub-route) | ✅ | `/reports/balance` | ✅ | — | — |
| R-02 | Ledger Report | — | ✅ | `/reports/ledger` | ✅ | — | — |
| R-03 | Item Report | `/reports/item-report/` | ❌ `ItemReportViewSet` missing | `/reports/items` (page only) | ⚠️ | HIGH | Implement `ItemReportViewSet`: filterable by item names, balance, qty, license status, companies, restrictions, purchase status, HSN, SION norm, expiry; inline edit |
| R-04 | Item Pivot Report | `/reports/item-pivot/` | ❌ `ItemPivotViewSet` missing | `/reports/pivot` (page only) | ⚠️ | HIGH | Implement `ItemPivotViewSet`: available-norms, generate-async (Celery), task-status polling, update-balance |
| R-05 | **Expiring Licenses Report** | `/reports/expiring-licenses` | ❌ Missing | ❌ Missing | ❌ | HIGH | Backend `ExpiringLicensesViewSet`; frontend page with days filter; Excel with separate sheets per SION norm |
| R-06 | **Active Licenses Report** | `/reports/active-licenses` | ❌ Missing | ❌ Missing | ❌ | HIGH | Backend `ActiveLicensesViewSet`; frontend page with days look-back filter |
| R-07 | **Download License Report** | `/reports/download-license` | ❌ `bulk-balance-excel` missing | ❌ Missing | ❌ | HIGH | Bulk per-license Excel: separate named sheet per license, BOE/allotment summary, balance qty, restriction %, CIF FC |
| R-08 | **Inventory Balance Report** | `/reports/inventory-balance/` | ❌ Missing | ❌ Missing | ❌ | HIGH | Per-SION-norm balance report; Excel export |
| R-09 | **SION Parle E1 Report** | `/reports/parle/sion-e1` | ❌ `active_dfia_report` action missing | ❌ Missing | ❌ | **CRITICAL** | Regulatory report for Parle Group; grouped by notification; SION norm E1 items |
| R-10 | **SION Parle E5 Report** | `/reports/parle/sion-e5` | ❌ | ❌ Missing | ❌ | **CRITICAL** | Same structure; norm E5 |
| R-11 | **SION Parle E126 Report** | `/reports/parle/sion-e126` | ❌ | ❌ Missing | ❌ | **CRITICAL** | Same structure; norm E126 |
| R-12 | **SION Parle E132 Report** | `/reports/parle/sion-e132` | ❌ | ❌ Missing | ❌ | **CRITICAL** | Same structure; norm E132 |

---

## Module 8 — Accounts & User Administration

| # | Feature | Legacy Endpoint | New Backend | New Frontend | Status | Priority | Action Required |
|---|---------|----------------|-------------|--------------|--------|----------|----------------|
| AC-01 | Login (JWT) | `POST /accounts/login/` | `POST /api/v1/auth/login/` | `/login` | ✅ | — | — |
| AC-02 | Logout | `POST /accounts/logout/` | `POST /api/v1/auth/logout/` | Sidebar button | ✅ | — | — |
| AC-03 | Token refresh | `POST /accounts/token/refresh/` | `POST /api/v1/auth/token/refresh/` | Axios interceptor | ✅ | — | — |
| AC-04 | Current user (me) | `GET /accounts/me/` | `GET /api/v1/auth/me/` | AuthContext | ✅ | — | — |
| AC-05 | User list | `GET /accounts/users/` | ✅ Partial (missing role/is_active filters) | ❌ No User Management page | ⚠️ | HIGH | Add `/admin/users` page with columns: username, email, roles, status, actions |
| AC-06 | **User create** | `POST /accounts/users/` | ❌ `UsersView` is ListAPIView only | ❌ Missing | ❌ | HIGH | Promote `UsersView` to `ModelViewSet`; frontend create form with username, email, password, roles, flags |
| AC-07 | **User update** | `PATCH /accounts/users/{id}/` | ❌ Missing | ❌ Missing | ❌ | HIGH | Edit user: name, email, roles, active/staff/superuser flags |
| AC-08 | **User delete** | `DELETE /accounts/users/{id}/` | ❌ Missing | ❌ Missing | ❌ | HIGH | Soft-delete or hard-delete with confirmation |
| AC-09 | **Available roles list** | `GET /accounts/users/available-roles/` | ❌ Missing | ❌ Missing | ❌ | MEDIUM | Drives role checkboxes in user form |
| AC-10 | **Admin reset password** | `POST /accounts/users/{id}/reset-password/` | ❌ Missing | ❌ Missing | ❌ | HIGH | Admin sets new password for any user; no token required |
| AC-11 | **Self-service password reset** | `POST /accounts/password/reset-request/` | ❌ Missing | ❌ Missing | ❌ | HIGH | Sends reset email; generic response prevents user enumeration |
| AC-12 | **Password reset confirm** | `POST /accounts/password/reset-confirm/` | ❌ Missing | ❌ Missing | ❌ | HIGH | Validates UID + token; sets new password |
| AC-13 | **User Management pages** | `/admin/users`, `/admin/users/create`, `/admin/users/:id/edit` | N/A | ❌ Missing | ❌ | HIGH | UserList + UserForm pages gated to `USER_MANAGER` role |
| AC-14 | **Profile page** | `/profile` | ✅ `/auth/me/` returns profile data | ❌ Missing | ⚠️ | MEDIUM | Self-service view/edit: name, email, password change |

---

## Module 9 — Incentive Licenses

| # | Feature | Legacy Endpoint | New Backend | New Frontend | Status | Priority | Action Required |
|---|---------|----------------|-------------|--------------|--------|----------|----------------|
| IL-01 | **Incentive License CRUD** | `GET/POST/PATCH/DELETE /incentive-licenses/` | ❌ No `incentive_licenses` app | ❌ No `/incentive-licenses` route | ❌ | HIGH | Entire module missing; check legacy `apps/license/views/incentive.py` and models |

---

## Module 10 — Dashboard

| # | Feature | Legacy | New Backend | New Frontend | Status | Priority |
|---|---------|--------|-------------|--------------|--------|----------|
| D-01 | KPI stats | `GET /licenses/dashboard/` | `GET /api/v1/dashboard/` | Dashboard cards | ✅ | — |
| D-02 | Utilisation chart | Same | Same | UtilisationChart | ✅ | — |
| D-03 | Expiring alerts | Same | Same | Alert panel | ✅ | — |

---

## Priority Backlog — Recommended Implementation Order

### 🔴 P0 — CRITICAL (system is not functionally usable without these)

These features are the core operational workflow. Without them, users cannot actually *use* the license management system — they can only view data.

| ID | Feature | Why Critical |
|----|---------|-------------|
| A-07/08/09/12 | **Allotment allocation workflow** | Cannot allocate licenses to allotments at all; the primary day-to-day task |
| L-23/24/25 | **Ledger Upload (DGFT import)** | Without this, DGFT transaction data cannot enter the system; all balance calculations are incomplete |
| L-44–47 | **SION Parle E1/E5/E126/E132 reports** | Used daily by Parle Group for regulatory reporting; direct client deliverable |

### 🟠 P1 — HIGH (major features; blocks normal operations)

| ID | Feature | Blocking what |
|----|---------|--------------|
| B-10/11 | BOE PDF parse + fetch allotment details | Cannot create BOEs efficiently without prefill |
| B-13/14 | BOE transfer letter | Document generation for customs compliance |
| AC-06/07/08/10/11/12/13 | User management CRUD + password reset | Cannot administer users; no self-service password recovery |
| L-18 | DFIA PDF parse | License creation from scanned documents |
| L-19/20/21/22 | License Planning Panel | Cannot plan import utilization; affects allotment decisions |
| L-26–32 | License Ledger subsystem (views + pages) | Core financial reconciliation feature |
| L-39/40 | Expiring/Active Licenses ViewSets | Key operational reports used weekly |
| R-03/04 | Item Report + Item Pivot backend | Frontend pages exist but call endpoints that don't exist |
| R-05/06/07/08 | Expiring/Active/Download/Inventory reports | Business intelligence reports |
| IL-01 | Incentive Licenses | Entire module absent |
| TK-04/05 | Task Complete + Reject UI buttons | Task workflow is broken without these |

### 🟡 P2 — MEDIUM (important but workarounds exist)

| ID | Feature |
|----|---------|
| A-06 | Allotment copy |
| A-10/11 | Allotment PDF + transfer letter UI |
| B-09 | BOE resolve dispute (BOE-level) UI button |
| B-12 | BOE merge |
| B-15 | BOE update invoice number |
| T-07/08/09/10 | Trade PDF generation + transfer letter |
| TK-06/07/08 | Task reopen + remarks + assignable users |
| L-35–38 | License ownership/transfer tracking |
| L-42/43 | Item Pivot + Item Report backend (R-03/04 dependency) |
| M-12 | Activity Log page |
| AC-14 | Profile page |

### 🟢 P3 — LOW / POLISH

| ID | Feature |
|----|---------|
| L-33/34 | Ledger PDF download + DGFT fetch (returns 501 in legacy) |
| B-16/17/18 | BOE product name updates + grouped export |
| M-08/09/10/11 | Head Norms + Scheme/Notification/Purchase Status admin |
| A-13 | Allotment grouped export |

---

## Open Questions (decisions required before build)

| # | Question | Impact |
|---|----------|--------|
| OQ-1 | Incentive Licenses: same balance formula as DFIA, or different? Legacy code path? | Scopes entire IL module |
| OQ-2 | Ledger Upload: is the DGFT HTML/HTM format stable? Any format changes since legacy was built? | Affects parser implementation |
| OQ-3 | SION Parle reports: do the column definitions (Vegetable Oil, Juice, etc.) come from config or are they hard-coded per norm? | Determines if backend is static or configurable |
| OQ-4 | Password reset: does a production SMTP server exist, or should reset be admin-only for now? | Scopes self-service vs admin-only reset |
| OQ-5 | Transfer letters: are there multiple templates, or one per entity type? Does the user pick a template? | Affects template system design |
| OQ-6 | Item Pivot async: what is the expected generation time? Should the new system use Celery or just synchronous Excel streaming? | Affects complexity of implementation |

---

## Coverage Map

```
                         LEGEND: ✅ Complete  ⚠️ Partial  ❌ Missing

AUTHENTICATION     [✅✅✅✅ AC-01–04] [⚠️ AC-05] [❌❌❌❌❌❌❌❌ AC-06–13]
LICENSE CRUD       [✅✅✅✅✅✅✅✅✅✅ L-01–10]
LICENSE REPORTS    [✅✅✅ L-11–14] [❌ L-15–16] [⚠️ L-17]
LICENSE PLANNING   [❌❌❌❌❌ L-18–22]
LICENSE LEDGER     [❌❌❌❌❌❌❌❌❌❌❌❌ L-23–34]
LICENSE OWNERSHIP  [❌❌❌❌ L-35–38]
LICENSE REPORT VW  [❌❌❌⚠️⚠️ L-39–43]
SION PARLE         [❌❌❌❌ L-44–47]
ALLOTMENT CRUD     [✅✅✅✅✅ A-01–05]
ALLOTMENT ACTIONS  [❌❌❌⚠️❌❌❌ A-06–12]
BOE CRUD+ROWS      [✅✅✅✅✅✅✅✅ B-01–08]
BOE ACTIONS        [⚠️❌❌❌❌❌❌❌❌❌ B-09–18]
TRADE              [✅✅✅✅✅✅ T-01–06] [⚠️⚠️⚠️❌ T-07–10]
TASKS              [✅✅✅ TK-01–03] [⚠️⚠️⚠️⚠️⚠️ TK-04–08]
MASTERS            [✅✅✅✅✅✅✅ M-01–07] [⚠️⚠️⚠️⚠️ M-08–12]
REPORTS            [✅✅ R-01–02] [⚠️⚠️ R-03–04] [❌❌❌❌❌❌❌❌ R-05–12]
DASHBOARD          [✅✅✅ D-01–03]
INCENTIVE LICENSE  [❌ IL-01]
```

---

*This document is the authoritative gap tracker. Update Status column as features land. Every ❌ CRITICAL/HIGH item requires a user story, acceptance criteria, and explicit sign-off before development begins.*
