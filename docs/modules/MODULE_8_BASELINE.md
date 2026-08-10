Let me now compile the comprehensive baseline discovery document. I'll write it directly to the output:

# MODULE 8: DFIA / LICENSE MANAGEMENT — BASELINE DISCOVERY

## 1. SCOPE

### What This Module Manages

**License Management** (Module 8) is the authoritative system for DFIA (Duty Free Import Authorization) licenses and Incentive licenses (RODTEP/ROSTL/MEIS). It manages:

- **License header data** (license number, date, expiry, exporter, port, file number)
- **Import items** (quantities, CIF values, item names, HSN codes)
- **Export items** (outbound trade references with CIF/FOB values)
- **License balance calculation** (credit from imports, debit from BOE/allotments, available balance)
- **License conditions** (AU, percentage-based restrictions on item allocation)
- **License documents** (license copies, transfer letters)
- **License ownership tracking** (current owner, DGFT file transfer status)
- **Utilization planning** (planned allocation caps per import item)

### Business Entities

| Entity | Purpose | Key Fields |
|--------|---------|-----------|
| **LicenseDetailsModel** | License header | number, date, expiry, exporter FK, port FK, scheme, notification, status |
| **LicenseImportItemsModel** | Import line items | license FK, quantity, cif_fc, items M2M, condition_type, available_value (calculated) |
| **LicenseExportItemModel** | Export line items (for DFIA) | license FK, quantity, cif_fc, item FK, norm_class FK |
| **LicenseBalance** | Denormalized balance cache | license FK (OneToOne), balance_cif, ledger_date |
| **LicenseFlags** | License metadata flags | license FK (OneToOne), is_active, is_expired, is_audit, is_mnm, is_null |
| **LicenseOwnership** | DGFT tracking | license FK (OneToOne), current_owner, file_transfer_status, last_fetch_date |
| **LicenseNotes** | License narratives | license FK (OneToOne), user_comment, condition_sheet, restrictions, balance_notes |
| **IncentiveLicense** | RODTEP/ROSTL/MEIS | license_type, license_value, sold_value (decimal tracking) |
| **LicenseItemPlan** | Utilization plan lines | import_item FK, planned_quantity, planned_cif_fc, remaining_quantity/cif (tracked independently) |

### Key Workflows

1. **License Registration** — Create license header with imports/exports
2. **Balance Calculation** — Multi-engine approach: Financial (Opening + Purchase - Sale - BOE - Allotment) vs. Customs (raw debit model)
3. **Condition Pool Allocation** — Percentage-restricted items (2%, 3%, 5%, 10%) share a collective pool; AU (non-transferable) has its own rules
4. **Item Planning** — User-authored allocation caps prevent over-commitment
5. **Allotment Gating** — License balance check gates allotment creation (live calculation, not denormalized cache)
6. **BOE Debit Integration** — Links to RowDetails (Bill of Entry) for consumption tracking
7. **Trade Debit Integration** — Links to LicenseTrade for purchase/sale accounting
8. **Ownership Transfer** — DGFT file tracking and company handoff

### Integration Points

| Module | Interaction | Direction |
|--------|-------------|-----------|
| **Bill of Entry** | RowDetails → License import items for BOE debit (DEBIT tx type) | Inbound debit |
| **Allotment** | AllotmentItems → License import items for non-BOE allotment | Inbound debit |
| **Trade** | LicenseTrade lines → License via purchase/sale trades | Financial ledger impact |
| **Reconciliation** | InvoiceBOEAllocation, BOEAllotmentAllocation → BOE/allotment link tracking | Allocation netting |
| **Core Masters** | CompanyModel (exporter), PortModel, HSCodeModel, ItemNameModel, SionNormClassModel | Reference data |
| **Accounts** | Permissions model (LicensePermission, LicenseLedgerViewPermission) | Access control |

---

## 2. FINANCIAL CALCULATIONS

### Calculation Engines

#### **Engine A: Financial Available Balance** (Authoritative for allocation, ledger, UI)

Formula:
```
BALANCE = Opening Balance 
        + Purchase Invoice CIF 
        - Sale Invoice CIF 
        - Our (unallocated) BOE Debit 
        - Outstanding Allotments
        (floor at 0, quantize to 2 DP)
```

**Implemented in:** `LicenseBalanceCalculator.calculate_financial_balance(license_obj)`

**Components:**

1. **Opening Balance** — Previous owner utilisation + credit from imports
   - Formula: Credit (export CIF total) - Previous Owner Utilisation (if hidden BOEs exist)
   - Method: `calculate_opening_balance()` — applies 3-way gate for hidden BOE scenarios
   - Precision: 2 decimal places (Decimal, ROUND_HALF_UP)

2. **Purchase Credit** — Internal purchase trades that add CIF
   - Sum of PURCHASE LicenseTrade lines' `cif_fc` for this license
   - Method: `calculate_purchase_credit()`
   - Precision: 2 DP

3. **Sale Debit** — Internal sales that reduce available balance
   - Sum of SALE LicenseTrade lines' `cif_fc` for this license
   - Method: `calculate_trade()` — INCLUDES netting of BOE rows already accounted for via allocation
   - Precision: 2 DP

4. **BOE Debit** — Bill of Entry consumption
   - Sum of RowDetails with `transaction_type=DEBIT` and `sr_number__license=this`
   - Excludes "hidden" (previous-owner) BOE rows via `annotate_and_exclude_hidden()`
   - **CRITICAL:** Uses `calculate_debit()` (allocation-aware, per-row exclusion) NOT `calculate_boe_debit_total()` (raw, invoice-unaware)
   - Rationale: A BOE row matched to a SALE trade is double-counted if included here; only the unmatched remainder should subtract from balance
   - Method: `calculate_debit()` — applies `_linked_boe_debit_exclusion_case()` to mark BOE rows already represented in trade totals
   - Precision: 2 DP

