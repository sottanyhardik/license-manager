# Module 3: Allocation / Allotment — Baseline Discovery

**Status:** Read-only audit (no code changes)  
**Date:** 2026-08-10  
**Scope:** Complete lifecycle of allotment creation → allocation → conversion to BOE

---

## 1. SCOPE

### Purpose
Module 3 manages the **allotment workflow**: breaking a parent shipment (import order) into smaller allocations against specific DFIA licenses, with business logic to constrain allocations by balance, expiry, planned quantity/value caps, and state transitions.

### Key Workflow
1. **Create Allotment**: User specifies quantity/value targets, company, port, item name
2. **Allocate Items**: User selects license items and assigns quantities/CIF values to the allotment
3. **Approve**: Mark as is_approved=True
4. **Convert to BOE**: Link to BillOfEntryModel (is_boe=True, blocks further allocation)
5. **Deallocate**: Remove allocations (unless converted to BOE)

### Business Entities
- `AllotmentModel`: Parent shipment record (company, item_name, required quantity/value, exchange rate)
- `AllotmentItems`: Individual allocations (license item → quantity/CIF)
- `LicenseImportItemsModel`: Available inventory being allocated from (from License module)
- `BillOfEntryModel`: Final customs document (imports allotment M2M)
- `LicenseItemPlan`: Utilization plan lines (optional caps per description group)

### Integration Points
- **License Module** (`license/models.py`): Provides LicenseImportItemsModel, LicenseItemPlan, balance calculations
- **Bill of Entry Module** (`bill_of_entry/models.py`): M2M relationship to BillOfEntryModel
- **Plan Enforcement** (`license/services/plan_enforcement.py`): Utilization-plan cap checks
- **Balance Calculator** (`license/services/balance_calculator.py`): Live available quantity/value
- **Condition Pool** (`license/services/condition_pool.py`): Restriction pooling (% / AU / open)
- **Core Module**: Company, Port, ItemNameModel, ExchangeRateModel

---

## 2. FINANCIAL CALCULATIONS

### Allotment-level Calculations

| Field | Formula | Precision | Source |
|-------|---------|-----------|--------|
| `required_value` | required_quantity × unit_value_per_unit | 2 decimals (ROUND_HALF_UP) | `models.py:160` |
| `cif_fc` (auto-calc) | unit_value_per_unit × required_quantity | 2 decimals (ROUND_HALF_UP) | `models.py:146` |
| `cif_inr` (auto-calc) | cif_fc × exchange_rate | 2 decimals (ROUND_HALF_UP) | `models.py:155` |
| `unit_value_per_unit` (reverse) | cif_fc ÷ required_quantity | 3 decimals (ROUND_UP) | `models.py:150` |
| `balanced_quantity` | required_quantity − SUM(allotment_details.qty) | Returns 0 if negative | `models.py:172–184` |
| `alloted_quantity` | SUM(allotment_details.qty) | Sum of all allocations | `models.py:187–195` |
| `allotted_value` | SUM(allotment_details.cif_fc) | Sum of allocation values | `models.py:198–206` |

### Allocation Item Calculations

| Field | Formula | Precision |
|-------|---------|-----------|
| `qty` | User-specified | 3 decimals |
| `cif_fc` | User-specified OR qty × unit_price | 2 decimals |
| `cif_inr` | cif_fc × exchange_rate | 2 decimals |

### Value Buffer
- **Required Value With Buffer** = required_value + **20** (fixed hardcoded buffer)
- Applied in `available_licenses` endpoint (views_actions.py:340) and validation_service.py
- Tolerates rounding drifts in unit price matching; NOT for quantity

### Balance Constraints
When allocating, **four concurrent checks** must all pass:

1. **Allotment capacity**: allocated_qty ≤ balanced_quantity
2. **License availability**: allocated_qty ≤ available_quantity (from LicenseImportItemsModel)
3. **License CIF**: allocated_cif ≤ available_value_calculated (live Balance CIF, not stored)
4. **Value buffer**: allocated_value + current_allotted_value ≤ required_value_with_buffer
5. **Utilization plan cap** (if plan exists): used_qty + allocated_qty ≤ plan.planned_quantity (and CIF)
6. **License expiry**: license_expiry_date ≥ today (rejected if already expired)
7. **Allocation state**: cannot allocate to allotments already converted to BOE

