# 03 — Features

> **Last updated:** June 2026 (Phase 4b — AllotmentModel item_name FK, all frontend migrated to shadcn/Tailwind v4/TypeScript)

## Frontend Stack Note

All frontend pages and components are TypeScript (`.tsx`). The UI uses **shadcn/ui + Tailwind CSS v4 + lucide-react** throughout — no Bootstrap, no bootstrap-icons. Dark mode is toggled via `[data-theme="dark"]` on `<html>`.

## Feature Inventory

---

### F-01: License Management (DFIA)

**Purpose**: Track the full lifecycle of DFIA (Duty Free Import Authorisation) licenses from issuance to exhaustion.

**Entry Points**:
- Frontend: `/licenses` → `pages/masters/MasterList.tsx` (entity: `licenses`)
- Frontend: `/licenses/create` / `/licenses/:id/edit` → `pages/masters/MasterForm.tsx`
- API: `GET/POST/PUT/PATCH/DELETE /api/licenses/`

**Files**:
- `backend/apps/license/models.py` — `LicenseDetailsModel` + sub-tables
- `backend/apps/license/views/license.py` — `LicenseDetailsViewSet`
- `backend/apps/license/serializers.py` — `LicenseDetailsSerializer`
- `frontend/src/pages/masters/MasterList.tsx`
- `frontend/src/pages/masters/MasterForm.tsx`

**Database Tables**:
- `license_licensedetailsmodel` — main license record
- `license_licenseimportitemsmodel` — import line items with balances
- `license_licenseexportitemsmodel` — export entitlement items
- `license_licensedocumentmodel` — attached files
- `license_licensebalance` — materialised balance (OneToOne)
- `license_licenseflags` — boolean flags (OneToOne)
- `license_licenseownership` — current owner (OneToOne)
- `license_licensenotes` — user comments/condition sheet (OneToOne)

**Business Rules**:
- License number must be unique; lookup works by PK or `license_number` string
- Balance = sum of import item `available_quantity` fields
- Balance is materialised — updated by signals, not computed on read
- A license can be marked `is_null` (DFIA with no entitlement) or `is_mnm` (minimum-maximum)
- `is_expired` computed from `license_expiry_date` vs today; also stored as a flag
- PDF uploads trigger OCR parsing (`LicensePdfParseView`) to pre-fill form fields

**Acceptance Criteria**:
- Creating a license auto-creates all OneToOne sub-tables (via `post_save` signal)
- Editing import items triggers immediate balance recalculation
- `balance_pdf` action generates multi-page ReportLab PDF showing per-company usage
- `bulk_balance_excel` generates an `.xlsx` with one sheet per license; includes CIF INR column (sourced from `RowDetails.cif_inr` for BOE rows, `AllotmentItems.cif_inr` for allotment rows)
- ViewSet applies `select_related('purchase_status')` and prefetches import/export items + allotment_details chain — no N+1 on list view

---

### F-02: Incentive License Management (RODTEP/ROSTL/MEIS)

**Purpose**: Track incentive-type licenses with 2-year validity, issued in INR.

**Entry Points**:
- Frontend: `/incentive-licenses/` → `MasterList.tsx` (entity: `incentive-licenses`)
- API: `GET/POST/PUT/PATCH/DELETE /api/incentive-licenses/`

**Files**:
- `backend/apps/license/models.py` — `IncentiveLicense`
- `backend/apps/license/views_incentive.py` — `IncentiveLicenseViewSet`

**Business Rules**:
- Validity = 2 years from license date (auto-calculated)
- Value in INR; no foreign currency component
- Trades against incentive licenses use `IncentiveTradeLine` (not `LicenseTradeLine`)
- Balance = face value minus sum of all incentive trade line amounts

---

### F-03: Bill of Entry (BOE) Management

**Purpose**: Record and track actual customs clearance events that debit license balances.

**Entry Points**:
- Frontend: `/bill-of-entries/` → `MasterList.tsx` (entity: `bill-of-entries`)
- Frontend: `/bill-of-entries/create` / `/bill-of-entries/:id/edit` → `MasterForm.tsx`
- API: `GET/POST/PUT/PATCH/DELETE /api/bill-of-entries/`

**Files**:
- `backend/apps/bill_of_entry/models.py` — `BillOfEntryModel`, `RowDetails`
- `backend/apps/bill_of_entry/views/boe.py`
- `frontend/src/pages/masters/MasterList.tsx`
- `frontend/src/pages/masters/MasterForm.tsx`
- `frontend/src/components/TransferLetterForm.tsx`

**Database Tables**:
- `bill_of_entry_billofentrymodel`
- `bill_of_entry_rowdetails`

