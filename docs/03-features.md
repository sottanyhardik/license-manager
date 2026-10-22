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
- Direction: `PURCHASE`, `SALE`, `COMMISSION_PURCHASE`, or `COMMISSION_SALE`
- License type: `DFIA` (default, uses `LicenseTradeLine`) or `INCENTIVE` (uses `IncentiveTradeLine`)
- Line modes: `QTY` (quantity × rate), `CIF_INR` (CIF × %), `FOB_INR` (FOB × %)
- Invoice number auto-generated per financial year:
  - PURCHASE: `P-PREFIX/YYYY-YY/NNNN` (e.g., `P-LM/2025-26/0024`)
  - SALE: `PREFIX/YYYY-YY/NNNN` (e.g., `LM/2025-26/0001`)
  - COMMISSION_PURCHASE: `COM-P-PREFIX/YYYY-YY/NNNN`
  - COMMISSION_SALE: `COM-PREFIX/YYYY-YY/NNNN`
- Company prefix derived from company name (first 3 letters if 1 word, first letter of each word if 2+)
- Totals auto-computed: `subtotal_amount` + `roundoff` = `total_amount`
- Party snapshots (`from_pan`, `to_gst`, etc.) frozen from company master on save
- Payments tracked via `LicenseTradePayment` (CASCADE on trade delete)
- Composite indexes on `(invoice_date)`, `(direction, invoice_date)`, `(direction, from_company)`, `(direction, to_company)`

**Counterpart / Paired Trade System**:
- `counterpart` (OneToOneField, PROTECT) — immutable reciprocal Sale↔Purchase pair created by `copy-to-purchase` / `copy-to-sale` actions
- `transaction_pair_uuid` (UUIDField) — shared UUID linking both halves of a pair
- `linked_trade` (ForeignKey, SET_NULL) — older manual link field, still present for backwards compatibility
- `copied_from` / `copied_from_type` / `source_document_number` — provenance tracking for copy operations

**Trade Deletion** (`DELETE /api/trades/:id/`):

**Delete Flow**:
1. Frontend: `MasterList.tsx` → `handleDelete(item)` → confirmation dialog → `api.delete('trades/{id}/')`
2. Backend: `LicenseTradeViewSet.destroy()` → `MasterViewSet.perform_destroy(instance)` → `instance.delete()`
3. Django signals fire before delete:
   - `clear_boe_invoice_on_trade_delete`: clears `invoice_no` and `invoice_date` on any linked BOE whose `invoice_no` matches the trade's `invoice_number`
   - `prevent_single_counterpart_delete`: **blocks delete** if `instance.counterpart_id` is set — raises `ValidationError` requiring audited pair-deletion workflow
4. Django CASCADE deletes child objects:
   - `LicenseTradeLine` (via `trade` FK, CASCADE)
   - `IncentiveTradeLine` (via `trade` FK, CASCADE)
   - `LicenseTradePayment` (via `trade` FK, CASCADE)
   - `TradeInvoiceDocument` (via `trade` FK, CASCADE)
   - `InvoiceDocumentAccessToken` (via `trade` FK, CASCADE)
   - `InvoiceDocumentAuditEvent` (via `trade` FK, CASCADE)
5. M2M relations cleared: `boes` many-to-many

**Delete Constraints**:
- **Paired trades cannot be deleted one-sided**: if `counterpart_id` is set, `prevent_single_counterpart_delete` signal raises `ValidationError` with message: "This trade has a linked counterpart. Use the audited pair-deletion workflow."
- **ProtectedError handling**: if any external reference (via PROTECT FK) exists, `MasterViewSet.perform_destroy` catches `ProtectedError` and returns 400 with detail listing the referencing objects
- **MDS cutover**: if MDS (Master Data Service) is active for the model, delete goes through MDS first; MDS down → 503, local row left intact

**Delete Permissions**:
- Requires `TRADE_MANAGER` role (via `TradePermission` — `required_roles_for_write = ['TRADE_MANAGER']`)
- `TRADE_VIEWER` can read but not delete

**Frontend Delete UI**:
- Delete button (trash icon, danger tone) shown in `TradesListView.tsx` when `canWrite` is true
- `handleDelete` in `MasterList.tsx` shows confirmation dialog, then calls `api.delete('trades/{id}/')`
- On success: toast "Record deleted successfully" + list refresh via `invalidateList()`
- On error: toast shows server error message (e.g., counterpart constraint violation)

**Validation Rules**:
- Unique constraint: `from_company` + `invoice_number` + `direction` must be unique for PURCHASE (non-blank invoice_number)
- Unique constraint: `to_company` + `invoice_number` + `direction` must be unique for SALE (non-blank invoice_number)
- `from_company` ≠ `to_company` (check constraint, NULLs allowed)