### Rounding Rules
- **Unit value → CIF FC**: ROUND_HALF_UP (2 decimals)
- **Quantity ÷ CIF → Unit price**: ROUND_UP (3 decimals) — slightly favors allocator
- **Value division**: Using `decimal_division` utility with 3-decimal result
- **Exchange rate**: Stored with 6 decimals; results quantized to 2 decimals

### Precision Risks Identified
1. **Tolerance in unit price validation** (tolerance=0.01) may silently accept mismatches
2. **20-unit buffer** is hardcoded, not parameterized (discovery in memory: Phase 1 found live defects from stale Balance CIF)
3. **Plan line remaining_quantity/remaining_cif_fc** decremented in-place; no reconciliation if stale

---

## 3. DATA MODELS

### AllotmentModel (46 dependents)
```
company (FK → CompanyModel, PROTECT)
  ├─ on_delete: PROTECT (company deletion fails if allotments exist)
type (CharField, ROW_TYPE_CHOICES, default='AT')
  ├─ Values: 'AT' (allotment), 'TL' (transfer letter), others?
required_quantity (Decimal 15,2, ≥0)
required_value (cached_property, read-only)
unit_value_per_unit (Decimal 15,3, ≥0)
  ├─ Auto-calculated if missing
cif_fc (Decimal 15,2, nullable)
  ├─ Auto-calculated if unit_value_per_unit + required_quantity provided
cif_inr (Decimal 15,2, nullable)
  ├─ Auto-calculated from cif_fc × exchange_rate
exchange_rate (Decimal 15,6, nullable)
item_name (CharField 255)
contact_person (CharField 255, nullable)
contact_number (CharField 255, nullable)
invoice (CharField 255, nullable)
estimated_arrival_date (DateField, nullable)
bl_detail (CharField 255, nullable)
port (FK → PortModel, PROTECT, nullable)
related_company (FK → CompanyModel, PROTECT, nullable, related_name='related_company')
is_boe (BooleanField, default=False)
  ├─ True if allotment.bill_of_entry.exists()
is_allotted (BooleanField, default=False)
  ├─ True if allotment_details (AllotmentItems) exists
is_approved (BooleanField, default=False)
  ├─ User approval flag (inline editable)
created_on / modified_on (AuditModel fields)
created_by / modified_by (AuditModel fields)

Indexes (8):
  ├─ (company, estimated_arrival_date)
  ├─ (port, estimated_arrival_date)
  ├─ (related_company)
  ├─ (estimated_arrival_date)
  ├─ (is_boe, is_allotted)
  ├─ (type)
  ├─ (invoice)
```

### AllotmentItems (unique_together: item + allotment)
```
item (FK → LicenseImportItemsModel, CASCADE, nullable, db_index=True)
  ├─ on_delete: CASCADE (delete AllotmentItems if item deleted)
  ├─ Index added in migration 0003 to enable fast batch lookups
allotment (FK → AllotmentModel, CASCADE, nullable, db_index=True)
  ├─ on_delete: CASCADE
  ├─ related_name: allotment_details
qty (Decimal 15,3, ≥0)
cif_fc (Decimal 15,2, ≥0)
cif_inr (Decimal 15,2, ≥0)
is_boe (BooleanField, default=False)
  ├─ True after conversion to Bill of Entry
created_on / modified_on (AuditModel)

Constraints:
  ├─ unique_together = (item, allotment)
  ├─ One row per (license item, allotment) pair — updates amend qty/cif in place

Related Cached Properties:
  ├─ serial_number, license_number, license_date, exporter
  ├─ hs_code, license_expiry, registration_number, notification_number
  ├─ product_description, port_code, file_number, ledger (date)
  ├─ all walk self.item.license safely (short-circuit on None)
```