5. **Outstanding Allotments** — Non-BOE allotments awaiting consumption
   - Sum of AllotmentItems with `allotment__bill_of_entry__isnull=True` for this license
   - Method: `calculate_allotment()`
   - Precision: 2 DP

#### **Engine B: Customs Balance** (Read-only, for audit/reconciliation comparison)

Formula:
```
CUSTOMS_BALANCE = Credit (export CIF) 
                - Raw BOE Debit (all visible rows, including allocated)
                (floor at 0, quantize to 2 DP)
```

**Implemented in:** `LicenseBalanceCalculator.calculate_balance(license_obj)`

- Deliberately does NOT deduct sales/purchases/allotments — literal customs formula
- Used only in `build_financial_ledger`'s self-check (`mismatched`) to flag discrepancies
- Never flows through allocation gating or list views

### Where Calculations Are Done

| Calculation | Primary Method | Batch Sibling | Caching |
|------------|--------|--------|---------|
| Credit | `LicenseBalanceCalculator.calculate_credit()` | `calculate_credit_for_licenses()` | None |
| Purchase | `calculate_purchase_credit()` | `calculate_purchase_credit_for_licenses()` | None |
| Sale | `calculate_trade()` | `calculate_trade_for_licenses()` | None |
| BOE Debit | `calculate_debit()` | `calculate_debit_for_licenses()` | None |
| Allotment | `calculate_allotment()` | `calculate_allotment_for_licenses()` | None |
| **Financial Balance** | `calculate_financial_balance()` | `calculate_financial_balance_for_licenses()` | `LicenseBalance.balance_cif` (denormalized, stale) |
| Customs Balance | `calculate_balance()` | `calculate_customs_balance_for_licenses()` | None |
| Item-level Available | `LicenseImportItemsModel.available_value_calculated` (property) | `condition_pool.available_value_bulk_map()` | None |
| Condition Pool | `condition_pool.compute_condition_pools()` | `condition_pool.compute_condition_pools_bulk()` | None |

### Duplicate Calculations Risk

**Known Duplicates / Divergence Points:**

1. **`calculate_debit()` vs. `calculate_boe_debit_total()`**
   - `calculate_debit()`: Allocation-aware, uses `_linked_boe_debit_exclusion_case()` to exclude rows already netted in sales
   - `calculate_boe_debit_total()`: Raw, invoice-allocation-unaware, includes all visible BOE rows
   - **Risk:** Substituting one for the other in the Financial Balance formula causes divergence whenever a SALE-matched BOE row has an unmatched sibling
   - **Guard:** Formula's docstring explicitly forbids the substitution; `calculate_debit()` output must empirically match `build_financial_ledger`'s `computed_balance` (self-check: `mismatched` flag)