**Sale Quantity Validation** (direct SALE without BOEs):

When creating a SALE trade with no BOEs attached (`boes: []`), the serializer validates that the total requested quantity per import item does not exceed the available quantity. This prevents over-selling imported goods.

**Validation Flow**:
1. Serializer `create()` method checks: `direction == SALE` AND `boes` is empty
2. For each line, accumulates `qty_kg` by `sr_number` (import item) — handles multiple lines for the same item
3. For each import item, acquires a row lock (`select_for_update()`) to prevent concurrent over-consumption
4. Calculates available quantity: `total_quantity − BOE_debited − outstanding_allotted − direct_sale_quantity`
5. If requested > available, raises `ValidationError` with message: `"SALE quantity {requested} exceeds available quantity {available} for import item {item_id}."`

**Available Quantity Formula** (`ItemBalanceCalculator.calculate_available_quantity`):
- **total_quantity**: The import item's stored `quantity` field (from `LicenseImportItemsModel`)
- **BOE_debited**: Sum of `RowDetails.qty` where `transaction_type = DEBIT` for this item (physical consumption via BOE linkage)
- **outstanding_allotted**: Outstanding allotment quantity from `LicenseBalanceCalculator.get_outstanding_allotment_totals` — allotments not yet linked to a BOE
- **direct_sale_quantity**: Sum of `qty_kg − allocated_qty` for unpaired SALE lines (no counterpart, no linked_trade, no BOE linkage) — represents already-consumed direct sales