### Cascade Behavior
- **AllotmentModel → AllotmentItems**: CASCADE
  - Deleting an allotment deletes all allocations
  - Signals update parent allotment.is_allotted before deletion
- **LicenseImportItemsModel → AllotmentItems**: CASCADE
  - Deleting a license item cascades to its allocations
  - Signals recalculate item balance on delete
- **BillOfEntryModel ←M2M→ AllotmentModel**: (M2M, blank=True)
  - No cascade (M2M is link-only)
  - Related_name: allotment.bill_of_entry
  - Checked in validation (allotment.bill_of_entry.exists() blocks new allocation)

### Denormalization & Caching
- **required_value** (@cached_property): Computed per request, not stored
- **balanced_quantity** (@cached_property): Computed per request (SUM on demand)
- **alloted_quantity, allotted_value** (@cached_property): Computed per request
- **dfia_list** (@cached_property): Comma-separated license numbers
- **is_boe** (Serializer.SerializerMethodField): Computed as bill_of_entry.exists()
- Cached properties bust when AllotmentItems change (signals trigger refresh)

---

## 4. BUSINESS RULES

### Validation Rules (allocation_service.py + validation_service.py)

| Rule | Enforcement | Consequence |
|------|-------------|-------------|
| Available quantity sufficient | Checked against LicenseImportItemsModel.available_quantity | Reject if insufficient |
| Available CIF sufficient | Checked against available_value_calculated (live Balance CIF) | Reject if insufficient |
| Balanced quantity positive | balanced_quantity > 0 | Can allocate |
| Allocation ≤ balanced quantity | allocated_qty ≤ required_qty − SUM(previous allocations) | Reject if exceeds |
| Value ≤ required + buffer | allocated_value ≤ required_value + 20 | Reject if exceeds |
| License not expired | license_expiry_date ≥ today | Reject if expired |
| Plan cap (if exists) | SUM(used + requested) ≤ plan.planned_qty/cif | Reject if plan exceeded |
| Unit price tolerance | \|calculated_unit_price − allotment.unit_value_per_unit\| ≤ 0.01 | Warning (currently unused) |
| Allotment not BOE-converted | bill_of_entry.exists() = False | Reject if is_boe=True |
| Item not None | AllotmentItems.item_id must be set | Reject if None |

### State Transitions
```
DRAFT (created)
  ├─ [allocate-items] → ALLOCATED
  └─ [delete] → (removed)

ALLOCATED (is_allotted=True)
  ├─ [allocate-items] → (amend: qty += requested)
  ├─ [delete-item] → (deallocate unless bill_of_entry exists)
  ├─ [approve] → is_approved=True
  └─ [convert-to-boe] → is_boe=True, bill_of_entry.add(boe)

APPROVED (is_approved=True)
  └─ [convert-to-boe] → is_boe=True, is_allotted=True

CONVERTED TO BOE (is_boe=True)
  ├─ Cannot reallocate (blocked at validate_can_allocate)
  ├─ Cannot deallocate (blocked in delete_allotment_item)
  └─ View-only (is_approved implicitly True)
```

### Permission & Access Control
- **AllotmentPermission** (apps/accounts/permissions.py)
  - Required for all CRUD + allocate/deallocate operations
  - Checked in AllotmentViewSet, AllotmentActionViewSet
- **TransferLetterPermission**
  - Required for generate_transfer_letter action only

### Workflow Constraints
1. **Once converted to BOE**: No further modification allowed (blocks allocate/deallocate)
2. **Expiry check at allocation time**: Rejected on stale flag OR live expiry_date < today
3. **Plan-line balance independent**: When allocate with plan_line_id, decrement that line only
4. **Utilization plan is advisory**: Plan cap violations return `plan_exceeded=True` (frontend opens planner, no auto-reject)
5. **Allocation amendment**: Allocating same item twice to same allotment adds to existing (unique_together constraint)

---

## 5. DEPENDENCIES