2. **`LicenseBalance.balance_cif` (denormalized) vs. `calculate_financial_balance()` (live)**
   - Cache updated by `update_license_flags` signal (post-reconciliation allocation save)
   - NOT updated on BOE hide/restore (see risk register #3)
   - **Guard:** All allocation gating reads the live `calculate_financial_balance()` directly, not the cache
   - Legacy views may read the cache and show stale figures (known, documented limitation)

3. **Item-level Available Value Hierarchy**
   - `LicenseImportItemsModel.available_value_calculated` (property) — single-item, reads live balance
   - `condition_pool.available_value_bulk_map()` — batched, reuses balance calculator bulk methods
   - **Guard:** Both follow the same branching logic (0.01 marker → % condition → item attribution → fallback); kept in lock-step per docstring in `available_value_calculated`

4. **Item Debit Calculation**
   - `LicenseImportItemsModel._calculate_item_debit()` — item-scoped BOE debit
   - Separate from `ItemBalanceCalculator.calculate_debited_cif_for_items()` (batched sibling)
   - Both exclude hidden rows; kept synchronized

### Formula Correctness

**Validation Mechanisms:**

1. **Golden-master tests** — 85 test files (~25k LOC) covering:
   - Balance parity across engines (Financial vs. Customs, live vs. cached)
   - BOE allocation netting (a row in a matched trade should NOT double-count)
   - Hidden BOE exclusion (previous-owner debits not subtracted)
   - Condition pool allocation (percentage restrictions)
   - Item-level attribution (positive CIF items use own debit, zero-CIF items use license balance)
   - Cross-module parity (Balance vs. Item Pivot vs. Ledger PDF vs. Excel export)

2. **Dual-ledger audit** — `build_financial_ledger()` produces both:
   - Running-balance progression (row-by-row accumulation)
   - BOE/Trade allocation mismatch warnings (`mismatched` rows)

3. **Live-balance gate** — Allotment creation reads `calculate_financial_balance()` directly, not cache, preventing stale-balance exploits

### Precision Requirements

| Field | Decimal Places | Django Field | Rounding |
|-------|--------|--------|---------|
| Quantity (import/export) | 3 | DecimalField(15, 3) | ROUND_HALF_UP |
| CIF/FOB/Value (FC) | 2 | DecimalField(15, 2) | ROUND_HALF_UP |
| CIF/FOB/Value (INR) | 2 | DecimalField(15, 2) | ROUND_HALF_UP |
| Unit Price | 2 | DecimalField(15, 2) | ROUND_HALF_UP |
| Exchange Rate | 6 | DecimalField(15, 6) | ROUND_HALF_UP |
| Allocated/Planned CIF | 3 (larger scale) | DecimalField(20, 3) | ROUND_HALF_UP |

**Quantization Rule:**
- All balance outputs: `quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)` → 2 DP
- All quantities: 3 DP (as stored in DB)
- Utility: `quantize_2dp()` in balance_calculator.py

### Rounding Rules

- **Floor at Zero:** All final balance values: `max(balance, Decimal("0"))` — never negative
- **Halfway:** ROUND_HALF_UP (0.5 rounds up) — consistent with financial reporting
- **Special Cases:**
  - **0.01 CIF Marker:** Treated as literal 0.01 (signal value for "calculate from pool") — NOT rounded away
  - **Percentage Conditions:** Computed as `N% × License CIF` — result then quantized to 2 DP

---

## 3. DATA MODELS

### Core Models

```
LicenseDetailsModel (PK=id)
├─ license_number (CharField, unique)
├─ license_date (DateField)
├─ license_expiry_date (DateField)
├─ exporter_id (FK → core.CompanyModel, PROTECT, nullable)
├─ archived_exporter_name (CharField, snapshot after deletion)
├─ port_id (FK → core.PortModel, PROTECT, nullable)
├─ purchase_status_id (FK → core.PurchaseStatus, PROTECT, nullable)
├─ scheme_code_id (FK → core.SchemeCode, PROTECT, nullable)
├─ notification_number_id (FK → core.NotificationNumber, PROTECT, nullable)
├─ file_number (CharField)
├─ registration_number (CharField)
├─ registration_date (DateField)
├─ ge_file_number (IntegerField)
└─ Relationships (reverse):
   ├─ import_license → LicenseImportItemsModel (CASCADE, many)
   ├─ export_license → LicenseExportItemModel (CASCADE, many)
   ├─ balance (OneToOne) → LicenseBalance
   ├─ flags (OneToOne) → LicenseFlags
   ├─ ownership (OneToOne) → LicenseOwnership
   ├─ notes (OneToOne) → LicenseNotes
   ├─ license_documents → LicenseDocumentModel (CASCADE, many)
   ├─ transfers → LicenseTransferModel (CASCADE, many)
   ├─ item_plans → LicenseItemPlan (CASCADE, many)
   └─ license_status → LicenseInwardOutwardModel (CASCADE, many)

LicenseImportItemsModel (PK=id, unique_together=(license, serial_number))
├─ serial_number (IntegerField)
├─ license_id (FK → LicenseDetailsModel, CASCADE)
├─ hs_code_id (FK → core.HSCodeModel, CASCADE, nullable)
├─ items (M2M → core.ItemNameModel)
├─ description (CharField)
├─ quantity (DecimalField, 15, 3)
├─ old_quantity (DecimalField, 15, 3)
├─ unit (CharField, choices UNIT_CHOICES)
├─ cif_fc (DecimalField, 15, 2)
├─ cif_inr (DecimalField, 15, 2)
├─ available_quantity (DecimalField, 15, 3) [denormalized, stale]
├─ available_value (DecimalField, 15, 2) [denormalized, stale]
├─ debited_quantity (DecimalField, 15, 3) [denormalized]
├─ debited_value (DecimalField, 15, 2) [denormalized]
├─ allotted_quantity (DecimalField, 15, 3) [denormalized]
├─ allotted_value (DecimalField, 15, 2) [denormalized]
├─ is_restricted (BooleanField) [derived: bool(condition_type.strip())]
├─ condition_type (CharField) [drives pool-based allocation: "", "AU", "2%", "3%", "5%", "10%"]
├─ comment (TextField)
└─ Relationships:
   ├─ item_details → RowDetails (reverse, BOE debits, DEBIT tx_type)
   ├─ allotment_details → AllotmentItems (reverse, non-BOE allotments)
   └─ utilization_plans → LicenseItemPlan (CASCADE, many)

LicenseExportItemModel (PK=id)
├─ serial_number (IntegerField)
├─ license_id (FK → LicenseDetailsModel, CASCADE)
├─ item_id (FK → core.ItemNameModel, CASCADE, nullable)
├─ norm_class_id (FK → core.SionNormClassModel, CASCADE, nullable)
├─ description (CharField)
├─ net_quantity (DecimalField, 15, 2)
├─ old_quantity (DecimalField, 15, 2)
├─ unit (CharField)
├─ fob_fc (DecimalField, 15, 2)
├─ fob_inr (DecimalField, 15, 2)
├─ fob_exchange_rate (DecimalField, 15, 6)
├─ currency (CharField, choices CURRENCY_CHOICES)
├─ value_addition (DecimalField, 15, 2)
├─ cif_fc (DecimalField, 15, 2)
└─ cif_inr (DecimalField, 15, 2)

LicenseBalance (OneToOne → LicenseDetailsModel, PK=license_id)
├─ balance_cif (DecimalField, 15, 2) [denormalized, stale]
└─ ledger_date (DateField)

LicenseFlags (OneToOne → LicenseDetailsModel, PK=license_id)
├─ is_active (BooleanField, default=True)
├─ is_audit (BooleanField)
├─ is_mnm (BooleanField)
├─ is_not_registered (BooleanField)
├─ is_null (BooleanField)
├─ is_au (BooleanField)
├─ is_incomplete (BooleanField)
├─ is_expired (BooleanField)
└─ is_individual (BooleanField)

LicenseOwnership (OneToOne → LicenseDetailsModel, PK=license_id)
├─ current_owner (CharField)
├─ file_transfer_status (CharField)
└─ last_ownership_fetch (DateTimeField)

LicenseNotes (OneToOne → LicenseDetailsModel, PK=license_id)
├─ user_comment (TextField)
├─ condition_sheet (TextField)
├─ user_restrictions (TextField)
└─ balance_report_notes (TextField)

LicenseItemPlan (PK=id, FK-indexed)
├─ import_item_id (FK → LicenseImportItemsModel, CASCADE)
├─ license_id (FK → LicenseDetailsModel, CASCADE) [denormalized for fast per-license queries]
├─ item_name_id (FK → core.ItemNameModel, SET_NULL, nullable)
├─ planned_quantity (DecimalField, 15, 3)
├─ unit_price (DecimalField, 15, 2)
├─ planned_cif_fc (DecimalField, 15, 2)
├─ planned_cif_inr (DecimalField, 15, 2, nullable)
├─ remaining_quantity (DecimalField, 15, 3, nullable) [live, decremented on allotment]
├─ remaining_cif_fc (DecimalField, 15, 2, nullable) [live, decremented on allotment]
└─ timestamps (created_on, modified_on)

IncentiveLicense (PK=id)
├─ license_type (CharField, choices: RODTEP/ROSTL/MEIS)
├─ license_number (CharField, unique)
├─ license_date (DateField)
├─ license_expiry_date (DateField, auto-calc: license_date + 2 years)
├─ exporter_id (FK → core.CompanyModel, CASCADE)
├─ port_code_id (FK → core.PortModel, CASCADE)
├─ license_value (DecimalField, 15, 2, ≥0)
├─ sold_value (DecimalField, 15, 2, ≥0)
└─ timestamps (created_on, modified_on)

LicenseDocumentModel (PK=id)
├─ license_id (FK → LicenseDetailsModel, CASCADE)
├─ type (CharField, choices: LICENSE COPY / TRANSFER LETTER / OTHER)
├─ file (FileField, upload_to=license_path)
└─ created_on (DateTimeField, auto_now_add)

LicenseTransferModel (PK=id)
├─ license_id (FK → LicenseDetailsModel, CASCADE)
├─ transfer_date (DateField)
├─ from_company_id (FK → core.CompanyModel, SET_NULL, nullable)
├─ to_company_id (FK → core.CompanyModel, SET_NULL, nullable)
├─ transfer_status (CharField)
├─ transfer_initiation_date (DateTimeField)
├─ transfer_acceptance_date (DateTimeField)
├─ cbic_status (CharField)
├─ cbic_response_date (DateTimeField)
├─ transfer_initiation_user_id (FK → User, SET_NULL, nullable)
└─ acceptance_user_id (FK → User, SET_NULL, nullable)
```

### Foreign Key Constraints

| Constraint | Type | Impact |
|-----------|------|--------|
| `license → exporter` (PROTECT) | Soft link | Prevent deletion; archived_exporter_name snapshot preserves history |
| `license → port` (PROTECT) | Soft link | Prevent port deletion while license exists |
| `license → purchase_status/scheme_code/notification` (PROTECT) | Master data | Prevent deletion of reference values |
| `import_item → license` (CASCADE) | Hard link | Deleting license cascades to all import items |
| `export_item → license` (CASCADE) | Hard link | Deleting license cascades to all export items |
| `LicenseBalance/Flags/Ownership/Notes → license` (OneToOne, CASCADE) | Soft link | Auto-created via signal; deleted with license |
| `plan_line → import_item` (CASCADE) | Hard link | Deleting import item cascades to its plan lines |
| `LicenseTransferModel → from/to_company` (SET_NULL) | Soft link | Allow company deletion; preserve transfer history |

### Cascade Settings Risk

**CASCADE Risks:**
1. **Bulk license deletion** cascades to ~100k+ import items if license has multi-item imports → potential data loss
2. **SET_NULL on transfers** means deleted companies leave dangling `from_company_id`/`to_company_id` (acceptable for audit trail)

**No CASCADE (PROTECT) Risks:**
1. Cannot delete exporter while license exists — acceptable business rule (prevents orphaning)
2. Cannot delete port/scheme/notification if referenced — acceptable (master data integrity)

### Indexes

**Performance-Critical Indexes:**

```sql
Index(fields=['license_number'])  -- License header lookup
Index(fields=['file_number'])  -- File number scan
Index(fields=['exporter', 'license_date'])  -- Exporter report scans
Index(fields=['port', 'license_date'])  -- Port report scans
Index(fields=['license_date'])  -- Date range queries
Index(fields=['license_expiry_date'])  -- Expiry scans

Index(fields=['license'])  -- Import item lookup by license
Index(fields=['hs_code'])  -- HSN code pivots
Index(fields=['available_quantity'])  -- Filter by available qty > 0
Index(fields=['available_value'])  -- Filter by available value
```

**Denormalization Trade-offs:**

| Field | Trade-off | Reason |
|-------|-----------|--------|
| `import_item.available_quantity` | Stale | Updated only on BOE save/allotment; misses reconciliation changes |
| `import_item.available_value` | Stale | Denormalized cache; live calculation reads via `available_value_calculated` property |
| `import_item.debited_quantity/value` | Stale | Denormalized; not refreshed on hidden BOE toggle |
| `import_item.allotted_quantity/value` | Stale | Denormalized; not refreshed on reconciliation allocation change |
| `LicenseBalance.balance_cif` | Stale | Updated only on allocation save; misses BOE hide/restore |
| `LicenseItemPlan.remaining_quantity/cif` | Live | Actively decremented on allotment; tracked independently |

**Consequence:** List views and reports relying on these denormalized fields may show stale figures. Allocation gating and ledger generation deliberately bypass the cache and read live calculations.

---

## 4. BUSINESS RULES

### Validations

| Rule | Implementation | Enforcement |
|------|--------|-----------|
| **License Number Unique** | `license_number` CharField(unique=True) | DB constraint |
| **Quantity ≥ 0** | MinValueValidator(DEC_0) on quantity/qty fields | Model validation |
| **CIF ≥ 0** | MinValueValidator(DEC_0) on cif_fc/cif_inr/fob_* fields | Model validation |
| **Import Serial Unique per License** | unique_together=(license, serial_number) | DB constraint, enforced at form/serializer |
| **Balance Never Negative** | Floor at 0 in `calculate_financial_balance()` | Service layer |
| **Available Value Precision** | Quantize to 2 DP (ROUND_HALF_UP) | Service layer |
| **Restricted Item Pool Enforcement** | `condition_pool.remaining_for_condition()` checks % pool before allotment | Service layer (plan_enforcement) |
| **Expiry Check on Allocation** | Allotment gating checks `license.license_expiry_date <= today()` | View layer (allotment/views_actions.py) |
| **Condition Type Format** | Whitelist: "", "AU", "2%", "3%", "5%", "10%" (extensible) | Model field + docstring, no DB check |
| **Item Attribution CIF** | Positive `import_item.cif_fc` signals item-level basis; 0 uses license balance | Service layer (ItemBalanceCalculator) |
| **0.01 CIF Marker** | Special case: 0.01 is never quantized away (signal value) | Service layer (available_value_calculated) |

### State Transitions

| Transition | Actor | Preconditions | Consequences |
|-----------|-------|----------|-------------|
| **Create License** | System/Admin | None | Auto-creates LicenseBalance, LicenseFlags, LicenseOwnership, LicenseNotes via signal |
| **Add Import Item** | System/Admin | License exists | Auto-tags items from filter_list; signal triggers balance update |
| **Allocate (Allotment)** | System | License not expired; live balance sufficient; restricted pool not exceeded | Decrements import_item.remaining_quantity/cif; creates AllotmentItems; triggers license balance recompute |
| **Hide BOE** | Reconciliation | BOE exists, belongs to this license | Marks as OTH_INVOICE_MARKER; excludes from BOE debit calculations; denormalized cache not refreshed |
| **Restore BOE** | Reconciliation | BOE is hidden | Reverses hide; re-includes in debit calculations |
| **Create Allocation** | Reconciliation | BOE + Allotment exist | Marks rows as matched; excludes BOE row from `calculate_debit()` remainder |
| **Transfer License** | User | License exists | Creates LicenseTransferModel with statuses; updates LicenseOwnership.current_owner |
| **Mark Expired** | System/Admin | License expiry_date <= today() | Sets LicenseFlags.is_expired = True; gating prevents new allotments |

### Permission Requirements

| Operation | Required Permission | Role Check |
|-----------|-------|-----------|
| **View License List** | `LicensePermission` | Any DFIA-aware role |
| **View License Detail** | `LicensePermission` | License.exporter scoped (if CompanyModel-linked) |
| **View Ledger** | `LicenseLedgerViewPermission` | Explicit ledger viewer role |
| **View Balance Ledger** | `LicenseBalanceLedgerPermission` | Explicit balance ledger role |
| **Edit License** | `LicensePermission` + superuser/owner check | Admin or license owner |
| **View Incentive License** | `IncentiveLicensePermission` | Explicit incentive viewer |
| **Allocate Items** | `LicensePermission` | Implicit: called from Allotment viewset |

**Scope Rule:** Non-superusers see only licenses whose exporter matches their `CompanyModel.role_scope` (if set). Superusers see all.

### Workflow Constraints

| Constraint | Rationale | Enforcement |
|-----------|-----------|-----------|
| **No Negative Balance** | Financial rule: cannot allocate more than available | Gating in `allocate_items()` reads live balance |
| **No Allocation to Expired License** | Regulatory: expired licenses cannot be used | Gating checks `license.license_expiry_date > today()` |
| **Condition Pool Cap** | Regulatory: percentage-restricted items share a fixed pool | `condition_pool.remaining_for_condition()` enforces pool limit |
| **Plan Line Cap** | Business rule: planned allocation acts as a ceiling | `plan_enforcement.check_item_plan_cap()` sums planned lines for this import item |
| **Non-Transferable AU Items** | Regulatory: AU items cannot be transferred after import | No explicit enforcement (manual process) |
| **BOE Debit Exclusion** | Accounting: previous-owner (hidden) debits not subtracted from balance | `annotate_and_exclude_hidden()` filters per OTH marker + audit trail |
| **Allocation-aware BOE Debit** | Accounting: don't double-count BOE rows matched to trades | `_linked_boe_debit_exclusion_case()` removes matched rows from remainder |

---

## 5. DEPENDENCIES

### What License Module Depends On

| Module | Type | Usage |
|--------|------|-------|
| **Bill of Entry** | Hard | `RowDetails` (BOE debit rows) — core to balance calculation |
| **Allotment** | Hard | `AllotmentItems` (non-BOE allotments) — core to balance calculation |
| **Trade** | Hard | `LicenseTrade` (purchase/sale lines) — core to financial ledger |
| **Reconciliation** | Soft | `InvoiceBOEAllocation`, `BOEAllotmentAllocation` — for BOE/allotment link tracking |
| **Core Masters** | Hard | CompanyModel (exporter), PortModel, HSCodeModel, ItemNameModel, SionNormClassModel, PurchaseStatus, SchemeCode, NotificationNumber |
| **Core Cache** | Soft | Cache signals to invalidate `license_list`, `get_license_balance` on import item save |
| **Accounts** | Soft | Permissions: LicensePermission, LicenseLedgerViewPermission, LicenseBalanceLedgerPermission |

### What Depends On License Module

| Module | Type | Usage |
|--------|------|-------|
| **Allotment** | Hard | License import items (allocation target); live balance gate; license expiry check |
| **Bill of Entry** | Hard | RowDetails.sr_number → LicenseImportItemsModel; BOE debit linked to license |
| **Trade** | Hard | LicenseTrade lines reference license via sr_number; purchase/sale trade aggregates |
| **Reconciliation** | Soft | Reconciliation allocations reference license via trade/BOE/allotment; balance gating |
| **Core Reports/Dashboards** | Soft | License list, balance summary, expiry alerts, item pivots |
| **Incentive** | Soft | IncentiveLicense (parallel hierarchy, not integrated) |

### API Contracts

#### Primary ViewSets

| ViewSet | Method | Endpoint | Purpose |
|---------|--------|----------|---------|
| `LicenseDetailsViewSet` | GET/LIST | `/licenses/` | License list with live balance |
| `LicenseDetailsViewSet` | GET/RETRIEVE | `/licenses/{id}/` | License detail |
| `LicenseDetailsViewSet` | PATCH/PUT | `/licenses/{id}/` | License update (admin) |
| `LicenseLedgerViewSet` | GET/LIST | `/license-ledgers/` | Ledger rows for a license |
| `LicenseItemViewSet` | GET/LIST | `/license-items/` | Import/export items for a license |
| `LicenseItemPlanViewSet` | GET/LIST/CREATE/PATCH/DELETE | `/license-item-plans/` | Utilization plan management |
| `ItemPivotViewSet` | GET/LIST | `/item-pivot/` | Item-grouped balance report |
| `ItemReportViewSet` | GET/LIST | `/item-report/` | Historical item report |
| `LicenseLedgerUploadView` | POST | `/license-ledgers/upload/` | Ledger PDF parse & ingest |
| `DashboardDataView` | GET | `/license-dashboard/` | Dashboard cards (counts, balances, expiry) |

#### Serializers

| Serializer | Purpose | Calculation |
|-----------|---------|-------------|
| `LicenseDetailsSerializer` | License header read | Includes `get_balance_cif` (live calculation) |
| `LicenseItemSerializer` | Import item read | Includes `available_value_calculated` (live), `available_quantity` (denormalized) |
| `PlannedQuantitySerializer` | Plan line CRUD | Updates `planned_quantity`, `remaining_quantity`, `remaining_cif_fc` |
| `LicenseLedgerSerializer` | Ledger row read | Includes `balance` (from CanonicalLedgerService) |
| `AvailableLicensesSerializer` | Allotment UI (available licenses) | Reads `available_value_calculated`, filters by expiry |

#### Database Dependencies

| Query | Location | Cardinality |
|-------|----------|-------------|
| `License.import_license.all()` | Multiple places | 1:N (license : import items) |
| `LicenseImportItemsModel.item_details` (RowDetails) | BOE debit scan | 1:N (item : debit rows) |
| `LicenseImportItemsModel.allotment_details` (AllotmentItems) | Allotment scan | 1:N (item : allotment rows) |
| `LicenseTrade.lines.all()` | Trade aggregates | 1:N (trade : trade lines) |
| `LicenseInwardOutwardModel.license_status` | License status history | 1:N (license : status events) |
| `LicenseTransferModel.transfers` | Ownership history | 1:N (license : transfers) |

---

## 6. TESTS EXISTING

### Test Coverage

**Total Tests:** 85 test files, ~25k LOC, 109+ test classes

### Test Organization

| Category | Files | Focus |
|----------|-------|-------|
| **Balance Calculation** | test_balance_calculator.py, test_balance_cif_single_source.py, test_dashboard_balance_cif.py, test_license_list_balance_consistency.py | Balance engine correctness, live vs. cache, item-level attribution |
| **Ledger Generation** | test_ledger_service.py, test_canonical_ledger_service.py, test_ledger_dual_run.py, test_balance_ledger_views.py | Ledger row assembly, mismatch detection, dual-engine validation |
| **Financial Ledger** | test_bl_ledger_03_cif_attribution.py, test_bl_ledger_03_sibling_scope.py, test_cross_output_parity_option_c.py, test_cross_output_parity_phase_4e_e.py | BOE attribution, allocation netting, parity across output formats |
| **Item Planning** | test_e1_plan.py, test_e5_plan.py, test_e126_plan.py, test_e132_plan.py, test_e1_auto_plan.py, test_e5_auto_plan.py, test_e126_auto_plan.py, test_e132_auto_plan.py | Norm-based auto-planning, split allocation, unit-price optimization |
| **Plan Enforcement** | test_plan_enforcement.py, test_plan_grouping.py, test_plan_utilization.py | Plan line cap gating, group balance caps, utilization tracking |
| **Exports & Reports** | test_item_pivot_*.py (10+ files), test_balance_excel_export.py, test_ledger_pdf_live_balance.py, test_inventory_balance_report.py | Report data assembly, parity with ledger, live balance usage |
| **Integration** | test_allotment (cross-module), test_trade (cross-module), test_reconciliation (cross-module) | BOE/trade/allotment linking, allocation gate, balance updates |
| **Edge Cases** | test_plan_norms_command_live_balance.py, test_auto_plan_all_live_balance.py, test_ledger_available_for_sale_live_balance.py | Live balance usage in bulk operations, stale cache handling |
| **Admin/Sync** | test_delete_licenses_by_exporter_command.py, test_sync_licenses_command.py, test_repair_license_subtables_command.py | Data migration, cleanup, consistency repair |

### Coverage Estimate

**Covered:**
- ✅ Balance calculation (financial, customs, item-level) — extensive golden-master tests
- ✅ Condition pool allocation (2%, 3%, 5%, 10% restrictions)
- ✅ BOE/allotment debit integration
- ✅ Item plan cap enforcement
- ✅ Ledger row generation and mismatch detection
- ✅ Norm-based auto-planning (E1, E5, E126, E132, A3627)
- ✅ Report parity (balance, item pivot, ledger PDF/Excel)
- ✅ Expiry gating and allocation validation
- ✅ Live balance in allocation gate vs. stale denormalized cache

**Known Gaps:**
- ⚠️ **BOE hide/restore signal** — No explicit test that denormalized import_item caches are refreshed (they're not, accepted limitation)
- ⚠️ **Condition pool edge cases** — Limited testing of conflicting condition types on same item
- ⚠️ **Permission boundary testing** — Role-scoped access not exhaustively tested
- ⚠️ **Concurrent allocation** — No race condition testing (allotment creation + balance update)
- ⚠️ **License deletion cascades** — No mass-delete performance testing
- ⚠️ **Custom report SQL** — Some hand-written aggregate queries not covered by parametric tests
- ⚠️ **Reconciliation allocation changes** — Limited testing of BOE/allotment allocation changes cascading to balance recalc

---

## 7. LEGACY CODE

### Old Implementations

| Code | Status | Location | Notes |
|------|--------|----------|-------|
| **`models.py` (pre-split)** | Removed (v2.0) | Historic | ~1.9k LOC file split into `core.py`, `invoice.py`; all references preserved |
| **`calculate_balance()` (Customs engine)** | Active but read-only | balance_calculator.py | Used only for reconciliation self-check; never for allocation gating |
| **`bill_of_entry.tasks.update_balance_values_task`** | Removed | Historic | Async task; replaced with synchronous `update_balance_values()` in signal; comment left for audit trail |
| **`get_item_head_data()`, `oil_queryset` (glass formers)** | Deprecated but active | models/core.py | Legacy item grouping; kept for backward-compat; `get_item_group_data()` is the modern sibling |
| **`import_license_head_grouped` property** | Deprecated alias | models/core.py | Maps to `import_license_group_grouped`; kept for templates |
| **`*_manual` fields** | Unused | Likely removed | No references in active code |

### Unused Exports

**None identified.** All exported classes/functions are in active use (no dead imports found in symbol table).

### Dead Services

**None identified.** Legacy services documented in comments; no inactive service files found.

### Deprecated Views

| View | Status | Replacement |
|------|--------|-------------|
| **LicensePdfParseView** (parse_pdf.py) | Active | Still used for legacy PDF upload; no replacement yet |
| **ItemReportView** (item_report.py) | Active (legacy) | Modern replacement: ItemPivotReportView |
| **PlannedReportView** (planned_report.py) | Active (legacy) | Gradually migrating to ItemPivotReportView |

---

## 8. RISK REGISTER

### Financial Accuracy Risks

| Risk | Severity | Likelihood | Description | Mitigation |
|------|----------|-----------|-------------|-----------|
| **Stale Balance Cache** | HIGH | MEDIUM | `LicenseBalance.balance_cif` not refreshed on BOE hide/restore or reconciliation allocation changes → list views show wrong balance → allocation gating reads wrong cached figure (if accidentally used) | Allocation gating reads `calculate_financial_balance()` live; list views documented as potentially stale; tests enforce live balance usage |
| **BOE Debit Double-Count** | HIGH | LOW | Substituting `calculate_boe_debit_total()` for `calculate_debit()` in Financial Balance formula → BOE rows matched to trades counted twice → balance diverges from ledger | Formula docstring forbids substitution; empirical guard: `calculate_debit()` must match `build_financial_ledger`'s `computed_balance`; self-check via `mismatched` flag |
| **Denormalized Quantity Stale** | MEDIUM | HIGH | `import_item.available_quantity` not updated on reconciliation allocation change → filtering/aggregation uses stale cache → reports show wrong figures | Reports should read live via `balance_calculator.py` bulk methods; denormalized field is a performance optimization, not authoritative |
| **Item CIF Attribution Ambiguity** | MEDIUM | LOW | Zero-CIF import items should fall back to license balance; positive-CIF items should use item-level balance — logic error → wrong availability calculation | Service layer enforces via `ItemBalanceCalculator.has_item_attributed_cif()` and `calculate_item_attributed_balance()` |
| **Condition Pool Overflow** | MEDIUM | MEDIUM | Multiple items with same condition_type (e.g., two "5%" items) share one pool — if item A consumes pool, item B shows wrong available → over-allocation | `condition_pool.remaining_for_condition()` computes pool once per license; must be called BEFORE each item's availability check |
| **0.01 Marker Quantization Loss** | LOW | LOW | Special 0.01 CIF value (signal for "calculate from pool") rounded to 0.00 during quantization → availability calculation breaks | Explicit check in `available_value_calculated`: `if cif_fc == Decimal("0.01"): return Decimal("0.01")` — never quantized |
| **Hidden BOE Exclusion Missed** | MEDIUM | LOW | BOE marked as hidden (OTH marker) but audit trail not confirming "genuine" hide — `annotate_and_exclude_hidden()` still includes it → debit overstated | `annotate_and_exclude_hidden()` applies two-step gate: OTH marker + audit trail confirmation; see docstring |
| **Purchase/Sale CIF Mismatch** | LOW | MEDIUM | Trade line CIF differs from matched BOE CIF (data quality issue) → ledger shows mismatch warning but still uses trade line amount (not BOE amount) → ledger figures diverge from customs reconciliation | Intentional: mismatch is flagged (`build_financial_ledger`'s `mismatch_warning`); trade line is the authoritative financial figure |

### Data Integrity Risks

| Risk | Severity | Likelihood | Description | Mitigation |
|------|----------|-----------|-------------|-----------|
| **Cascade Delete Orphans** | HIGH | LOW | License deletion cascades to 100k+ import items if multi-item license — if process crashes mid-cascade → inconsistent state | No explicit transaction guard; relies on DB atomicity; should wrap delete in explicit transaction if bulk-deleting |
| **Unique Constraint Violation** | MEDIUM | LOW | Creating license with duplicate `license_number` → IntegrityError in production | DB constraint enforced; serializer should validate pre-save |
| **Condition Type Invalid** | LOW | MEDIUM | `condition_type` field accepts free-text (no DB check) — bad value like "7.5%" breaks pool logic | Model docstring lists valid values; no DB validation; should add `in_choices` validator |
| **Serial Number Collision** | LOW | LOW | Two import items with same (license, serial_number) — unique_together constraint prevents insert but error handling may be poor | Constraint is at DB level; serializer should pre-validate |
| **Denormalized Field Staleness** | MEDIUM | HIGH | `available_quantity`, `available_value`, `debited_*`, `allotted_*` fields on import_item not atomically updated with their source data — async updates may lag | Fields are performance optimizations; reading stale values is acceptable for reports; allocation gating reads live |
| **Plan Line Remaining Tracking** | MEDIUM | MEDIUM | `LicenseItemPlan.remaining_quantity/cif` decremented on allotment — if allotment is deleted or reconciliation changes link status, remaining is not incremented back → over-allocated | No reversal logic found; requires explicit reconciliation to fix |

### Concurrency Risks

| Risk | Severity | Likelihood | Description | Mitigation |
|------|----------|-----------|-------------|-----------|
| **Allocation Race Condition** | HIGH | LOW | Two concurrent `allocate_items` requests read balance (pass), both decrement balance concurrently → total decrement > available | No explicit locking; relies on DB transaction isolation (SERIALIZABLE may deadlock); Allotment model may have `get_lock()` |
| **Balance Cache Refresh Lag** | MEDIUM | MEDIUM | Reconciliation allocation saves, triggers `update_license_flags` signal, cache refreshes — meanwhile, another request reads old cache | Cache refresh is atomic with allocation save (via `on_commit()`); gap is minimal but possible in high-concurrency scenarios |
| **Plan Line Decrement Race** | MEDIUM | MEDIUM | Two concurrent allocations decrement same `LicenseItemPlan.remaining_quantity` → race condition on DB update | SQL `UPDATE remaining = remaining - X` should be atomic; no explicit version control |

### Security Risks

| Risk | Severity | Likelihood | Description | Mitigation |
|------|----------|-----------|-------------|-----------|
| **Exporter Scope Bypass** | MEDIUM | LOW | Non-superuser requests license not in their exporter scope → permission check missing in serializer/view | `LicenseDetailsViewSet` has role-based filtering; should verify all endpoints (GET, PATCH, DELETE) |
| **Ledger Unauthorized Access** | LOW | LOW | User without `LicenseLedgerViewPermission` accesses ledger endpoint → permission denied | View enforces permission; guard in `LicenseLedgerViewSet.get_permissions()` |
| **Document File Access** | LOW | LOW | User without license access downloads license PDF/TL document | `ProtectedMediaView` enforces role-scoped access (see BL-LEDGER-02 security review) |
| **Incentive License Visibility** | LOW | LOW | Non-superuser sees IncentiveLicense not in their scope | Filtering likely missing; Incentive is parallel hierarchy, less integrated |
| **Balance Calculation Cache Poisoning** | LOW | LOW | Attacker modifies `LicenseBalance.balance_cif` directly → gating reads wrong value (if it reads cache instead of live) | Live calculation is read; cache is stale-acceptable; direct DB modification would require DB access already compromised |

### Performance Risks

| Risk | Severity | Likelihood | Description | Mitigation |
|------|----------|-----------|-------------|-----------|
| **N+1 in License List** | HIGH | MEDIUM | Rendering license list with balance for 1000 licenses → 1001 queries (license list + 1 balance per license) | Should use `calculate_financial_balance_for_licenses()` batch method; verify view uses this |
| **Item Pivot Aggregation** | MEDIUM | MEDIUM | Item pivot report groups by HSN/item name across 1000s of licenses → full table scan without proper indexes | Indexes on `available_quantity`, `available_value` present; query should use aggregation; verify plan |
| **Denormalized Field Staleness Cascade** | MEDIUM | HIGH | Refreshing `available_quantity` on every BOE save for 1000-item import → 1000 DB updates per BOE | Bulk serializer suspends per-item refresh, does final flush; acceptable for typical BOE (< 100 items) |
| **Condition Pool Recompute** | LOW | MEDIUM | Computing condition pools for every item on a license with 50 items and multiple condition types → O(items * conditions) computation | `compute_condition_pools()` is O(n); bulk version reuses single pool calculation per license |
| **Historical Data Growth** | MEDIUM | HIGH | License ledger rows, transfer records, status history grow unbounded — queries slow over time | No automatic archival strategy; production DB may need partitioning by license_date or periodic cleanup |

---

## ACCEPTANCE CRITERIA FOR AUDIT COMPLETION

- [x] Scope documented (business entities, workflows, integrations)
- [x] Financial calculations documented (formulas, engines, components, precision, rounding, deduplication, correctness)
- [x] Data models documented (structure, keys, constraints, cascades, indexes, denormalization trade-offs)
- [x] Business rules documented (validations, state transitions, permissions, workflows)
- [x] Dependencies documented (inbound/outbound, API contracts, DB dependencies)
- [x] Tests documented (file count, coverage areas, gaps)
- [x] Legacy code documented (old implementations, unused exports, dead services)
- [x] Risk register completed (financial, data integrity, concurrency, security, performance)

---

**Document Generated:** 2026-08-10  
**Audit Scope:** DFIA/License Management (Module 8)  
**Status:** BASELINE DISCOVERY COMPLETE  
**Next Phase:** Risk mitigation planning and remediation roadmap (if requested)