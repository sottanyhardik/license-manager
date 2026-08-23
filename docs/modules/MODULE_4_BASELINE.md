Now I'll create the comprehensive baseline document based on my audit findings:

## MODULE_4_BASELINE.md

```markdown
# MODULE 4 BASELINE: BOE / Import Utilization (bill_of_entry app)

## 1. SCOPE

### What does this module manage?
Module 4 manages Bills of Entry (BOE) — the authoritative ledger of physical import documents from Indian Customs (ICEGATE). A BOE represents one customs import clearance, containing multiple item rows (`RowDetails`), each debiting a license's import balance.

### Business entities involved
- **BillOfEntryModel**: Customs import document (unique by bill_of_entry_number + bill_of_entry_date)
  - Attributes: number, date, port, company, product_name, exchange_rate
  - Links: FK to Port, Company; M2M to Allotment (source of items)
  - Special: `invoice_no` field doubles as hidden-BOE marker (value "OTH")

- **RowDetails**: One line item on a BOE (imports for a specific license item)
  - Attributes: qty, cif_fc (foreign currency), cif_inr (INR equivalent)
  - Links: FK to BillOfEntryModel, FK to LicenseImportItemsModel (sr_number)
  - Flags: `is_frozen` (read-only if from ledger upload), `is_dispute` (flagged if missing in ledger reconciliation)
  - Type: Always DEBIT transaction_type (bills of entry are debits)

### Key workflows
1. **BOE Ingestion**: PDF→parsing (PDF text extraction regex) OR manual entry
   - PDF parser extracts: BE number, date, port, company, exchange rates, invoice summary, item details, license references
   - Manual: user uploads item details via web form
   - Exchange rate auto-calculated from row totals (cached_property, triggers on save)

2. **BOE-License Linking**: RowDetails per license item
   - One BOE can debit multiple licenses (M2M via item rows)
   - One BOE can debit same license on multiple items (RowDetails.sr_number)
   - unique_together = (bill_of_entry, sr_number, transaction_type) prevents duplicate rows

3. **BOE-Allotment Association**: M2M link
   - BOE lists source allotments (context for financial tracking)
   - Allotment→BOE link via `fetch_allotment_item_details` (form population)

4. **BOE-Invoice Reconciliation** (Phase A):
   - Manual allocation: user links BOE row to SALE trade line via `InvoiceBOEAllocation` record
   - Legacy tag: trade.boes M2M (deprecated, still supported for backward compat)
   - Reconciliation status: Matched / Pending / Unmatched (per BOE & per row)

5. **Hidden BOE** (previous-owner utilisation):
   - Mark BOE as OTH to exclude from balance/debit calculations (via hide_boe service)
   - `invoice_no == "OTH"` + latest ReconciliationLog.ACTION_HIDE_BOE = genuinely hidden
   - BOE-level: hiding applies to ALL licenses the BOE touches
   - Audit trail: ReconciliationLog records every hide/restore with reason, preserves original invoice_no

6. **BOE Maintenance**:
   - Merge two BOEs (move RowDetails, transfer allotments)
   - Dispute resolution (clear is_dispute flag)
   - Product-name generation from linked items

### Integration points
- **License app**: RowDetails.sr_number links to LicenseImportItemsModel; debit calculations consume BOE rows
- **Allotment app**: M2M association; BOE may source from allotments
- **Trade app**: LicenseTrade.boes M2M (legacy); InvoiceBOEAllocation links rows to trade lines
- **Reconciliation app**: InvoiceBOEAllocation, BOEAllotmentAllocation, ExternalInvoiceLink, ReconciliationLog manage BOE→Invoice and BOE→Allotment consumption
- **Core app**: Exchange rate fetching; materialized views on BOE data

---

## 2. FINANCIAL CALCULATIONS

### What values are calculated?
1. **BOE-level totals** (cached_property, recalculated on RowDetails save/delete):
   - `get_total_fc`: Sum of RowDetails.cif_fc
   - `get_total_inr`: Sum of RowDetails.cif_inr
   - `get_total_quantity`: Sum of RowDetails.qty
   - `get_unit_price`: get_total_fc / get_total_quantity (3dp, ROUND_HALF_UP)
   - `get_exchange_rate`: get_total_inr / get_total_fc (3dp, ROUND_HALF_UP)
   - `exchange_rate` field: Persisted computed rate (only auto-updates if diff > 1)

2. **License-level debit** (from LicenseBalanceCalculator):
   - `calculate_boe_debit_total`: Sum of RowDetails.cif_fc for DEBIT rows (raw, unconditional)
   - `calculate_debit`: Allocation-netted debit = Σ(cif_fc - min(cif_fc, allocated)) for each row
     - Used by Financial Ledger's "BOE Pending" row
     - Allocation sum from InvoiceBOEAllocation.allocated_cif_fc per row
   - `calculate_hidden_boe_debit_total`: Sum of cif_fc for genuinely-hidden rows (excluded from balance)
   - Balance CIF: Uses raw `calculate_boe_debit_total`, NOT netted debit

3. **Hidden BOE detection** (binary classification):
   - `annotate_and_exclude_hidden`: Queryset filter combining invoice_no="OTH" + latest ReconciliationLog check
   - `genuinely_hidden_boe_ids`: Python-side set of hidden BOE ids (no N+1, one query per batch)
   - Rationale: ~35-40% of all BOEs have invoice_no="OTH" as legacy free-text; only OTH + latest log entry "HIDE_BOE" = genuinely hidden

### Where are calculations done?
- **BillOfEntryModel.save()**: Recalc exchange_rate from row totals (triggers when pk exists)
- **_recalculate_boe_exchange_rate()**: Atomic .update() variant (skips signal re-trigger)
- **RowDetails.post_save/post_delete signals**: Synchronously call balance update (via transaction.on_commit)
- **LicenseBalanceCalculator** (license/services/balance_calculator.py): 
  - `get_debit_rows()`: Annotated RowDetails with allocated/linked_excluded/matched/contributed
  - `calculate_debit()`: Sum contributed (= cif_fc - matched)
  - `calculate_boe_debit_total()`: Raw sum of cif_fc
  - `resolve_boes_represented_by_invoice[_for_licenses]()`: Checks formal allocation + legacy trade.boes tags

### Are there duplicates?
**No intentional duplicates, but risk of divergence:**
- LicenseBalanceCalculator.get_debit_rows + Financial Ledger builder both fetch RowDetails rows
- LicenseBalanceLedgerBuilder.build_financial_ledger breaks down rows into Matched/Pending/Unmatched status — reuses same annotations as balance engine, not independent recomputation
- PDF/Excel exporters call same builder, not their own calc
- **Risk**: If get_debit_rows' annotation logic drifts, all three outputs silently diverge. Mitigation: builder is documented as "read-only breakdown of annotated querysets," never recalculates.

### Formula correctness

#### BOE-level totals
- All three use `Coalesce(Sum(...), Value(DEC_0))` to handle NULL aggregates → 0
- quantize() to 0 dp (DEC_0) or 3 dp (DEC_000) per field
- Unit price: `get_total_fc / qty` with 3dp ROUND_HALF_UP (tolerance for precision loss)
- Exchange rate: `get_total_inr / get_total_fc` with 3dp ROUND_HALF_UP

#### License debit
- `contributed` = max(cif_fc - matched, 0) where matched = min(cif_fc, allocated + linked_excluded)
- allocated = Σ InvoiceBOEAllocation.allocated_cif_fc (ACTIVE, is_current=True, per row)
- linked_excluded = full cif_fc IF bill_of_entry_id in represented set AND allocated=0, else 0
  - represented set = {BOE ids with >=1 active InvoiceBOEAllocation on any row} ∪ {legacy trade.boes tags}
- Combined: a row with partial formal allocation (e.g. 300/1000) keeps 700 visible; a legacy-tagged row with NO allocation gets full 1000 excluded

### Precision requirements
- cif_fc, cif_inr: 15 max_digits, 3 decimal places (Decimal("0.001") granularity)
- allocated fields (InvoiceBOEAllocation, BOEAllotmentAllocation): 20 max_digits, 3 decimal places (covers larger LicenseTradeLine.cif_fc: 20, 2)
- qty: 15,3 in RowDetails; 20,4 in allocation records
- exchange_rate: 12,4 on BillOfEntryModel; 3dp on computed rate
- Debit totals: quantized to 2dp (DECIMAL_CENT) for display via quantize_2dp()

### Rounding rules
- BOE-level rates: ROUND_HALF_UP to 3dp
- Debit summary: ROUND_HALF_UP to 2dp
- TOLERANCE = Decimal("10.00") for CIF mismatch warnings in Financial Ledger (not enforced, only flagged)
- No active cascading rounding (each calculation stands alone)

---

## 3. DATA MODELS

### Key models
1. **BillOfEntryModel**
   - Primary key: id (auto)
   - Unique constraint: (bill_of_entry_number, bill_of_entry_date)
   - Indexes: 7 (number, company+date, port+date, date, invoice_no+invoice_date, is_fetch, product_name)

2. **RowDetails**
   - Primary key: id (auto)
   - Unique constraint: (bill_of_entry, sr_number, transaction_type)
   - No explicit indexes (relies on FK indexes)
   - Meta: ordered by transaction_type, bill_of_entry_date

### Foreign keys
- BillOfEntryModel.company → CompanyModel (PROTECT)
- BillOfEntryModel.port → PortModel (PROTECT)
- BillOfEntryModel.allotment → AllotmentModel (M2M, blank=True)
- RowDetails.bill_of_entry → BillOfEntryModel (CASCADE)
- RowDetails.sr_number → LicenseImportItemsModel (CASCADE)

### Constraints
- BillOfEntryModel: unique_together (bill_of_entry_number, bill_of_entry_date); constraints on indexes
- RowDetails: unique_together (bill_of_entry, sr_number, transaction_type)
- InvoiceBOEAllocation: CheckConstraint (allocated_qty, allocated_cif_fc, allocated_cif_inr ≥ 0)
- BOEAllotmentAllocation: CheckConstraint (allocated_qty, allocated_cif_fc, allocated_cif_inr ≥ 0)

### Cascade settings
- RowDetails.bill_of_entry → CASCADE (delete BOE = delete all rows)
- RowDetails.sr_number → CASCADE (delete import item = delete associated BOE rows)
- InvoiceBOEAllocation.trade_line → PROTECT (cannot delete a trade line with allocations)
- InvoiceBOEAllocation.row_details → PROTECT (frozen rows cannot be deleted without unallocating)
- BOEAllotmentAllocation.row_details → PROTECT (same)
- ExternalInvoiceLink.row_details → PROTECT

### Indexes
**BillOfEntryModel** (7 indexes):
- bill_of_entry_number (prefix scan for lookup)
- (company, bill_of_entry_date) (company ledger queries)
- (port, bill_of_entry_date) (port-based views)
- bill_of_entry_date (date range filters)
- (invoice_no, invoice_date) (reconciliation queries)
- is_fetch (fetch vs. manual filter)
- product_name (text search fallback)

**RowDetails**: No explicit indexes (will use BillOfEntryModel FK + sr_number FK by default)
- Implicit: bill_of_entry_id, sr_number_id, transaction_type
- Consider adding: (sr_number, transaction_type) for debit row lookups per license item

**InvoiceBOEAllocation**: 2 indexes
- status (query for ACTIVE rows)
- is_current (version filter)

**BOEAllotmentAllocation**: same 2 indexes

**ReconciliationLog**: indexed on created_on (implicit from ordering)

---

## 4. BUSINESS RULES

### Validations
1. **BOE Uniqueness**: bill_of_entry_number + bill_of_entry_date (no two BOEs on same date with same number)
2. **Row Uniqueness**: (bill_of_entry, sr_number, transaction_type) per BOE (no duplicate import items on a single BOE)
3. **Frozen Row Protection**: RowDetails.is_frozen=True → .save() is silently blocked (immutable once frozen)
4. **Non-negative Amounts**: All cif_fc, cif_inr, qty ≥ 0 (DB constraints + validators)
5. **Exchange Rate Validity**: ≥ 0 (MinValueValidator); auto-computed when BOE has rows
6. **Invoice No Collision**: No validation on duplicate invoice_no values (many real BOEs share "OTH")
7. **Allotment Uniqueness**: M2M does not enforce deduplication (same AllotmentModel can appear multiple times)

### State transitions
1. **BOE Lifecycle**:
   - Created (manual entry or PDF parse) → invoice_no blank/null
   - Invoiced → invoice_no filled (e.g. "INV-2026-001")
   - Hidden (previous owner) → invoice_no = "OTH"
   - Restored (unhide) → invoice_no restored from ReconciliationLog

2. **Row States**:
   - Created (from BOE or import) → is_frozen=False, is_dispute=False
   - Ledger frozen → is_frozen=True (from ledger upload, read-only)
   - Disputed → is_dispute=True (missing from ledger reconciliation)
   - Cleared (user resolves dispute) → is_dispute=False

3. **Allocation States** (InvoiceBOEAllocation):
   - Created (user formal link) → status=ACTIVE, is_current=True
   - Edited (user changes amount) → old: is_current=False, superseded_by=new; new: status=ACTIVE, is_current=True, version++
   - Reversed → status=REVERSED, is_current=False (never deleted)
   - Never transitions back to ACTIVE once REVERSED

### Permission requirements
- **View BOE**: BillOfEntryPermission (role-based, checked in views)
- **Edit BOE**: BillOfEntryPermission + create/update methods
- **Hide/Restore BOE**: Requires user context (stored in ReconciliationLog); also BillOfEntryPermission
- **Merge BOE**: BillOfEntryPermission + validation (no protected duplicate rows)

### Workflow constraints
1. **BOE Merge**:
   - Target must exist; source must exist
   - Cannot merge BOE with itself
   - Duplicate sr_number+transaction_type rows are skipped (source row deleted via cascade)
   - If skipped row has reconciliation records (InvoiceBOEAllocation, etc.), merge is rejected (bounded query check)
   - Allotments transferred (added to target.allotment M2M)
   - Source is deleted (unmoved rows cascade-delete)

2. **Hide/Restore**:
   - Hide: any invoice_no value is preserved in ReconciliationLog.before["invoice_no"]
   - Restore: only acts if current invoice_no == "OTH"; reads preserved value from latest HIDE_BOE log
   - Cross-license: BOE hiding affects all licenses its RowDetails rows touch (not scoped to one)
   - Recompute: every touched license's flags are updated (balance recalc, flags set)

3. **Dispute Resolution**:
   - is_dispute flag is user-settable
   - Clearing clears flag on ALL rows of that BOE
   - No validation (user can clear even if row still missing from ledger)

---

## 5. DEPENDENCIES

### What modules does this depend on?

**Tight coupling** (imports in boe models/services):
- **license.models**: LicenseImportItemsModel (FK: RowDetails.sr_number)
- **license.signals**: update_license_flags() called after hide/restore to recompute affected licenses
- **license.services.balance_calculator**: exclude_hidden() used in debit calculations
- **core.models**: CompanyModel (FK), PortModel (FK), AuditModel (base)
- **core.constants**: DEC_0, DEC_000, DEBIT transaction type
- **reconciliation.models**: ReconciliationLog, InvoiceBOEAllocation, BOEAllotmentAllocation (FK protection)

**Medium coupling** (views/serializers):
- **allotment.models**: AllotmentModel (M2M), fetch_allotment_item_details() in form population
- **trade.models**: LicenseTrade.boes M2M (legacy tag support)
- **core.views.master_view**: MasterViewSet base class

**Loose coupling** (data consumers):
- **license.services.exporters**: license_balance_pdf, license_balance_excel (call builder, not direct calc)
- **license.services.license_balance_ledger_builder**: Builds Financial Ledger rows from annotated RowDetails (reads, doesn't write)
- **license.views.license_balance_ledger**: JSON API consumer of builder

### What modules depend on this?

**Tight coupling** (rely on BOE presence/calculations):
- **license**: balance_calculator, debit calculations, views
- **reconciliation**: allocation models, BOE hide/restore, reconciliation queries
- **trade**: legacy .boes M2M, trade-to-BOE linking

**Medium coupling**:
- **allotment**: management command checks is_boe flag (update_is_boe.py)
- **core**: cached views on BOE data, materialized views refresh, media view access control (BOE PDFs)

**Loose coupling**:
- **accounts**: permissions checks (BillOfEntryPermission)
- **activity logs**: middleware logs BOE CRUD

### API contracts

**Service layer** (boe_service.py):
- `update_product_name_for_boe(boe)` → {success, product_name, message}
- `bulk_update_product_names()` → {success, total, updated, skipped, message}
- `fetch_allotment_item_details(allotment_id, boe_id)` → {exchange_rate, product_name, port, company, item_details[]}
- `resolve_dispute(boe)` → {success, cleared, message}
- `merge_boe(target, source_id)` → {success, message, boe[serialized]}
- `update_invoice_no(boe, invoice_no)` → {id, invoice_no, message}
- `hide_boe(boe, user, reason)` → {id, is_hidden, invoice_no, previous_invoice_no, hidden_by, hidden_at}
- `restore_boe(boe, user, reason)` → {id, is_hidden, invoice_no, restored_by, restored_at}
- `hide_boes_bulk(ids, user, reason)` → {hidden[], failed[], licenses_refreshed[], hidden_by, hidden_at}
- `restore_boes_bulk(ids, user, reason)` → {restored[], skipped[], failed[], licenses_refreshed[], restored_by, restored_at}

**View layer** (BillOfEntryViewSet):
- `GET /bill-of-entries/` → List with filters (company, port, date range, is_fetch, search)
- `GET /bill-of-entries/{id}/` → Retrieve with nested item_details
- `POST /bill-of-entries/` → Create BOE with item_details
- `PATCH /bill-of-entries/{id}/` → Update BOE (inline editing of invoice_no enabled)
- `DELETE /bill-of-entries/{id}/` → Delete BOE (cascades RowDetails)
- `POST .../bulk_update_product_names/` → Bulk action
- `POST .../fetch_allotment_details/` → Fetch allotment for form population
- `GET .../available_licenses/` → (Allotment module) list available items for BOE
- `POST .../allocate_items/` → (Allotment module) allocate items to BOE
- `POST .../generate_pdf/` → Generate transfer letter
- `POST .../generate_transfer_letter/` → Generate transfer letter with license copies
- `POST /bill-of-entries/parse-pdf/` → Parse PDF → extract data → return dict for manual review

### Database dependencies
- **Core**: CompanyModel, PortModel tables (no direct data dependency, just FKs)
- **License**: LicenseImportItemsModel, LicenseDetailsModel (RowDetails.sr_number → LicenseImportItemsModel; hide/restore reads LicenseDetailsModel)
- **Trade**: LicenseTrade.boes M2M join table
- **Reconciliation**: InvoiceBOEAllocation, BOEAllotmentAllocation join tables (foreign key protection)

---

## 6. TESTS EXISTING

### Test file locations
- `/backend/apps/bill_of_entry/tests/test_boe_hide_service.py` — Hide/restore logic (main unit tests)
- `/backend/tests/test_api_boe.py` — API endpoint tests (CRUD, filters)
- `/backend/tests/test_boe_script_helpers.py` — PDF parsing helpers
- `/backend/apps/license/tests/test_boe_invoice_representation.py` — BOE-invoice allocation tests (phase A)
- `/backend/apps/license/tests/test_license_overview_boes_view.py` — BOE overview view tests
- `/backend/apps/reconciliation/tests/test_boe_link_reconciler.py` — Reconciliation candidate detection
- `/backend/apps/reconciliation/tests/test_backfill_boe_allocations_command.py` — Backfill command
- `/backend/apps/license/tests/test_balance_calculator.py` — Debit calculations with BOE
- `/backend/apps/license/tests/test_balance_ledger_views.py` — Financial ledger with BOE rows
- `/backend/apps/license/tests/test_ledger_characterization_option_c.py` — BOE in balance formula

### Test count estimate
- ~150+ tests directly on BOE (hide/restore, API, reconciliation, debit calculations)
- ~400+ tests indirectly use BOE (all license balance tests create BOE fixtures)

### Coverage estimate
- **Models** (BillOfEntryModel, RowDetails): ~85% (cached_property logic, signals, constraints)
- **Services** (boe_service): ~95% (hide/restore, merge, product name generation)
- **Serializers**: ~70% (nested validation not extensively tested)
- **Views**: ~60% (basic CRUD, filters; advanced features like PDF parse less tested)
- **Integration**: ~80% (BOE→License→Balance chain)

### Known gaps
1. **PDF Parsing**: Regex patterns tested in isolation, but end-to-end PDF ingestion not heavily exercised (only happy path)
2. **Ledger Frozen Flag**: is_frozen logic (read-only from ledger) has minimal test coverage
3. **Exchange Rate Recalc**: Auto-recalc on RowDetails save tested, but edge cases (division by zero, extreme values) sparse
4. **Concurrent Merges**: Merge atomicity under concurrent requests not tested
5. **Bulk Hide/Restore**: Bulk operations tested separately, but interaction with concurrent balance recalcs unclear
6. **Error Handling**: Service layer error cases (AllotmentModel.DoesNotExist, etc.) partially covered
7. **M2M Allotment Deduplication**: Not validated/tested (same AllotmentModel can appear twice)
8. **Performance**: No load tests on BOE-heavy licenses (1000+ rows, 100+ BOEs)

---

## 7. LEGACY CODE

### Old implementations
1. **RowDetails.is_hidden column** (REMOVED)
   - Replaced by BillOfEntryModel.invoice_no == "OTH" + ReconciliationLog marker
   - Reason: BOE-level hiding must apply to all licenses at once; row-level column can't enforce this
   - Migration: N/A (no down-grade path; OTH marker is forward-only)

2. **License-scoped hide_boe_for_license()** (REMOVED)
   - Replaced by BOE-level `hide_boe()` affecting all touched licenses
   - Old behavior: hide only for one license; new: hide uniformly for all licenses
   - Breaking change documented in test file comment

3. **Direct RowDetails.is_hidden checks** (REPLACED)
   - Old: simple `.filter(is_hidden=True)` or `.exclude(is_hidden=False)`
   - New: `annotate_and_exclude_hidden()` subquery combining invoice_no + log entry check
   - Reason: ~35-40% collision with legitimate "OTH" values in legacy data

### Unused exports
- None identified (all public functions in boe_service are used)

### Dead services
- None identified (all services actively called)

### Deprecated views
- None formally deprecated; legacy trade.boes M2M still supported but superseded by InvoiceBOEAllocation

---

## 8. RISK REGISTER

### Financial accuracy risks

**HIGH**:
1. **Hidden BOE Detection Collision** (invoice_no="OTH" collision with legacy data)
   - ~35-40% of BOEs legitimately carry "OTH" as free-text invoice data
   - Mitigation: Subquery check on ReconciliationLog.latest_action; not DB constraint, requires log entry
   - **Residual Risk**: Log entries can be absent (BOEs hidden before feature existed); these remain visible. Also, if log entry is deleted (shouldn't happen, but possible via raw SQL), collision re-surfaces.

2. **Exchange Rate Calculation Drift**
   - Computed as get_total_inr / get_total_fc
   - Stored value only updated if diff > 1 (prevents spurious writes)
   - **Risk**: If rows are manually deleted without recalc, rate stales; if rows added in bulk without signal, rate not updated
   - **Mitigation**: Signals on RowDetails.post_save/post_delete; bulk_update bypasses signals

3. **Allocation Netting in Debit**
   - contributed = max(cif_fc - min(cif_fc, allocated + linked_excluded), 0)
   - **Risk**: Partial allocation logic is complex; a row with 300/1000 allocated must leave 700 visible. Netting at multiple levels (allocated + linked_excluded) can hide precision loss.
   - **Mitigation**: Tests cover partial allocation; Decimal precision (20,3) is generous

4. **BOE-to-Multiple-License Span**
   - A single BOE can debit multiple licenses; hiding hides for all at once
   - **Risk**: User intends to hide for one license, accidentally hides for others
   - **Mitigation**: UI clearly shows affected licenses; confirmation required; audit trail (ReconciliationLog)

### Data integrity risks

**MEDIUM**:
1. **Cascade Delete on RowDetails Removal**
   - Deleting a BillOfEntryModel cascades delete of all RowDetails
   - **Risk**: If RowDetails has live InvoiceBOEAllocation / BOEAllotmentAllocation, those FKs are PROTECT-constrained, blocking the delete. But if allocation is manually deleted first, RowDetails cascade succeeds, orphaning trade/allotment side references.
   - **Mitigation**: FK protection on allocation records; merge operation explicitly checks for protected duplicates before proceeding

2. **Frozen Row Immutability**
   - RowDetails.is_frozen=True → .save() silently returns (no-op)
   - **Risk**: User thinks they saved a change; no error raised; data silently unchanged
   - **Mitigation**: View layer should check is_frozen before allowing edit form; client-side read-only flag

3. **Unique Constraint Violation on Merge**
   - Merge skips duplicate (bill_of_entry, sr_number, transaction_type) rows
   - **Risk**: Skipped row stays on source BOE, then source BOE is deleted, row is cascade-deleted
   - **Mitigation**: Merge checks for protected duplicates before any mutation; if found, rejects entire merge

4. **Manual .update() on Frozen Rows During Ledger Upload**
   - Ledger upload bulk_updates RowDetails; boe_service.merge_boe() also uses .update() to bypass is_frozen guard
   - **Risk**: Direct SQL mutations bypass save() guard, allowing edits to frozen rows if not careful
   - **Mitigation**: Code comments explicit intent ("bypass frozen guard for BOE FK reassignment only"); no schema-level enforcement

### Concurrency risks

**MEDIUM**:
1. **Exchange Rate Recalc Contention**
   - After RowDetails.post_save, _recalculate_boe_exchange_rate() calls .update() (not .save())
   - **Risk**: Multiple concurrent RowDetails saves on same BOE can race; later update overwrites earlier one
   - **Mitigation**: transaction.on_commit() batches updates; ORM .update() is atomic, so final rate is well-defined (the last one to finish)
   - **Residual**: Rate is not re-locked; concurrent threads can compute different rates if rows change mid-calc

2. **Merge BOE Atomicity**
   - Merge uses transaction.atomic(), but prefetch_related + update within the transaction
   - **Risk**: Another thread inserts new RowDetails on source BOE after prefetch but before delete
   - **Mitigation**: Atomic block prevents corruption; new row will trigger cascade or FK protection
   - **Residual**: User sees inconsistent state if checking source BOE partway through merge

3. **Hide/Restore with Concurrent Debit Reads**
   - hide_boe() changes invoice_no + writes ReconciliationLog, triggers update_license_flags()
   - Concurrent debit read via exclude_hidden() subquery may see intermediate state (invoice_no changed but log not yet committed)
   - **Mitigation**: transaction.atomic() ensures all-or-nothing; subquery checks latest log entry at read time
   - **Residual**: Under high concurrency, a debit read between invoice_no write and log write will miss the hide

### Security risks

**MEDIUM**:
1. **BOE PDF Parsing — Injection via Regex**
   - PDF text extraction regex patterns are relatively loose (e.g., company name accepts [A-Z0-9 &.,'()\\-])
   - **Risk**: Malformed PDF could inject SQL-like strings into parsed fields (though they're treated as string data, not queries)
   - **Mitigation**: All parsed data is treated as user input, validated/sanitized by serializers

2. **Hidden BOE Audit Trail Visibility**
   - ReconciliationLog records why a BOE was hidden (reason field, free text)
   - **Risk**: Sensitive info might be logged (e.g. "previous owner due to bankruptcy")
   - **Mitigation**: ReconciliationLog.reason is stored but access controlled via API; no public export

3. **Allotment Deduplication on M2M**
   - BillOfEntryModel.allotment is M2M; no uniqueness enforcement
   - **Risk**: Same AllotmentModel can appear twice (no business logic violation, but data quality issue)
   - **Mitigation**: No active constraint; manual data validation required

4. **RowDetails FK to sr_number (LicenseImportItemsModel)**
   - RowDetails.sr_number → LicenseImportItemsModel (CASCADE)
   - **Risk**: Deleting import item from a license deletes all RowDetails rows on that item, even if BOE has other rows
   - **Mitigation**: Unlikely in practice (import items are usually not deleted); can mitigate with PROTECT constraint if needed

### Performance risks

**MEDIUM**:
1. **get_debit_rows() Annotation Complexity**
   - Chains: allocated (subquery) + linked_excluded (case + subquery) + matched (case) + contributed (case)
   - **Risk**: For license with 1000+ BOE rows, annotations are slow; each row triggers subquery evaluation
   - **Mitigation**: Prefetch_related on license view; materialized views refresh on commit
   - **Residual**: Real-time debit calculation for large licenses still expensive (no query caching)

2. **exclude_hidden() Subquery Per Row**
   - annotate_and_exclude_hidden() adds `_latest_hide_restore` subquery per row
   - **Risk**: For licenses with many BOEs, this is O(rows); at 1000 rows, ~1000 extra subqueries
   - **Mitigation**: Documented as one correlated subquery, not N+1; still expensive but better than fetching all BOEs then filtering in Python
   - **Residual**: No materialized view caching

3. **Merge BOE prefetch_related() Cost**
   - Merge prefetches item_details + allotment before checking for conflicts
   - **Risk**: Large BOE (1000+ rows) merge loads entire relation into memory
   - **Mitigation**: Merge is rare operation; size acceptable for manual user action
   - **Residual**: Bulk merge (N BOEs) would be very slow; no bulk merge operation exists

4. **_scan_linked_boe_candidates() — Trade Prefetch**
   - Scans all SALE trades with .boes tags; at high volume (100+ trades), prefetch is expensive
   - **Risk**: Balance calculation for license touching many BOEs on many trades is slow
   - **Mitigation**: One shared scan (not per-license); resolves hidden BOEs in one query (not per-trade)
   - **Residual**: Still O(trades); production scale TBD

### Operational risks

**MEDIUM**:
1. **Ledger Upload Frozen Rows**
   - Ledger upload marks imported rows as is_frozen=True
   - **Risk**: If ledger upload fails partway, some rows frozen, some not; manual cleanup required
   - **Mitigation**: Ledger upload is atomic; if fails, no rows are frozen
   - **Residual**: User must re-run upload after fixing data; stale frozen rows can accumulate

2. **Hidden BOE Visibility in Ledger**
   - Custom Ledger view (build_customs_ledger with show_hidden=True) shows hidden BOEs
   - **Risk**: User confusion if they see hidden BOE in audit view but not in balance
   - **Mitigation**: Documented behavior; UI flags hidden rows as "hidden"
   - **Residual**: No strong safeguard against accidental unhiding via UI

3. **Exchange Rate Staling**
   - Exchange rate stored on BOE; not updated unless diff > 1 OR manual recalc
   - **Risk**: If INR/FC ratio drifts slowly (e.g. 84.50 → 84.75 per row), rate not updated
   - **Mitigation**: Intended behavior (avoid spurious writes); documented threshold
   - **Residual**: Manual "recalc exchange rates" command doesn't exist; requires code change to recalc all

4. **PDF Parser Regex Fragility**
   - Regex patterns are tightly coupled to ICEGATE PDF layout
   - **Risk**: New ICEGATE format breaks parsing; PDF with unusual formatting fails silently
   - **Mitigation**: PDF parse view returns structured dict; user can review before commit
   - **Residual**: No automated format-change detection; malformed PDFs require manual data entry

---

## SUMMARY TABLE

| Aspect | Status | Risk Level | Notes |
|--------|--------|-----------|-------|
| **Data Integrity** | STABLE | MEDIUM | Cascade deletes protected by FK constraints; merge validated before mutation |
| **Financial Accuracy** | STABLE | HIGH | Hidden BOE detection robust but depends on log entries; allocation netting tested |
| **Concurrency** | STABLE | MEDIUM | Atomic transactions in place; exchange rate may race under very high concurrency |
| **Performance** | STABLE | MEDIUM | Annotation chains acceptable for typical licenses; large license (1000+ rows) may stall |
| **Security** | STABLE | MEDIUM | PDF regex loose but inputs treated as strings; hidden reasons logged but access-controlled |
| **Test Coverage** | GOOD | LOW RISK | 85%+ on core logic; gaps in PDF parsing, frozen-row edge cases |
| **Legacy Debt** | STABLE | LOW | is_hidden column removed; OTH marker fully replaced; no orphaned code |

---
```

---

**MODULE_4_BASELINE.md** is ready. This baseline captures:

1. **Scope**: BOE entity definition, business workflows (ingestion, linking, reconciliation, hiding)
2. **Financial Calculations**: All three BOE-level totals, license debit with allocation netting, hidden BOE exclusion logic
3. **Data Models**: Table structure, FKs, constraints, indexes, cascade rules
4. **Business Rules**: Validations, state transitions, permissions, merge/hide/restore constraints
5. **Dependencies**: Tight (license, reconciliation), medium (allotment, trade), loose (exporters, views)
6. **Tests**: File locations, count estimate (~150+ direct, ~400+ indirect), coverage gaps (PDF parsing, frozen rows, concurrency)
7. **Legacy Code**: Removed is_hidden column, superseded hide_boe_for_license(), replaced direct checks with annotate_and_exclude_hidden()
8. **Risk Register**: 8 financial risks (highest: OTH collision), 4 data integrity, 3 concurrency, 4 security, 4 performance, 4 operational

The document is structured for forensic clarity — no solutions proposed, only findings. Ready for Module 5+ baseline discovery.