### Inbound (what depends on Allotment)
```
bill_of_entry/models.py
  ├─ BillOfEntryModel.allotment (M2M)
  ├─ Related: BillOfEntryModel.items (many RowDetails) + RowDetails.trade_line
  └─ Allocation → BOE → RowDetails debit chain

license/models/core.py
  ├─ LicenseImportItemsModel.allotment_details (reverse FK)
  ├─ LicenseImportItemsModel.available_quantity (depends on SUM of AllotmentItems)
  └─ Balance calculator (balance_calculator.py) subtracts allotments from available

reconciliation/models.py
  ├─ Mentions allotment vs BOE tracking (which RowDetails row is sourced from)
  ├─ BOEAllotmentAllocation table (tracking allocation → BOE → debit chain)
  └─ Not a direct import, but reconciliation logic aware of allocations
```

### Outbound (Allotment depends on)
```
license/models.py
  ├─ LicenseImportItemsModel (FK in AllotmentItems)
  ├─ LicenseDetailsModel (via import_item.license)
  ├─ LicenseItemPlan (utilization plan, optional cap)
  └─ Ledger, Balance, and Debit services (for live available value)

license/services/
  ├─ balance_calculator.py → ItemBalanceCalculator
  │  ├─ calculate_available_quantity (import_item)
  │  ├─ calculate_item_balance (import_item) → available_value_calculated
  │  └─ calculate_allotment (license) → total allotment for a license
  ├─ plan_enforcement.py → plan_status_for(import_item)
  │  ├─ Returns {original_qty, used_qty, remaining_qty, original_cif_fc, used_cif_fc, remaining_cif_fc}
  │  └─ Used to enforce plan cap during allocation
  ├─ condition_pool.py → available_value_bulk_map(items)
  │  └─ Live Balance CIF with restriction pooling (% / AU / open)
  └─ item_usage.py → billed_no_boe_bulk_map (RowDetails count excluding BOE)

bill_of_entry/models.py
  ├─ M2M relationship (allotment.bill_of_entry)
  └─ is_boe flag updated by update_is_boe management command

core/models.py
  ├─ CompanyModel, PortModel, ExchangeRateModel, ItemNameModel
  ├─ AuditModel (created_on, modified_on, created_by, modified_by)
  └─ DEC_0, DEC_000 constants

django.utils.timezone
  ├─ timezone.now().date() for expiry check
  └─ Used at allocation time (not stored)
```

### API Contracts

#### REST Endpoints
```
POST   /api/allotments/                             — Create allotment
GET    /api/allotments/                             — List (with filters)
GET    /api/allotments/{id}/                        — Retrieve
PATCH  /api/allotments/{id}/                        — Partial update
DELETE /api/allotments/{id}/                        — Delete

GET    /api/allotment-actions/{id}/available-licenses/  — List items for allocation
                                                         (with plan-mode variant)
POST   /api/allotment-actions/{id}/allocate-items/      — Allocate items
DELETE /api/allotment-actions/{id}/delete-item/{item_id}/ — Deallocate
GET    /api/allotments/download/                    — Export (grouped PDF/XLSX)
GET    /api/allotment-actions/{id}/generate-pdf/    — Generate allotment PDF
GET    /api/allotment-actions/{id}/generate-transfer-letter/ — Generate transfer letter
```

#### available-licenses Query Params
```
search, license_number, description, exporter, exclude_exporter
available_quantity_gte, available_quantity_lte
available_value_gte, available_value_lte
notification_number, norm_class, hs_code, is_restricted
purchase_status, license_status
item_names, expiry_date_from, expiry_date_to
debit_based_on ('actual' or 'plan')
planned_item_names (plan mode only)
page, page_size
```

#### allocate-items Request Body
```json
{
  "allocations": [
    {
      "item_id": 123,
      "qty": "100.00",
      "cif_fc": "1000.00",
      "cif_inr": "83000.00",
      "plan_line_id": 456  // optional: LicenseItemPlan row to decrement
    },
    ...
  ]
}
```

