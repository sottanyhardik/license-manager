# System Module Map — License Manager
**Discovery Date:** 2026-08-10  
**Status:** Authoritative mapping from code analysis (agents: backend-engineer, data-scientist, frontend-engineer)  
**Validation:** All module boundaries verified against actual imports, models, URL routes, React routes  

---

## SYSTEM OVERVIEW

The License Manager is organized into **11 business modules** distributed across **8 Django apps** + **1 frontend SPA**. Modules correspond to business domains, NOT file structure.

### Module List (Priority Order)

| # | Module | Business Purpose | Scale | Risk | Status |
|---|--------|---|-------|------|--------|
| 1 | **Core/Foundation** | Authentication, master data, shared utilities | Small | Low | Stable (recent SEC fixes) |
| 2 | **License Management** | DFIA license entity, attributes, lifecycle | Large | Medium | Modernizing (Phase 2B complete) |
| 3 | **License Ledger** | Transaction history, running balance, PDF/Excel | Large | **HIGH** | In Progress (Phase 3) |
| 4 | **License Balance** | Balance calculation, availability, restrictions | Medium | **CRITICAL** | Active (balance_calculator hot path) |
| 5 | **Planning** | Manual + auto-planning, norms, allocations | Large | **HIGH** | Modernizing (A3627 new) |
| 6 | **Allotment** | Procurement order, item allocation | Medium | Medium | Stable |
| 7 | **Bill of Entry** | Customs import document, line items | Medium | Medium | Stable |
| 8 | **Invoice/Trade** | Purchase/sale transactions, financial tracking | Large | Medium | Active |
| 9 | **Reconciliation** | Invoice-BOE matching, allocation ledgers | Medium | **HIGH** | Stable (but complex) |
| 10 | **Reports & Exports** | Dashboards, ledger, pivot, Excel/PDF | Large | **HIGH** | Modernizing (Phase 2B in progress) |
| 11 | **Administration** | Users, audit logs, settings | Small | Low | Stable |

---

## DETAILED MODULE BREAKDOWN

### MODULE 1: CORE / FOUNDATION
**Files:** `backend/apps/core/`  
**Purpose:** Infrastructure, authentication, master data, utilities  

**Components:**
- **Authentication:** JWT + session auth, password reset, token refresh
- **Master Data:** Company, Port, HS Code, Item, SION norms, exchange rates
- **Utilities:** Caching, filters, exporters, PDF/Excel builders, decimal utilities
- **Materialized Views:** `license_balance_mv`, `item_balance_mv`, `dashboard_stats_mv` (NOT scheduled in Celery Beat — **P1 risk**)
- **Management Commands:** 20+ (auto-import, reconcile, refresh views, etc.)
- **Permissions:** 10+ role-based permission classes

**Database Tables:**
- `accounts_user`, `core_company`, `core_port`, `core_hscodmodel`, `core_itemname`, `core_sionormclass`
- `core_exchangerate`, `core_transferletter`, `core_purchasestatus`, `core_schemecode`
- `core_activitylog` (append-only audit trail)

**API Endpoints:** ~20 (master CRUD, health check, activity log, throttle status)

**Frontend:** Login, profile, settings, masters list (generic table)

**Risk:** Low (mature, stable, recent security fixes)  
**Tech Debt:** Materialized views not scheduled (quick fix: 2 hours)  
**Status:** STABLE

---

### MODULE 2: LICENSE MANAGEMENT
**Files:** `backend/apps/license/` (primary), `frontend/src/pages/license-*`  
**Purpose:** DFIA license entity, attributes, lifecycle, document management  

**Core Models:**
- `LicenseDetailsModel` — Main license header (license_number, expiry, status)
- `LicenseExportItemModel` — Export restrictions (SION, qty, value)
- `LicenseImportItemsModel` — Import credit items (SRs), balance fields
- `LicenseBalance` (OneToOne, cached) — Balance CIF snapshot
- `LicenseFlags`, `LicenseNotes`, `LicenseOwnership` (OneToOne metadata)
- `LicenseTransfer`, `LicensePurchase` — Ownership/purchase history