**Business Rules**:
- Each BOE row (`RowDetails`) links to a specific `LicenseImportItemsModel`
- Linking a BOE row debits the import item's `debited_quantity` and `debited_cif`
- `frozen=True` rows were created via ledger upload — cannot be manually edited
- `is_dispute=True` flags rows where the license item is missing (ledger import found no match)
- Transfer letters can be generated from a BOE (`BOETransferLetter.tsx`)

---

### F-04: Allotment Management

**Purpose**: Pre-authorise specific importers to use a portion of a license before actual customs clearance.

**Entry Points**:
- Frontend: `/allotments/` → `MasterList.tsx` (entity: `allotments`)
- Frontend: `/allotments/:id/allocate` → `AllotmentAction.tsx`
- API: `GET/POST/PUT/PATCH/DELETE /api/allotments/`
- API: `GET /api/allotment-actions/:id/` (allotment with full line detail)

**Files**:
- `backend/apps/allotment/models.py` — `AllotmentModel`, `AllotmentItems`
- `backend/apps/allotment/views.py` — `AllotmentViewSet`
- `backend/apps/core/filtersets.py` — `AllotmentFilterSet`
- `frontend/src/pages/AllotmentAction.tsx`
- `frontend/src/components/AllotmentFormModal.tsx`
- `frontend/src/components/TransferLetterForm.tsx`

**Database Tables**:
- `allotment_allotmentmodel`
- `allotment_allotmentitems`

**Key Fields** (`AllotmentModel`):

| Field | Type | Notes |
|---|---|---|
| `item_name` | `CharField(255)` | Import item name — free-text, required |
| `company` | `ForeignKey(CompanyModel)` | Importer company |
| `port` | `ForeignKey(PortModel)` | Import port |
| `type` | `CharField` choices | `AT` (allotment) or `TR` (transfer) |
| `required_quantity` | `DecimalField(15,2)` | |
| `cif_fc` / `cif_inr` | `DecimalField` | CIF in foreign currency / INR |
| `exchange_rate` | `DecimalField(15,6)` | USD→INR rate at time of allotment |
| `is_boe` | `BooleanField` | True once a BOE is linked to this allotment |
| `is_approved` | `BooleanField` | Inline-editable approval flag |

**Business Rules**:
- Allotment types: `AT` (allotment) or `TR` (transfer)
- `item_name` is a required free-text field describing the import item; it is entered manually in `AllotmentFormModal`
- Each `AllotmentItems` row links to a `LicenseImportItemsModel` and reserves `required_quantity`
- Saving/deleting an allotment item triggers signal → updates `allotted_quantity` on the linked import item
- Balance available for allotment = import item's `available_quantity` − `allotted_quantity`
- Transfer letters for allotments generated via `generate-transfer-letter` action on the allotment-actions viewset

---

### F-05: Trade Invoicing

**Purpose**: Record trade transactions (purchase/sale of licensed goods) and generate invoices.

**Entry Points**:
- Frontend: `/trades/` → `MasterList.tsx` (entity: `trades`)
- Frontend: `/trades/create` / `/trades/:id/edit` → `TradeForm.tsx`
- API: `GET/POST/PUT/PATCH/DELETE /api/trades/`

**Files**:
- `backend/apps/trade/models.py` — `LicenseTrade`, `LicenseTradeLine`, `IncentiveTradeLine`, `LicenseTradePayment`
- `backend/apps/trade/views.py` — `LicenseTradeViewSet`
- `frontend/src/pages/TradeForm.tsx`
- `frontend/src/pages/TradeTransferLetter.tsx`

**Database Tables**:
- `trade_licensetrade`
- `trade_licensetradelineitem`
- `trade_incentivetradelineitem`
- `trade_licensetradepaymment`

**Business Rules**:
- Direction: `PURCHASE` or `SALE`; some trades are `COMMISSION` variant
- Line modes: `QTY` (quantity × rate), `CIF_INR` (CIF × %), `FOB_INR` (FOB × %)
- Invoice number auto-generated per financial year (format: `INV-FY-NNNN`)
- A trade can be linked to a paired trade (`linked_trade`) — e.g. purchase linked to corresponding sale
- `auto_create_paired` toggle creates a mirror trade automatically
- Payments tracked separately with date and amount fields
- Composite indexes on `(invoice_date)`, `(direction, invoice_date)`, `(direction, from_company)`, `(direction, to_company)` for fast list queries
- ViewSet applies `select_related` + `prefetch_related` for all FK chains — no N+1 on list view

---

### F-06: License Ledger

**Purpose**: Show a chronological ledger of all transactions (BOE debits, allotments) against each license, per importer company.