#### Response
```json
{
  "success": N,
  "created_items": [...],
  "errors": [...],
  "allotment": { ... updated allotment data ... }
}
```

---

## 6. TESTS EXISTING

### Test Files (7 files, 48 test methods, ~1580 lines)

| File | Tests | Focus |
|------|-------|-------|
| test_allocate_items_cif_validation.py | 5 | Live available_value_calculated vs stale stored value; legacy CIF check regression |
| test_allocate_items_e1_group_plan_cap.py | 4 | E1 mixed-HSN group plan independence (each group has own cap) |
| test_allocate_items_expiry_check.py | 13 | License expiry validation; date boundary cases; multiple licenses |
| test_allocate_items_group_plan_cap.py | 5 | Group plan cap (multiple serial numbers) consolidated into one cap |
| test_allocate_items_plan_line_balance.py | 6 | Plan line remaining_quantity decrement (per-line, not shared) |
| test_available_licenses_filters.py | 7 | Quantity/value filter logic; live balance filtering |
| test_available_licenses_plan_mode.py | 8 | Plan-mode grid; plan status; item name filtering |

### Coverage Estimate
- **Models (save, properties, signals)**: ~70% (auto-calc, cached properties, signals tested)
- **Services (allocation, validation, filtering)**: ~80% (core allocation paths, edge cases covered)
- **Views (allocate, delete, available-licenses)**: ~60% (happy path + major error cases; filtering partially covered)
- **Signals (balance update on save/delete)**: ~40% (integration tested indirectly, no direct tests)
- **Exports (PDF, XLSX)**: ~0% (untested, view-level only)
- **Management commands**: ~0% (untested)

### Known Test Gaps
1. **Concurrent allocation**: No test for race condition (allocate same item twice simultaneously)
2. **Exchange rate calculation**: No test for edge cases (very high/low rates, precision drift)
3. **Deallocate (delete-item endpoint)**: Minimal coverage (one basic test)
4. **Signal cascades**: Indirect (tested through allocation, not isolation)
5. **Export endpoints**: No tests for PDF/XLSX generation
6. **Approval workflow**: No tests for is_approved state transitions
7. **BOE conversion**: Linked via M2M, no test for is_boe sync or unlink behavior
8. **Management commands**: update_is_boe, update_exchange_rate untested

---

## 7. LEGACY CODE

### Known Stale/Deprecated Patterns