**Direct Sale Quantity Exclusions** (what does NOT count as direct sale consumption):
- SALE lines with a linked BOE (the BOE's RowDetails DEBIT already accounts for the physical quantity)
- SALE lines with a counterpart (paired Sale↔Purchase has net zero effect — the purchase restores the quantity)
- SALE lines with a `linked_trade` (older manual link field, same net-zero logic)
- Allocated portions via `InvoiceBOEAllocation` (only `qty_kg − allocated_qty` counts)

**When BOEs ARE attached**: The validation is skipped because the BOE linkage itself serves as the physical quantity debit — the BOE's RowDetails DEBIT rows track the actual consumption.

**⚠️ UI vs Backend Balance Discrepancy**:

The frontend and backend use **different formulas** for calculating available quantity, causing the UI to display a higher balance than what the API actually allows for new direct sales.

**Backend validation formula** (`ItemBalanceCalculator.calculate_available_quantity`):
```
Available = total_quantity − BOE_debited − outstanding_allotted − direct_sale_quantity
```

**Frontend display formula** (`CustomsLedgerSection.tsx`):
```
Actual Available = quantity − boe_debited_quantity
```
The frontend omits **outstanding_allotted** and **direct_sale_quantity** from the displayed balance.

**Balance snapshot API** (`balance_snapshot.py`):
```
Available = total_quantity − debited_quantity − outstanding_qty
```
The snapshot omits **direct_sale_quantity** from the calculated balance.

**Stored field** (`item.available_quantity`, updated by `calculate_balance.py`):
```
Available = quantity − debited − allotted − direct_sale_quantity
```
The stored field includes all four components correctly.

**Impact**: When the user views the Customs Ledger section on the license overview page, the "Actual Available" column shows `quantity - boe_debited` only. If there are outstanding allotments or prior direct sales for that item, the displayed balance will be higher than what the trade creation API accepts. For example, if an item has 342,672.02 kg total quantity and 15,251.30 kg in direct sale quantities, the UI shows 342,672.02 kg available, but the API rejects quantities above 327,420.72 kg.

**Affected UI components**:
- `frontend/src/pages/license-overview/CustomsLedgerSection.tsx` — "Actual Available" column uses `quantity - boe_debited_quantity` only
- `frontend/src/pages/license-overview/ItemsTab.tsx` — "Balance Qty" uses the stored `item.available_quantity` field (correct)
- Balance snapshot API used by list views — omits `direct_sale_quantity`

**Files**:
- `backend/apps/trade/serializers.py` — `LicenseTradeSerializer.create()` lines 431-445 (validation)
- `backend/apps/license/services/balance_calculator.py` — `ItemBalanceCalculator.calculate_available_quantity()` (formula)
- `backend/apps/license/services/balance_calculator.py` — `ItemBalanceCalculator._direct_sale_quantity_rows()` (direct sale filter)
- `backend/apps/license/services/balance_calculator.py` — `ItemBalanceCalculator.calculate_direct_sale_quantity()` (aggregation)
- `backend/apps/license/services/balance_snapshot.py` — `get_snapshot_bulk()` lines 202-203 (snapshot formula — missing direct_sale_qty)
- `backend/apps/core/scripts/calculate_balance.py` — `calculate_available_quantity()` (stored field update — correct)
- `frontend/src/pages/license-overview/CustomsLedgerSection.tsx` — line 12 (frontend formula — incomplete)

**Potential Edge Cases**:
- Deleting a trade with linked BOEs: BOE's `invoice_no` is cleared, allowing reuse
- Deleting a trade with a counterpart: **blocked** by signal — user must delete both or use audited workflow
- Deleting a trade with `SaleClassificationDecision` records: **blocked** by PROTECT on `trade` FK
- Deleting a trade with `TradePairAudit` records: **blocked** by PROTECT on `source`/`counterpart` FKs
- Deleting incentive trade lines triggers `update_incentive_license_on_trade_line_delete` signal to refresh sold status

**Acceptance Criteria**:
- Deleting an unpaired PURCHASE trade removes the trade, all lines, payments, and generated documents
- Deleting a trade with linked BOEs clears the BOE's invoice reference without deleting the BOE
- Attempting to delete one half of a paired trade returns 400 with clear error message
- Only `TRADE_MANAGER` role can delete; `TRADE_VIEWER` sees no delete button

**Force Delete** (bypassing counterpart protection):

When a trade must be deleted despite having a counterpart or other protecting references, the following manual steps are required via Django shell or database operations:

1. **Clear the counterpart link** on both trades:
   ```python
   # In Django shell
   from apps.trade.models import LicenseTrade, TradePairAudit, SaleClassificationDecision
   
   trade = LicenseTrade.objects.get(pk=677)
   counterpart = trade.counterpart
   
   # Clear counterpart on both sides
   trade.counterpart = None
   trade.save(update_fields=['counterpart'])
   
   if counterpart:
       counterpart.counterpart = None
       counterpart.save(update_fields=['counterpart'])
   ```

2. **Delete protecting audit records**:
   ```python
   # Delete TradePairAudit records (PROTECT FK on source/counterpart)
   TradePairAudit.objects.filter(source=trade).delete()
   TradePairAudit.objects.filter(counterpart=trade).delete()
   
   # Delete SaleClassificationDecision records (PROTECT FK on trade)
   SaleClassificationDecision.objects.filter(trade=trade).delete()
   ```

3. **Delete the trade**:
   ```python
   trade.delete()
   ```

**Alternative: QuerySet delete() bypass**:
Django's `QuerySet.delete()` bypasses `pre_delete` signals, but NOT `PROTECT` FK constraints. So you still need to clear the PROTECT references first:
```python
# Clear PROTECT references first
trade = LicenseTrade.objects.get(pk=677)
if trade.counterpart_id:
    cp = LicenseTrade.objects.get(pk=trade.counterpart_id)
    trade.counterpart = None
    trade.save(update_fields=['counterpart'])
    cp.counterpart = None
    cp.save(update_fields=['counterpart'])

TradePairAudit.objects.filter(source=trade).delete()
TradePairAudit.objects.filter(counterpart=trade).delete()
SaleClassificationDecision.objects.filter(trade=trade).delete()

# Now queryset delete bypasses signals
LicenseTrade.objects.filter(pk=677).delete()
```

**Warning**: Force delete destroys audit trail integrity. Use only for data cleanup or error recovery, not for normal operations.

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

---

### F-14: SION Planning (Auto Plan)

**Purpose**: Automate the allocation of import-license entitlements to SION (Scheme for Value Addition in Non-Conventionally Imported Products) export planning. The system matches import items to export items based on configurable rules, then allocates CIF (Cost, Insurance, Freight) values using a priority-based waterfall algorithm.

**Entry Points**:
- Frontend: `/planning?sion=E5&rule=48` → `LicensePlanningWorkspace.tsx`
- API: `GET/POST/PATCH/DELETE /api/sion-planning-rules/`
- API: `POST /api/sion-planning-rules/plan/` (execute planning)
- API: `POST /api/sion-planning-rules/preview/` (preview without saving)
- API: `GET /api/sion-planning-rules/preview-scoped/` (exact license/SION preview)

**Core Concepts**:

1. **SION Norm Classes**: E1, E5, E126, E132, etc. Each norm defines what import items can be converted to what export items.
2. **Planning Rules**: Versioned, database-driven rules that define how to match and allocate. Each rule has:
   - **Expression**: AND/OR tree of conditions (HSN, product description, item key)
   - **Max Unit Price**: The maximum CIF price per unit for this rule's output
   - **Priority**: Execution order (lower = higher priority)
   - **Strategy**: STANDARD (single item), SPLIT_BY_PERCENT, or SPLIT_BY_UNIT_VALUE
3. **Planning Execution**: Priority waterfall — rules execute in priority order, each consuming from the remaining CIF/quantity pool.

**Rule Strategies**:

| Strategy | Description | Configuration |
|---|---|---|
| STANDARD | One import item → one output item | `import_item` FK, `max_unit_price` |
| SPLIT_BY_PERCENT | Split one import item into multiple outputs by percentage | `percentage_rows` (each row: import_item, percentage, unit_price, max_quantity) |
| SPLIT_BY_UNIT_VALUE | Split by price bands | `unit_value_rows` (each row: import_item, min/max/preferred unit price) |

**Planning Execution Flow**:
1. Load all active rules for the selected SION norm, ordered by priority
2. For each rule, evaluate the expression against all import items
3. Calculate available quantity: `original_quantity − BOE_used − unlinked_allotment`
4. Allocate CIF using `allocate_step()`: min(requested CIF, remaining balance)
5. Claim source items to prevent double-allocation across rules
6. Generate `LicenseItemPlan` records with full provenance

**CIF Restriction per Item** (Feature Request — Not Yet Implemented):

The user requests a new field on each planning rule (or percentage row) that limits how much of an import item's total CIF value can be planned. The restriction is expressed as a percentage of the item's total CIF value.

**Proposed Field**: `cif_restriction_percentage` (nullable Decimal, choices: 2, 3, 5, 10)

**Logic**:
- For each import item matched by a rule, compute: `used_cif = debited_cif + allotted_cif`
- Compute the restriction ceiling: `ceiling = item.cif_fc × cif_restriction_percentage / 100`
- If `used_cif >= ceiling`, skip planning for that item
- Otherwise, plan normally but cap the new planned CIF so that `used_cif + new_planned_cif <= ceiling`

**UI Changes Required**:
- In `AllocationStrategyEditor.tsx`, add a dropdown for CIF restriction percentage (None, 2%, 3%, 5%, 10%)
- For STANDARD strategy: one dropdown per rule
- For SPLIT_BY_PERCENT: one dropdown per percentage row
- For SPLIT_BY_UNIT_VALUE: one dropdown per unit value row
- In `LicensePlanningWorkspace.tsx` rule detail view, display the CIF restriction value

**Backend Changes Required**:
- `SionPlanningRule` model: add `cif_restriction_percentage` field (nullable Decimal)
- `SionPlanningPercentageRow` model: add `cif_restriction_percentage` field (nullable Decimal)
- `SionPlanningUnitValueRow` model: add `cif_restriction_percentage` field (nullable Decimal)
- `sion_planning_execution.py`: in `add_line()` or before allocation, check the restriction and skip/cap accordingly
- `SionPlanningRuleSerializer`: include the new field
- Frontend types: add `cif_restriction_percentage` to `SionPlanningRule`, `PercentageRow`, and `UnitValueRow`

**Database Tables**:
- `license_sionplanningrule` — add `cif_restriction_percentage` column
- `license_sionplanningpercentagerow` — add `cif_restriction_percentage` column
- `license_sionplanningunitvaluerow` — add `cif_restriction_percentage` column

**Files**:
- `backend/apps/license/models/core.py` — `SionPlanningRule`, `SionPlanningPercentageRow`, `SionPlanningUnitValueRow`
- `backend/apps/license/serializers/incentive.py` — `SionPlanningRuleSerializer`
- `backend/apps/license/services/sion_planning_execution.py` — `_compute_license_new_architecture()`, `add_line()`
- `frontend/src/pages/planning/LicensePlanningWorkspace.tsx`
- `frontend/src/pages/planning/AllocationStrategyEditor.tsx`
- `frontend/src/services/api/planningRuleApi.ts` — types

**Business Rules**:
- The restriction applies per import item, not per license total
- "Debited CIF" = sum of BOE RowDetails DEBIT CIF for this item
- "Allotted CIF" = sum of allotment CIF for this item
- If restriction is not set (NULL), the item is planned without this cap
- The restriction is a hard ceiling — the planner skips the item entirely if already exceeded

**Edge Cases**:
- Item with zero CIF: restriction ceiling is zero, item is always skipped
- Multiple rules matching the same item: first rule in priority order applies its restriction; later rules see the item as already claimed
- Restriction change on existing rule: affects future planning runs only, not existing plans

**Acceptance Criteria**:
- User can select CIF restriction percentage (2%, 3%, 5%, 10%, or None) when editing a planning rule
- During planning, items exceeding their CIF restriction are skipped with a diagnostic reason
- Preview shows which items were skipped and why
- The restriction is persisted and shown in the rule detail view