**Entry Points**:
- Frontend: `/license-ledger` → `LicenseLedger.tsx`
- Frontend: `/license-ledger/:id` → `LicenseLedgerDetail.tsx`
- API: `GET /api/license-ledger/`

**Files**:
- `backend/apps/license/views/ledger.py` — `LicenseLedgerViewSet`
- `frontend/src/pages/LicenseLedger.tsx`
- `frontend/src/pages/LicenseLedgerDetail.tsx`
- `frontend/src/utils/ledgerExport.ts`

**Business Rules**:
- Ledger is filtered by financial year (default: current FY April–March)
- Company filter narrows to one importer's view
- Supports PDF and Excel export of ledger data
- `active_only` filter shows only licenses with remaining balance

---

### F-07: Ledger Upload (Async CSV/HTM Processing)

**Purpose**: Bulk-import BOE debit rows from government-issued ledger files (CSV or HTM format).

**Entry Points**:
- Frontend: `/ledger-upload` → `LedgerUpload.tsx`
- API: `POST /api/upload-ledger/`
- API: `GET /api/ledger-task-status/:task_id/`

**Files**:
- `backend/apps/license/views/ledger_upload.py`
- `frontend/src/pages/LedgerUpload.tsx`
- `frontend/src/hooks/useFileUpload.ts`

**Business Rules**:
- Max file size: 50 MB
- Supports batch upload of multiple files simultaneously
- Each file is split into per-license Celery tasks for parallel processing
- Processing creates `RowDetails` entries (with `frozen=True`) linked to import items
- Rows with no matching license item are flagged `is_dispute=True`
- Frontend polls task status every 1 second until all tasks complete/fail
- **Async mode** (default): tasks queued to Celery; **Sync mode**: inline processing for small files

---

### F-08: Transfer Letter Generation

**Purpose**: Generate DGFT-compliant transfer letters in PDF or DOCX format for allotments/BOEs/trades.

**Entry Points**:
- Frontend: `TransferLetterForm.tsx` component (embedded in AllotmentAction, BOETransferLetter, TradeTransferLetter pages)
- Frontend: `TransferLetterModal.tsx` (triggered from MasterList action buttons)
- API: `POST /api/allotment-actions/:id/generate-transfer-letter/`
- API: `POST /api/trades/:id/generate-transfer-letter/`
- API: `POST /api/bill-of-entries/:id/generate-transfer-letter/`

**Files**:
- `backend/apps/allotment/views.py` — generate_transfer_letter action
- `backend/apps/bill_of_entry/views/boe.py` — generate_transfer_letter action
- `frontend/src/components/TransferLetterForm.tsx`
- `frontend/src/pages/BOETransferLetter.tsx`
- `frontend/src/pages/TradeTransferLetter.tsx`
- `frontend/src/pages/AllotmentAction.tsx`

**Business Rules**:
- Multiple parties (importers) can be on a single letter
- Template selection required per party (from `TransferLetterModel` master)
- Address lines can be entered manually or auto-filled from company master
- CIF values can be manually edited per letter generation
- Output formats: PDF, ZIP (contains DOCX per party), or combined PDF
- `include_license_copy` toggle attaches the license copy PDF

---

### F-09: Master Data Management

**Purpose**: Manage reference data used throughout the application.

**Entry Points**:
- Frontend: `/masters/:entityName` → `MasterList.tsx`
- Frontend: `/masters/:entityName/create` / `/:id/edit` → `MasterForm.tsx`
- API: `GET/POST/PUT/PATCH/DELETE /api/masters/:entity/`

**Entities**:

| Entity | Endpoint | Key Fields |
|---|---|---|
| Company | `/api/masters/companies/` | name, IEC, PAN, GST, address, bank details, logo, signature, stamp |
| Port | `/api/masters/ports/` | code, name |
| HS Code | `/api/masters/hs-codes/` | hs_code, description, duty rates, unit |
| SION Norm Class | `/api/masters/sion-classes/` | norm_class, E-number, export/import items |
| Item Name | `/api/masters/item-names/` | name, group, sion_norm_class (FK), restriction_percentage, display_order, is_active |
| Exchange Rate | `/api/masters/exchange-rates/` | currency, rate, date |
| Transfer Letter Template | `/api/masters/transfer-letters/` | name, template file |
| Purchase Status | `/api/masters/purchase-statuses/` | code, label, display_order |
| Scheme Code | `/api/masters/scheme-codes/` | code, description |
| Notification Number | `/api/masters/notification-numbers/` | number, description |