**Services (Critical):**
- `balance_calculator.py` (43 dependents) — **HOTTEST PATH** — calculates balance_cif, available_qty/cif, handles BOE representation, allotment deduction
- `condition_pool.py` — Condition-based restrictions (N%, AU)
- `plan_grouping.py` — Item grouping for planning
- `validation_service.py` — Business rule enforcement

**Views/APIs:**
- `LicenseDetailsViewSet` — CRUD + custom actions (balance-pdf, balance-excel, nested-items, parse-pdf)
- License item management
- Document management
- Ownership fetching (DGFT scraping)

**Frontend:**
- License list (search, filters, pagination)
- License detail (tabs: overview, items, documents, ownership)
- License create/edit form
- License transfer dialog

**Database Tables:**
- `license_licensedetails`, `license_licenseexportitem`, `license_licenseimportsmodel`
- `license_licensebalance`, `license_licenseflags`, `license_licensenotes`, `license_licenseownership`
- `license_licensedomcumentmodel`, `license_licensetransfer`, `license_licensepurchase`

**Risk:** Medium (complex business logic, active modernization)  
**Tech Debt:** 
- Balance calculator has complex Case/When subqueries (performance risk)
- Parse PDF functionality (DFIA extraction) is brittle
- Export item management underused in UI

**Status:** MODERNIZING (Phase 2B export consistency work completed; Phase 2B.2B notification summary migration in progress)

---

### MODULE 3: LICENSE LEDGER
**Files:** `backend/apps/license/views/ledger.py`, `backend/apps/license/services/exporters/ledger_pdf.py`, `frontend/src/pages/LicenseLedgerDetail.tsx`, `frontend/src/utils/ledgerExport.js`  
**Purpose:** Transaction history, running balance view, PDF/Excel export  

**Core Models:**
- No dedicated ledger models (uses RowDetails + calculations)
- Ledger data built dynamically from: License + ExportItems + RowDetails + Trades + Allocations

**Builders:**
- `build_dfia_ledger_detail()` (in ledger_pdf.py) — DFIA license ledger (~250 lines, **zero tests**)
- `build_incentive_ledger_detail()` — RODTEP/ROSTL/MEIS ledger (~300 lines, **zero tests**)
- `LicenseLedgerDetailViewSet.ledger_detail()` — JSON API endpoint

**Exports:**
- PDF via `ledger_pdf.py` (backend, jinja2 template)
- Excel via `ledgerExport.js` (frontend, ExcelJS)
- Browser display via `LicenseLedgerDetail.tsx`

**Critical Issue — P0 DEFECT:**
All three (page, PDF, Excel) show **DIFFERENT RUNNING BALANCES** for the same license/transactions:
- **Backend (ledger_pdf.py):** License-wide running balance (PURCHASE→SALE order, COMMISSION_SALE debits)
- **Frontend (LicenseLedgerDetail.tsx + ledgerExport.js):** Per-company running balance (restarts per company, COMMISSION excluded)
- **Root:** Two legitimate conventions, not a code bug — **requires business decision**
- **Phase 3 Status:** Design doc complete, awaiting business approval (§10 B2 decision gate)
- **Test Coverage:** Zero characterization tests for both builders

**Frontend Components:**
- `LicenseLedgerDetail.tsx` (509 lines) — Page view with filters, inline calculations
- `ledgerExport.js` (825 lines) — PDF/Excel generation with running balance loops
- `LicenseLedger.tsx` (46 lines) — Summary list view

**Risk:** **HIGH** (user-visible defect, active design work, zero tests for 550 lines of balance logic)  
**Tech Debt:**
- Builders have no tests (Phase 3D required)
- Running balance calculation duplicated in 3 places (page + PDF + Excel)
- No golden-master validation
- Prior hypothesis (backend balance wrong) disproven — issue is semantic

**Status:** IN PROGRESS (Phase 3 design, awaiting business decision)

---

### MODULE 4: LICENSE BALANCE
**Files:** `backend/apps/license/services/balance_calculator.py` (primary)  
**Purpose:** Calculate available balance, plan capacity, debit tracking, financial reconciliation  

**Core Calculation:**
```
Balance CIF = Opening + Purchase - Sale - BOE_Debit - Allotment
Opening Gate = (if hidden BOEs) Credit - hidden - purchase ELSE (if purchased) 0 ELSE Credit
BOE Debit (per-row) = max(cif_fc - matched_allocations, 0)  [allocation-driven, not binary]
```