| Location | Issue | Status | Impact |
|----------|-------|--------|--------|
| views_actions.py:710–721 (comments) | Legacy CIF check used is_restricted + stored available_value | **FIXED** in recent refactor | Used to reject valid allocations (Defect #33740) |
| filter_service.py:178–193 | apply_value_filters() tries .filter(balance_cif_fc__gte=...) on Python property | **BUG, UNREACHABLE** | No callers; would FieldError if called; documented but not fixed |
| license/signals.py | mentions "is_restricted is no longer set from ItemNameModel.restriction_percentage" | **DEAD** | Old exception-license model, replaced by condition_type |
| allocation_service.py:64 | `required_value_with_buffer or (required_value + Decimal('20'))` | **FRAGILE** | Fallback to hardcoded buffer if None; should be explicit |

### Unused Exports
- None identified; all services actively used

### Dead Services
- None identified; all services linked from views or signals

---

## 8. RISK REGISTER

### Financial Accuracy Risks

| Risk | Likelihood | Severity | Mitigation |
|------|------------|----------|-----------|
| **Stale available_value vs live Balance CIF** | Medium (recalc delayed) | High (silent rejection) | Live compute in allocate_items; stored field only for display |
| **Precision loss (unit price tolerance 0.01)** | Low | Medium (cosmetic mismatches) | Tolerance threshold documented but currently unused |
| **20-unit hardcoded buffer** | Low | Low (conservative) | Parameterize if business rules change |
| **CIF rounding (ROUND_HALF_UP vs ROUND_UP)** | Low | Low (by design) | Rounding rules documented; unit_value_per_unit uses ROUND_UP to favor allocator |
| **Exchange rate changes mid-allotment** | Medium (manual update only) | Medium (CIF INR recalc) | Manual update via management command; not auto-synced |
| **Duplicate allocation (same item to same allotment twice)** | Low (unique_together) | Low | unique_together = (item, allotment) enforces single row; updates amend in place |

### Data Integrity Risks

| Risk | Likelihood | Severity | Mitigation |
|------|------------|----------|-----------|
| **Cascade delete (allotment → items)** | Very Low | High (data loss) | CASCADE is correct (items only exist for this allotment) |
| **Plan line remaining_quantity goes stale** | Medium (no reconciliation) | Medium (wrong cap) | Decremented in allocate_items under select_for_update; baseline snapshot catches drift |
| **is_boe flag out of sync** | Low (update_is_boe command) | Medium (state confusion) | Management command exists; should be run after BOE creation |
| **is_allotted flag incorrect** | Low (signal on save/delete) | Low (display only) | Signal updates on AllotmentItems change; works correctly |
| **Item or License deleted** | Very Low | Low (cascade) | CASCADE on both; AllotmentItems automatically removed |
| **Bill of Entry unlinked** | Low (manual M2M) | Medium (is_boe stays true) | No automatic sync; requires manual fix or command |

### Concurrency Risks

| Risk | Likelihood | Severity | Mitigation |
|------|------------|----------|-----------|
| **Two allocations race on plan cap check** | Medium | Medium (exceeds cap) | `select_for_update()` on LicenseImportItemsModel + @transaction.atomic |
| **Allocation and delete race** | Low | Low (one wins) | `select_for_update()` on item in delete endpoint |
| **Stale plan_line_id reference** | Low | Low (silently skipped) | Stale reference caught and logged; allocation succeeds, plan-line decrement skipped |
| **Multiple allocators same allotment** | Low | Low (last write wins) | No row-level lock; concurrent updates both succeed (qty += is additive) |

### Security Risks

| Risk | Likelihood | Severity | Mitigation |
|------|------------|----------|-----------|
| **Unauthorized allocation** | Very Low | High | AllotmentPermission required on all endpoints |
| **Cross-company allocation** | Very Low | Low | No explicit check (trusts user role); allotment.company is free-text |
| **BOE conversion without permission** | Low | Medium | Checked elsewhere (bill_of_entry/views); allotment module doesn't perform conversion |
| **Expired license allocation** | Low | High | **FIXED** in recent refactor: checks license_expiry_date < today.now() at allocate time |

### Performance Risks

| Risk | Likelihood | Severity | Mitigation |
|------|------------|----------|-----------|
| **N+1 queries on available-licenses** | Medium | Medium (~300ms for 100-item page) | Batched balance computations (available_value_bulk_map, plan_map, billed_no_boe_map) |
| **Live Balance CIF recompute per item** | Medium | Medium (slow filter) | Only computed for items matching other filters; materialized once per request |
| **Large allotment_details prefetch** | Low | Low | select_related + prefetch_related optimized in views |
| **Cascade delete (large item set)** | Very Low | Low | Rare edge case; Django handles in batches |
| **Unindexed lookups** | Very Low | Low | All FK lookups indexed; unique_together indexed |

### Operational Risks

| Risk | Likelihood | Severity | Mitigation |
|------|------------|----------|-----------|
| **Exchange rate stale after system update** | Medium (manual step) | Low | Management command `update_exchange_rate --dry-run` available |
| **is_boe flag stale after BOE delete** | Low | Low | Management command `update_is_boe --dry-run` available |
| **Plan enforcement silently skipped** | Low | Low | `plan_exceeded` error returned; frontend UX depends on this |
| **Allotment approval workflow not enforced** | N/A | Low | is_approved is inline-editable; no workflow state machine |

---

## 9. KEY INTEGRATION POINTS

### License Module Dependency
- **On read**: `available_licenses` endpoint queries LicenseImportItemsModel with 14 filters + live balance computation
- **On write**: `allocate_items` triggers `update_balance_values(item)` via signal → recalculates available_quantity
- **Plan enforcement**: `plan_status_for(item)` returns used/remaining at allocation time
- **Condition pool**: `available_value_calculated` applies restriction pooling (% / AU / open)

### Bill of Entry Integration
- **M2M link**: AllotmentModel ←→ BillOfEntryModel.allotment
- **State sync**: is_boe field synced via management command (not automatic)
- **Conversion blocks**: Allocate/deallocate rejected if bill_of_entry.exists()
- **No reverse cascade**: Deleting BOE does NOT auto-unlink allotment.is_boe

### Plan Enforcement
- **Plan cap override**: Allocation returns `plan_exceeded=True` (not rejected; frontend decides)
- **Plan line balance**: When `plan_line_id` provided, that line's remaining_quantity decremented independently
- **Baseline snapshot**: Detects allocation between plan creation and use (baseline_used_qty/cif_fc)
- **No auto-plan**: Allocation does NOT create plan lines; uses existing or falls back to availability

### Balance & Ledger Chain
```
AllotmentItems.qty/cif_fc
  ↓ [signal: post_save, post_delete]
  → update_license_balance(item)
    → update_balance_values(item) [optimize batch call]
      → calculate_available_quantity (import_item)
      → calculate_item_balance (import_item)
      → store in LicenseImportItemsModel.available_quantity / available_value
```

---

## 10. REBUILD SPEC

### Minimal Rebuild
To reproduce Module 3 from scratch:

**Essential tables** (in dependency order):
1. Core: Company, Port, ItemNameModel, SionNormClass, ExchangeRate, HeadSIONNorms
2. License: LicenseDetails, LicenseImportItems, LicenseItemPlan, Ledger (balance)
3. Allotment: AllotmentModel, AllotmentItems
4. Bill of Entry: BillOfEntryModel (M2M to AllotmentModel)

**Essential services**:
1. `allocation_service.py` — allocate, deallocate, calculate_max_allocation
2. `validation_service.py` — validate_allocation_within_limits, check_allotment_fully_allocated
3. `filter_service.py` — available items filtering (query params)
4. Balance calculator (from license module) — live available_quantity, available_value_calculated
5. Plan enforcement (from license module) — plan_status_for, utilization plan cap

**Essential views**:
1. AllotmentViewSet — CRUD (via MasterViewSet)
2. AllotmentActionViewSet.available_licenses — GET (with filters)
3. AllotmentActionViewSet.allocate_items — POST
4. AllotmentActionViewSet.delete_allotment_item — DELETE
5. Exports — download_grouped_export (PDF/XLSX)

**Signals**:
1. AllotmentItems.post_save → update_license_balance
2. AllotmentItems.post_delete → update_license_balance
3. AllotmentItems post_save → update_is_allotted on parent AllotmentModel

**Management commands**:
1. `update_is_boe` — sync is_boe flag after BOE creation/deletion
2. `update_exchange_rate` — batch recalc cif_inr across allotments

**Tests** (prioritized):
1. Allocation validation (expiry, balance, plan cap)
2. Plan line balance decrement
3. Filter and search (available-licenses)
4. Concurrent allocation (race on plan cap)
5. Deallocate (delete-item, BOE blocking)

---

## 11. SUMMARY

**Module 3** is a **moderately complex**, **well-tested** allocation workflow with:
- ✅ Clear data model (2 tables, normalized)
- ✅ Comprehensive validation (7-point check + plan cap)
- ✅ Strong signal-based balance sync
- ✅ Optimized querying (batched balance compute, indexes)
- ⚠️ Hardcoded buffer (20 units) and stale plan-line risk
- ❌ No management-enforced workflow state (is_approved not blocking)
- ❌ Untested exports and signals (indirect coverage only)

**Financial risk: LOW** (live balance check + expiry validation)  
**Data integrity risk: LOW** (cascades correct, unique constraint enforced)  
**Concurrency risk: MEDIUM** (select_for_update covers plan, but amendment race unguarded)  
**Performance risk: LOW** (batched balance, indexed FKs)