**Business Rules**:
- Master data is managed on the canonical `license-manager` server and synced to followers via `scripts/maintenance/sync-masters.sh`
- Companies have full KYC fields (IEC, PAN, GST) required for transfer letter generation
- Exchange rates are historical — one record per currency per date
- `ItemNameModel` is referenced from `AllotmentModel.item_name_fk` — item names in use on allotments should not be deleted; `SET_NULL` on delete protects the allotment record
- `ItemNameModel` fields `sion_norm_class` and `restriction_percentage` drive the item pivot and item reports; `display_order` controls report row ordering

---

### F-10: Dashboard & Reporting

**Purpose**: Provide operational KPI overview and analytical reports.

**Reports**:

| Report | URL | API |
|---|---|---|
| Dashboard | `/` | `GET /api/dashboard/` |
| License Ledger | `/license-ledger` | `GET /api/license-ledger/` |
| Item Pivot Report | `/reports/item-pivot` | `GET /api/item-pivot/` |
| Item Report | `/reports/item-report` | `GET /api/item-report/` |
| Download License Excel | `/reports/download-license` | `POST /api/licenses/bulk_balance_excel/` |
| Expiring Licenses | `/reports/expiring-licenses` | `GET /api/expiring-licenses/` |
| Active Licenses | `/reports/active-licenses` | `GET /api/active-licenses/` |
| SION Reports (E1/E5/E126/E132) | `/reports/parle/sion-e*` | `GET /api/item-report/?norm=...` |
| Inventory Balance | n/a | `GET /api/inventory-balance/` |

---

### F-11: Task Management

**Purpose**: Internal workflow tasks for tracking compliance work, follow-ups, and assignments.

**Entry Points**:
- Frontend: `TaskDrawer.tsx` (slide-in panel accessible from any page)
- API: `GET/POST/PUT/PATCH/DELETE /api/tasks/`
- API: `POST /api/tasks/:id/complete/`, `/reject/`, `/reopen/`
- API: `POST /api/tasks/:id/remarks/`

**Business Rules**:
- Tasks visible to creator or assignee (superusers see all)
- Priority levels: LOW, NORMAL, HIGH
- Status flow: `pending` → `in_progress` → `completed` or `rejected`
- Rejected tasks can be reopened
- Voice input via browser's Web Speech API (`useSpeechRecognition` hook) auto-parses title + assignee + priority from spoken text; `parseVoiceCommand()` extracts "urgent"/"asap" → HIGH priority and "assign to NAME" → fuzzy user match
- Remarks are append-only (no edit/delete)
- Queryset applies `select_related('created_by', 'assigned_to', 'rejected_by')` and `prefetch_related('remarks__created_by')` — no N+1 queries
- Composite indexes on `(assigned_to, status)` and `(created_by, status)` for fast filtering

---

### F-12: Activity Log & Audit Trail

**Purpose**: Maintain an immutable log of every user action for compliance and debugging.

**Entry Points**:
- Frontend: `/admin/activity-log` → `ActivityLog.tsx`
- API: `GET /api/masters/activity-logs/`

**Business Rules**:
- Middleware captures: user, timestamp, method, path, status code, IP, user agent, response time
- All actions logged regardless of success/failure
- Superuser-only access to full log
- Searchable by user, path, method, status code, date range

---

### F-13: User & Role Management

**Purpose**: Manage user accounts and assign role-based access.

**Entry Points**:
- Frontend: `/admin/users` → `UserList.tsx`
- Frontend: `/admin/users/create` / `/:id/edit` → `UserForm.tsx`
- API: `GET/POST/PUT/PATCH/DELETE /api/auth/users/`
- API: `POST /api/auth/users/:id/reset-password/`

**Roles** (15 total):

| Role Code | Permission Scope |
|---|---|
| `USER_MANAGER` | Create/manage users |
| `LICENSE_MANAGER` | Full license CRUD |
| `LICENSE_VIEWER` | Read-only licenses |
| `ALLOTMENT_MANAGER` | Full allotment CRUD |
| `ALLOTMENT_VIEWER` | Read-only allotments |
| `BOE_MANAGER` | Full BOE CRUD |
| `BOE_VIEWER` | Read-only BOEs |
| `TRADE_MANAGER` | Full trade CRUD |
| `TRADE_VIEWER` | Read-only trades |
| `INCENTIVE_LICENSE_MANAGER` | Full incentive license CRUD |
| `INCENTIVE_LICENSE_VIEWER` | Read-only incentive licenses |
| `REPORT_VIEWER` | Access all reports |
| `TL_GENERATE` | Generate transfer letters |
| `LEDGER_MANAGER` | Upload ledger files |
| `ACCOUNT_ACCESS` | Finance read access |