**Services:**
- `LicenseBalanceCalculator.calculate_financial_balance_for_licenses()` — Authoritative owner
- Calculates: balance_cif, available_quantity, available_value, debited_qty/value, allotted_qty/value

**Models Using Balance:**
- `LicenseBalance` (cached snapshot, updated via signals)
- `LicenseImportItemsModel` (item-level balances)

**Signals Triggering Recalc:**
- AllotmentItems post_save/post_delete
- RowDetails post_save/post_delete
- LicenseTradeLine post_save/post_delete

**Frontend:**
- Displayed in license detail, ledger, item pivot, all reports
- Balance modal in allotment dialog (live calculation)

**API:**
- Calculated on-demand for license list/detail views
- Cached in `license_balance` table (updated via signal)

**Risk:** **CRITICAL** (hot path, 43 dependents, complex SQL, signal-driven consistency)  
**Performance Issues:**
- Case/When subqueries in `get_debit_rows()` slow on large BOE sets
- Called on every license list view (potential N+1 if not optimized)
- No caching beyond signal invalidation

**Tech Debt:**
- Opening gate logic could use comments (complex rule)
- BOE representation logic (two mechanisms: legacy M2M + formal allocation ledger)

**Status:** ACTIVE (recent fixes: 2026-08-08, balance calculator refactoring)

---

### MODULE 5: PLANNING
**Files:** `backend/apps/license/services/{e1,e5,e126,e132,a3627}_auto_plan.py`, `backend/apps/license/services/plan_grouping.py`, `frontend/src/pages/*/planning/`  
**Purpose:** Manual + auto-planning, SION norm allocation, item grouping  

**Core Models:**
- `LicenseItemPlan` — Per-item plan records (quantity, CIF, norms)

**Planning Engines:**
| Engine | SION | Scope | Status |
|--------|------|-------|--------|
| E1 | E1 (confectionery) | Manual allocation by item | Stable |
| E5 | E5 (oils/wheat) | Auto-planning with unit price constraints | Stable |
| E126 | E126 | Specialized rules | Stable |
| E132 | E132 (milk) | Multi-variant (SWP/DWP/WPC prices) | Stable |
| **A3627** | A3627 (glass/ceramics) | **NEW** 4-priority waterfall (RUTILE→TITANIUM→SODA→PP) | **Active** (committed 2026-08) |

**Core Service: `plan_grouping.py`**
- Merge items for planning: HSN + normalized description
- Group key: `"{norm_hsn}|{norm_desc}"` where norm() = trim + upper + collapse + no-spaces-around-slash
- Allocate per category, persist on lowest-serial representative

**Critical Invariant:**
```
TOTAL_PLANNED_USAGE <= TOTAL_AVAILABLE_BALANCE
```
Enforced at:
- Frontend: client-side validation in plan editor
- Backend: `plan_enforcement.py` validation before save
- API: plan update endpoint (400 if violated)

**Frontend:**
- `PlanningEditor.tsx` (62KB) — Timeline visualization, manual edit, auto-plan triggers
- `InlineNormEditor.tsx` — Edit SION norms inline in item pivot

**APIs:**
- `LicenseItemPlanViewSet` — CRUD + `auto_plan()` action
- `plan_utilization` endpoints

**Risk:** **HIGH** (complex waterfall logic, new A3627 planner needs validation, plan cap enforcement critical)  
**Tech Debt:**
- A3627 planner (committed but not verified against real data)
- Price selection logic (USD 3.00 threshold) needs business validation
- Plan grouping normalization could have edge cases

**Status:** MODERNIZING (A3627 new, Phase 2B.2B notification summary fixes applied)

---

### MODULE 6: ALLOTMENT
**Files:** `backend/apps/allotment/`  
**Purpose:** Procurement allotment orders, item allocation quantities  

**Core Models:**
- `AllotmentModel` — Order header (supplier, qty, value, CIF, exchange rate)
- `AllotmentItems` — Line items (qty, CIF per item, BOE indicator)

**Services:**
- `allocation_service.py` — Allocate to items, validate capacity, deduct from balance
- `validation_service.py` — Allotment completeness, within-limit checks
- `filter_service.py` — Get available items for allocation

