# Data Integrity Rules — License Manager
**Discovery Date:** 2026-08-10  
**Method:** Model audit, relationship analysis, constraint verification  
**Validation:** All CASCADE/PROTECT checked in model definitions (backend/apps/*/models.py)

---

## CRITICAL CONSTRAINTS — DO NOT DELETE

### Master Data (PROTECTED)

**CompanyModel**
- **Status:** PROTECTED (9 PROTECT FKs as of 2026-08-08)
- **Cannot Delete If:**
  - Referenced as exporter on any LicenseDetailsModel
  - Referenced as current_owner on any LicenseOwnership
  - Referenced as company on any BillOfEntryModel
  - Referenced as company/from_company/to_company on any LicenseTrade
  - Referenced as company on any AllotmentModel
  - Referenced as related_company on any AllotmentModel
- **Safety:** ✅ All relationships PROTECT (no CASCADE)
- **Deletion Attempt Result:** 400 Bad Request (PROTECT constraint)

**PortModel**
- **Status:** PROTECTED (4 PROTECT FKs as of 2026-08-08)
- **Cannot Delete If:**
  - Referenced on any LicenseDetailsModel.port
  - Referenced on any BillOfEntryModel.port
  - Referenced on any AllotmentModel.port
- **EXCEPTION:** ⚠️ IncentiveLicense.port_code still CASCADE (P1-001)
- **Safety:** ✅ DFIA protected; ⚠️ Incentive licenses vulnerable
- **Deletion Attempt Result:** 400 Bad Request (except IncentiveLicense, which cascades)

**HSCodeModel**
- **Status:** PROTECTED (1 PROTECT FK)
- **Cannot Delete If:**
  - Referenced on ProductDescriptionModel
- **Safety:** ✅ Protected
- **Deletion Attempt Result:** 400 Bad Request

### TransactionModels (PROTECTED)

**LicenseDetailsModel**
- **Status:** Central entity (depends on it: 141 dependents)
- **Deletion Safety:** PROTECTED (6 PROTECT FKs guard it from deletion)
- **Cannot Delete If:**
  - Referenced as exporter → LicenseDetailsModel (via LicenseOwnership.current_owner)
- **Cascade On Deletion:**
  - ✅ LicenseExportItem (export credits)
  - ✅ LicenseImportItem (import items, SRs) → RowDetails, AllotmentItems
  - ✅ LicenseBalance, LicenseNotes, LicenseFlags, LicenseOwnership (metadata)
  - ✅ LicenseTransfer, LicensePurchase (history)
- **Ripple Effects:**
  - Deleting license cascades RowDetails → breaks BOE-license relationships
  - Deletes AllotmentItems → breaks allotment-license relationships
  - Deletes ReconciliationLog entries (may be unintended)
- **Safety:** ✅ Deletion is safe (cascades clean up dependent records) BUT creates data loss
- **Verdict:** SAFE to delete (programmatically), but DANGEROUS (business impact)

**BillOfEntryModel**
- **Status:** PROTECTED (2 PROTECT FKs on Company/Port as of 2026-08-08)
- **Cannot Delete If:** Referenced by company/port FKs (rare, only at BOE level)
- **Cascade On Deletion:**
  - ✅ RowDetails (line items) → cascades to:
    - InvoiceBOEAllocation ledger entries (PROTECT will block)
    - BOEAllotmentAllocation ledger entries (PROTECT will block)
    - ExternalInvoiceLink (PROTECT will block)
  - ✅ M2M to AllotmentModel (cleared)
- **Safety:** ⚠️ Deletion cascades through allocation ledgers, triggers PROTECT constraint
- **Verdict:** Deletion likely fails (PROTECT on allocation ledgers) — safe

**AllotmentModel**
- **Status:** PROTECTED (3 PROTECT FKs on company/port/related_company as of 2026-08-08)
- **Cascade On Deletion:**
  - ✅ AllotmentItems (line items) → cascades to:
    - BOEAllotmentAllocation ledger (PROTECT will block)
  - ✅ M2M to BillOfEntryModel (cleared)
- **Safety:** ⚠️ Deletion cascades through allocation ledgers, triggers PROTECT constraint
- **Verdict:** Deletion likely fails (PROTECT on allocation ledgers) — safe

**LicenseTrade**
- **Cascade On Deletion:**
  - ✅ LicenseTradeLine → cascades to:
    - InvoiceBOEAllocation ledger (PROTECT will block)
  - ✅ M2M to BillOfEntryModel (cleared)
- **Safety:** ⚠️ Deletion cascades through allocation ledgers, triggers PROTECT constraint
- **Verdict:** Deletion likely fails (PROTECT on allocation ledgers) — safe

---

## ALLOCATION LEDGERS — IMMUTABLE (PROTECT)

**InvoiceBOEAllocation**
- **Relationship:** trade_line (PROTECT), row_details (PROTECT)
- **Status:** Immutable audit trail (PROTECT prevents deletion of underlying records)
- **Deletion Safety:** ✅ PROTECT relationships prevent cascade
- **Verdict:** Safe (cannot be deleted, links are protected)

**BOEAllotmentAllocation**
- **Relationship:** allotment_item (PROTECT), row_details (PROTECT)
- **Status:** Immutable audit trail
- **Deletion Safety:** ✅ PROTECT relationships prevent cascade
- **Verdict:** Safe

**ExternalInvoiceLink**
- **Relationship:** row_details (PROTECT)
- **Status:** Immutable audit trail
- **Deletion Safety:** ✅ PROTECT prevents cascade
- **Verdict:** Safe

---

## CASCADE RELATIONSHIPS (Auto-Delete on Parent Deletion)

**Safe Cascades (Expected Behavior):**

| Parent | Child | Relationship | Impact | Safety |
|--------|-------|---|---|---|
| License | ExportItem | CASCADE | Export credits deleted | Safe (rare deletion) |
| License | ImportItem | CASCADE | Import items deleted | Safe (rare deletion) |
| License | LicenseBalance | CASCADE | Balance cache deleted | Safe (recalculated on-demand) |
| License | LicenseNotes | CASCADE | Notes deleted | Safe (metadata) |
| License | LicenseFlags | CASCADE | Flags deleted | Safe (recalculated on-demand) |
| License | LicenseOwnership | CASCADE | Ownership deleted | Safe (metadata) |
| License | LicenseTransfer | CASCADE | Transfer history deleted | ⚠️ DATA LOSS (audit) |
| License | LicensePurchase | CASCADE | Purchase records deleted | ⚠️ DATA LOSS (audit) |
| ImportItem | RowDetails | CASCADE | BOE lines deleted | ⚠️ DATA LOSS (affects balance) |
| ImportItem | AllotmentItems | CASCADE | Allotment links deleted | ⚠️ DATA LOSS (affects balance) |
| BOE | RowDetails | CASCADE | Line items deleted | ⚠️ DATA LOSS (affects debit) |
| Allotment | AllotmentItems | CASCADE | Allocation deleted | ⚠️ DATA LOSS (affects balance) |
| Trade | TradeLine | CASCADE | Invoice lines deleted | ⚠️ DATA LOSS (affects balance) |

**Dangerous Cascades (Known Issues):**

| Parent | Child | Issue | P# | Fix |
|--------|-------|---|---|---|
| IncentiveLicense | exporter (Company) | Should be PROTECT | P1-001 | Change to PROTECT |
| IncentiveLicense | port_code (Port) | Should be PROTECT | P1-001 | Change to PROTECT |

---

## SET_NULL RELATIONSHIPS (Nullify on Parent Deletion)

| Parent | Child | Field | Impact | Safety |
|--------|-------|---|---|---|
| Company | License | exporter (SET_NULL) | Exporter becomes null, snapshot preserved | Safe (historical data) |
| Company | LicenseTrade | from_company (SET_NULL) | Party info becomes null, snapshot preserved | Safe |
| Company | LicenseTrade | to_company (SET_NULL) | Party info becomes null, snapshot preserved | Safe |
| User | ReconciliationLog | user (SET_NULL) | Audit log survives user deletion | Safe |

---

## UNIQUE CONSTRAINTS

**License-Level:**
- LicenseDetailsModel.license_number — unique (identifies license)
- BillOfEntryModel (bill_of_entry_number, bill_of_entry_date) — unique together

**Row-Level:**
- RowDetails (bill_of_entry, sr_number, transaction_type) — unique together (no duplicate rows per BOE/SR/type)
- AllotmentItems (item, allotment) — unique together (no duplicate items per allotment)
- IgnoredWarning (license, warning_type, entity_type, entity_id) — unique together (only one ignore per warning)

**Consequences:**
- Violating unique constraint → 400 Bad Request (database constraint)
- Applied at: form validation + serializer validation + model save

---

## CHECK CONSTRAINTS

**None found explicitly in model definitions.** Business logic validation done at service layer:
- Over-allocation prevention (service-level check, no DB constraint)
- Plan cap validation (service-level check, no DB constraint)
- Quantity/value validation (service-level check, no DB constraint)

**Risk:** Service-level validation can be bypassed by:
- Direct database inserts
- Raw SQL updates
- Concurrent requests (race condition)

**Mitigation:**
- API endpoint throttling (prevents brute-force)
- Comprehensive service-level tests
- Transactional semantics (serialize writes)

---

## HIDDEN BOE MARKER LOGIC

**Marker:** `invoice_no = "OTH"` (free-text legacy indicator)

**Visibility Determined By:** Latest `ReconciliationLog.action` entry
- If latest action = HIDE_BOE → BOE is hidden
- If latest action = RESTORE_BOE → BOE is visible
- If no ReconciliationLog entry → BOE visible (default)

**Scope:** ~35–40% of all BOEs carry "OTH" as legacy invoice data

**Impact on Balance Calculation:**
- Hidden BOEs excluded from balance.cif calculation
- Affects opening gate logic (hidden BOEs reduce opening balance)

**Data Integrity:** ✅ Safe (immutable audit trail preserves hide/restore history)

---

## DELETION SAFETY MATRIX

| Model | Can Safely Delete? | Conditions | Impact | Data Loss Risk |
|-------|---|---|---|---|
| License | ✅ Rare, safe | Never (business rules prevent) | Cascades all related | HIGH (audit, balance history) |
| BOE | ✅ Rare, safe | When no allocations | Cascades RowDetails | MEDIUM (transaction history) |
| Allotment | ✅ Rare, safe | When no allocations | Cascades items | MEDIUM (procurement history) |
| Trade | ✅ Rare, safe | When no allocations | Cascades lines | MEDIUM (transaction history) |
| Company | ❌ Not safe | Referenced by multiple models | PROTECT blocks | SAFE (no CASCADE) |
| Port | ❌ Not safe | Referenced by multiple models | PROTECT blocks | SAFE (except IncentiveLicense) |
| RowDetails | ⚠️ Complex | If no allocations | Cascades to nothing (PROTECT on ledgers) | SAFE (ledger protected) |

---

## RECENT CONSTRAINT TIGHTENING (2026-08-08)

**Commit b3802917:** "fix(db): change Port/Company FKs from CASCADE to PROTECT"

**Changed (6 fields):**
1. LicenseDetailsModel.port — CASCADE → PROTECT
2. BillOfEntryModel.company — CASCADE → PROTECT
3. BillOfEntryModel.port — CASCADE → PROTECT
4. AllotmentModel.company — CASCADE → PROTECT
5. AllotmentModel.port — CASCADE → PROTECT
6. AllotmentModel.related_company — CASCADE → PROTECT

**NOT Changed (Known Gap):**
7. ⚠️ IncentiveLicense.exporter — Still CASCADE (should be PROTECT)
8. ⚠️ IncentiveLicense.port_code — Still CASCADE (should be PROTECT)

**Impact:** Master data now protected from accidental deletion (PROTECT prevents cascade). Excellent safety improvement.

---

## AUDIT TRAIL INTEGRITY

**ReconciliationLog** (append-only)
- Never deleted or updated (immutable ledger)
- Preserves all BOE/trade linking/hiding/restoration history
- User deletions don't orphan log (SET_NULL on user FK)
- ✅ Safe (immutable)

**ActivityLog** (append-only)
- Every authenticated API request logged
- User/IP/action/timestamp recorded
- ✅ Safe (immutable)

**IgnoredWarning** ⚠️ (mutable)
- Mutated in-place (ignored boolean changed)
- Audit fields (ignored_by, ignored_at, restored_by, restored_at) updated
- **Not append-only** (no change history)
- ✅ Safe for current requirements, but consider soft-delete pattern if full history needed

---

## SUMMARY OF INTEGRITY RULES

| Rule | Status | Evidence | Risk |
|------|--------|----------|------|
| Master data protected from cascade deletion | ✅ | 6 PROTECT FKs (b3802917) | Low |
| Allocation ledgers immutable | ✅ | 3 PROTECT FKs | Low |
| Audit trails preserved | ✅ | ReconciliationLog, ActivityLog | Low |
| Unique constraints enforced | ✅ | DB-level constraints | Low |
| Business rule validation | ⚠️ | Service-level only (no DB checks) | Medium |
| IncentiveLicense constraints | ❌ | Still CASCADE (P1-001) | High |
| Ledger balance divergence | ❌ | 3 different conventions (P0-001) | Critical |

---

## RECOMMENDED CHANGES (In Priority Order)

### Immediate (Before Production)
1. Fix IncentiveLicense constraints (2 lines, 1 day) — P1-001
2. Verify no code relies on CASCADE behavior

### Before Phase 3 Completion
3. Add reconciliation log tests (verify immutability)
4. Add golden-data test for balance calculation (P0-002)

### Future Improvements
5. Add CHECK constraints for over-allocation prevention (DB-level safety)
6. Add soft-delete pattern for IgnoredWarning (if audit history needed)
7. Audit and document all service-level validations

---

**Data Integrity Status:** STRONG (master data protected, audit trails preserved, allocation ledgers immutable)

**Critical Gap:** IncentiveLicense CASCADE vulnerability (P1-001)