**APIs:**
- `AllotmentViewSet` — CRUD + `available_licenses`, `allocate_items` actions
- `AllotmentActionViewSet` — Copy allotment, PDF generation

**Frontend:**
- Allotment list (search, status, company filter)
- Allotment detail (items grid, available licenses modal)
- Allotment create/edit form

**Database Tables:**
- `allotment_allotmentmodel`, `allotment_allotmentitems`

**Risk:** Medium (simple domain, signal-driven balance updates)  
**Tech Debt:** None identified  
**Status:** STABLE

---

### MODULE 7: BILL OF ENTRY (BOE)
**Files:** `backend/apps/bill_of_entry/`  
**Purpose:** Customs import document (BOE), line items (RowDetails)  

**Core Models:**
- `BillOfEntryModel` — BOE header (invoice_no, date, port, company, M2M to allotments)
- `RowDetails` — Line items (qty, CIF, status, frozen flag, transaction_type DEBIT/CREDIT)

**Services:**
- `boe_service.py` — BOE operations (update product name, resolve disputes, merge BOE, hide/restore)

**Key Feature: Hidden BOE Marker**
- `invoice_no = "OTH"` marks BOE as legacy free-text
- Latest `ReconciliationLog.action` entry determines actual visibility (HIDE_BOE vs RESTORE_BOE)
- ~35–40% of BOEs carry "OTH" as legacy data

**APIs:**
- `BillOfEntryViewSet` — CRUD + custom actions
- `BOEPdfParseView` — Extract invoice details from PDF

**Frontend:**
- BOE list (search, filters, hidden status indicator)
- BOE detail (line items, allotment links, invoice linking)
- BOE create/edit form
- BOE PDF parser (upload → auto-fill)

**Database Tables:**
- `bill_of_entry_billofentrymodel`, `bill_of_entry_rowdetails`

**Risk:** Medium (hidden BOE marker logic, PDF parsing brittle)  
**Tech Debt:** PDF parser could fail on non-standard invoices  
**Status:** STABLE

---

### MODULE 8: INVOICE / TRADE
**Files:** `backend/apps/trade/`  
**Purpose:** Purchase/sale transactions, financial tracking, invoice generation  

**Core Models:**
- `LicenseTrade` — Transaction header (invoice, from/to companies, subtotal, M2M to BOEs)
- `LicenseTradeLine` — DFIA line items (SR link, qty, rate, amount)
- `IncentiveTradeLine` — Incentive scheme lines (license, amount)
- `LicenseTradePayment` — Payment records

**Services:**
- `trade_service.py` — Auto-prefill invoice number, build summary, link trades, stamp BOE

**Key Feature: Paired Trades**
- PURCHASE → auto-create corresponding SALE for commission tracking
- `linked_trade` field links them

**APIs:**
- `LicenseTradeViewSet` — CRUD + `generate_bill_of_supply`, `generate_purchase_invoice`, `link_trade` actions
- Nested: trade lines, payments, BOE links

**Frontend:**
- Trade list (search, type filter, date range)
- Trade detail (line items, payments, linked BOE)
- Trade create/edit form (complex: auto-calculate financials, link BOEs, nested lines)
- Transfer letter generation

**Database Tables:**
- `trade_licensetrade`, `trade_licensetradeline`, `trade_incentivetradeline`, `trade_licensetradepa yment`

**Risk:** Medium (complex nested create/update, paired trade logic, financial calculations)  
**Tech Debt:** TradeForm at 92KB (complex, not yet decomposed)  
**Status:** STABLE

---

### MODULE 9: RECONCILIATION
**Files:** `backend/apps/reconciliation/`  
**Purpose:** Validate and reconcile BOE-invoice relationships, allocation ledgers  

**Core Models (Three Independent Ledgers):**
1. **InvoiceBOEAllocation** — Which invoice line "explains" which BOE row
   - Fields: trade_line (PROTECT), row_details (PROTECT), qty/cif allocated, status (ACTIVE/REVERSED)
   - Ledger semantics: superseded_by (self FK), is_current, version
2. **BOEAllotmentAllocation** — Which allotment "sources" which BOE row
   - Fields: allotment_item (PROTECT), row_details (PROTECT), qty/cif allocated
   - Ledger semantics: same as above
3. **ExternalInvoiceLink** — Non-system invoice reference
   - Fields: row_details (PROTECT), invoice_number (text), qty/cif
   - Markers: ACTIVE/REVERSED, is_current

**Services:**
- `queries.py` — Detection queries (missing_boe, missing_invoice, duplicate_*, cif_comparison, qty_comparison)
- `allocation_service.py` — Create/reverse allocations, prevent over-allocation
- `boe_link_reconciler.py` — Auto-link BOEs to invoices
- `warning_service.py` — Manage ignored warnings

**IgnoredWarning Model:**
- Per-license warning suppression (warning_type, entity_type, entity_id)
- **NOT append-only** — mutated in-place (ignored boolean)
- Audit fields: ignored_by, ignored_at, restored_by, restored_at

**APIs:**
- `ReconciliationViewSet` — Read-only queries (summary, missing_boe, duplicate_*, cif_comparison, etc.)
- Write actions (link, merge_boe, note, recalculate) require BOTH trade + BOE manager roles

**Frontend:**
- Reconciliation panel (5 detection tabs: missing BOE, missing invoice, duplicates, etc.)
- Reconciliation issues page (portfolio-wide discovery)
- Link trade-to-BOE dialog

**Risk:** **HIGH** (complex allocation ledger logic, PROTECT constraints critical, allocation over-prevention relies on service validation not DB constraints)  
**Tech Debt:**
- IgnoredWarning is mutated (should be append-only with soft-delete marker)
- Allocation services have no DB-level checks (relies on application validation)
- Over-allocation prevention tests needed

**Status:** STABLE (but architecturally complex)

---

### MODULE 10: REPORTS & EXPORTS
**Files:** `backend/apps/license/views/report*.py`, `backend/apps/reports/`, `frontend/src/pages/reports/`, `frontend/src/utils/ledgerExport.js`  
**Purpose:** Dashboards, ledgers, pivot tables, Excel/PDF exports  

**Reports:**
| Report | Purpose | Backend | Frontend | Export |
|--------|---------|---------|----------|--------|
| Dashboard | Overview stats, expiring licenses, BOE trends | DashboardDataView | React | - |
| Ledger | License transactions, running balance | LicenseDetailsViewSet.ledger_detail | LicenseLedgerDetail.tsx | PDF/Excel (client-side) |
| Item Pivot | License-item matrix with norms, restrictions | ItemPivotReportView | ItemPivotReport.tsx (126KB) | Excel (Phase 2B modernized) |
| Item Report | Item-level aggregation | ItemReportView | ItemReport.tsx | Excel |
| Planned Report | Planning vs actual | PlannedReportView | PlannedReport.tsx | Excel |
| License Purchase Profit | Financial analysis | LicensePurchaseProfitReportView | LicensePurchaseProfitReport.tsx | Excel |
| Expiring Licenses | License expiry tracking | ExpiringLicensesReportView | ExpiringLicenses.tsx | - |
| SION Norm | Norm-level aggregation | (views) | SionE1/E5/E126/E132.tsx | - |

**Critical Issues:**
1. **Item Pivot Report** — Phase 2B.2B Display Dataset Rule migration completed
   - Flagship report, now single-sources all calculations (Phase 2B.2A/2B.2B modernization)
   - Notification summary, norm selection, totals all consolidated (verified via regression tests)

2. **Ledger Reports** — P0 defect (described in Module 3)
   - Backend PDF and frontend Excel use different balance conventions
   - Causes 3-screen divergence

3. **Excel Export** — Performance risk (N+1 patterns)
   - license_balance_excel.py: loops per item with nested BOE/allotment queries
   - ledgerExport.js: similar pattern on frontend

**Frontend Exports:**
- PDF via jsPDF (license-ledger, transfer letters)
- Excel via ExcelJS (all reports)
- Formatting: Indian number system (123,456.78), native date formatting

**Risk:** **HIGH** (P0 ledger defect, N+1 performance patterns, Ledger builders have zero tests)  
**Tech Debt:**
- Ledger PDF/Excel balance calculations duplicated (3 implementations)
- Export functions not lazy-loaded in frontend bundle (~1.5MB dead weight)
- Item Pivot Report at 126KB (complex but modernized)

**Status:** MODERNIZING (Phase 2B completed for Item Pivot; Phase 3 in progress for Ledger)

---

### MODULE 11: ADMINISTRATION
**Files:** `backend/apps/accounts/views/`, `frontend/src/pages/admin/`  
**Purpose:** User management, audit logs, system settings  

**Core:**
- User create/edit/delete (requires USER_MANAGER role)
- Role assignment
- Activity log viewer (read-only audit trail)
- Settings (superuser only)

**Risk:** Low (simple domain, permissions enforced)  
**Status:** STABLE

---

## CROSS-MODULE DEPENDENCIES

**Critical Path (Highest Coupling):**
```
License
  ↓ (defines available_balance)
Balance
  ↓ (validates planning)
Planning
  ↓ (allocates to items)
Allotment
  ↓ (sources from BOE)
BOE
  ↓ (matched to invoice)
Invoice/Trade
  ↓ (reconciled)
Reconciliation
  ↓ (displayed in)
Reports
```

**Most-Depended-On Files (Refactor Risk):**
1. `license/models/__init__.py` — 141 dependents
2. `core/models.py` — 121 dependents
3. `bill_of_entry/models.py` — 46 dependents
4. `allotment/models.py` — 44 dependents
5. `license/services/balance_calculator.py` — 43 dependents

---

## ACTIVE WORK & PHASE STATUS

**Currently In Progress (41 uncommitted items):**
- Phase 3: Ledger Detail Display Dataset (design done, awaiting business decision)
- A3627 auto-planner (committed 2026-08, needs validation)
- Balance calculator improvements (recent commits 2026-08-08)
- Ledger detail test files (new)
- Architecture documentation updates

**Completed Phases:**
- Phase 1: Authentication (2026-07)
- Phase 2A: Export Consistency (2026-08-06)
- Phase 2B.1: Item Pivot Framework (2026-08-07)
- Phase 2B.2A: Consolidate Grand Totals (2026-08-07)
- Phase 2B.2B: Notification Summary (2026-08-07)

**Do Not Modify (Active Work):**
- balance_calculator.py (active optimization)
- ledger_pdf.py (Phase 3)
- test_*_live_balance.py files (new test suite)
- LEDGER_DETAIL_*.md files (Phase 3 design)

---

## MODULE SCORECARD (1–10 scale)

| Module | Architecture | Quality | Logic Clarity | Data Integrity | Security | Performance | Testing | UX | Maintainability | Tech Debt |
|--------|---|---|---|---|---|---|---|---|---|---|
| Core | 8 | 8 | 8 | 9 | 9 | 8 | 8 | 7 | 8 | 6 |
| License | 7 | 7 | 6 | 8 | 8 | 6 | 7 | 6 | 7 | 5 |
| Ledger | 5 | 5 | 4 | 6 | 7 | 5 | **2** | 5 | 4 | 4 |
| Balance | 6 | 6 | 5 | 8 | 7 | 4 | 7 | 7 | 5 | 5 |
| Planning | 6 | 6 | 5 | 7 | 7 | 7 | 6 | 6 | 6 | 4 |
| Allotment | 8 | 8 | 8 | 9 | 8 | 8 | 8 | 7 | 8 | 9 |
| BOE | 8 | 8 | 8 | 8 | 8 | 8 | 8 | 7 | 8 | 8 |
| Trade | 7 | 7 | 6 | 8 | 8 | 7 | 7 | 6 | 7 | 5 |
| Reconciliation | 6 | 6 | 5 | 7 | 8 | 7 | 6 | 6 | 6 | 4 |
| Reports | 6 | 6 | 5 | 7 | 8 | 5 | 6 | 6 | 6 | 4 |
| Admin | 8 | 8 | 8 | 9 | 9 | 9 | 8 | 7 | 8 | 9 |

**Overall Risk Score:** 6.4/10 (medium-high, driven by Ledger defect, Balance performance, Planning new code)

---

## SUMMARY

The License Manager comprises **11 well-scoped business modules** with clear dependencies. The architecture is **sound** but shows signs of:

1. **Active modernization** (Phases 2–3 in progress)
2. **Hot paths** (balance calculator, balance ledger) requiring optimization
3. **Test gaps** (ledger builders, reconciliation queries)
4. **Unresolved design decision** (ledger balance convention)

**Next Step:** Resolve ledger balance decision and unblock Phase 3 completion before tackling other modules.
