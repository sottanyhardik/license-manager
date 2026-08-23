# MODULE 3: MASTER FUNCTION INVENTORY
## Allocation/Allotment System — Complete Function Audit

**Date:** 2026-08-10  
**Scope:** All functions participating in allocations, allotments, balance calculations, and plan enforcement  
**Format:** Master inventory table (one function per row)  

---

## INDEX OF FUNCTIONS BY CATEGORY

1. **View/API Entry Points** (3 functions)
2. **Service Layer: Allocation** (7 functions)
3. **Service Layer: Validation** (6 functions)
4. **Service Layer: Filter & Plan Enforcement** (4 functions)
5. **Model Properties & Helpers** (11 functions)
6. **Signal Handlers** (3 functions)
7. **Balance Calculation** (3 functions)
8. **Serializers** (6 functions)
9. **Helpers & Utilities** (5 functions)

---

## MASTER FUNCTION INVENTORY

### 1. VIEW/API ENTRY POINTS

| Function | File | Line | Class/Type | HTTP Method | Inputs | Outputs | Database Access | Business Rule | Callers | Risk Level | Tests |
|----------|------|------|------------|-------------|--------|---------|-----------------|---------------|---------|-----------|-------|
| `available_licenses` | `views_actions.py` | 42 | ViewSet method | GET | `request`, `pk` (allotment_id), query params (search, filters, debit_based_on) | JSON paginated list of `LicenseImportItemSerializer` with available qty/value | SELECT (prefetch) on LicenseImportItemsModel, LicenseModel; no UPDATE | Base: available_quantity > 0; Optional: plan-mode vs actual-mode branching (line 83); Filters on qty/value/expiry/notification/norm_class/hs_code; Restricts by company (via AllotmentPermission) | Calls: `_available_licenses_plan_mode()` (line 84), `available_value_bulk_map()` (line 313), `plan_map_for_import_items()` (line 321), `plan_status_for_items()` (line 355) | **MEDIUM** — N+1 risk mitigated by bulk maps; double-filtering on quantity/value; no transaction lock | `test_available_licenses_filters.py` (quantity/value boundary tests); tested indirectly in allocate tests |
| `allocate_items` | `views_actions.py` | 625 | ViewSet action | POST | JSON request body: `{allocations: [{item_id, qty, cif_fc, cif_inr, plan_line_id?}]}` | JSON response: `{success, created_items[], errors[], allotment}` | SELECT_FOR_UPDATE on LicenseImportItemsModel, LicenseItemPlan; INSERT/UPDATE AllotmentItems; UPDATE AllotmentModel.is_allotted | **5-gate validation stack:** (1) expiry check (line 680), (2) available_quantity sufficiency (line 694), (3) available_value_calculated sufficiency (line 722), (4) balanced_quantity sufficiency (line 735), (5) plan_status_for cap (line 761) | Calls: `plan_status_for()` (line 761), `AllotmentItems.filter().first()` (line 788), `AllotmentItems.create()` (line 802), `LicenseItemPlan.select_for_update().get()` (line 836), signals chain (post_save) | **CRITICAL** — Race condition A1 (plan cap check before lock), upsert race A3 (no lock on AllotmentItems check), partial state B2 on plan-line failure; see MODULE_3_FORENSIC_AUDIT.md risks A1, A3, B2 | `test_allocate_items_cif_validation.py`, `test_allocate_items_expiry_check.py`, `test_allocate_items_group_plan_cap.py`, `test_allocate_items_e1_group_plan_cap.py`, `test_allocate_items_plan_line_balance.py` |
| `delete_allotment_item` | `views_actions.py` | 878 | ViewSet action | DELETE | URL params: `pk` (allotment_id), `item_id` (AllotmentItems.id) | JSON response: `{message, deleted_qty}` or error | SELECT_FOR_UPDATE on LicenseImportItemsModel; DELETE AllotmentItems; pre_delete/post_delete signals | Credit side of allotment debit: removes qty/cif allocation; triggers signal chain to recalculate license balance | Calls: `get_object_or_404()` (line 896), `LicenseImportItemsModel.select_for_update()` (line 909), `AllotmentItems.delete()` (line 912), signals chain | **MEDIUM** — delete signal B2 risk (deletes ALL details when checking for ANY); see MODULE_3_FORENSIC_AUDIT.md risk B2 | Indirectly tested via balance recalculation tests |

---

### 2. SERVICE LAYER: ALLOCATION

| Function | File | Line | Class | Inputs | Outputs | Database Access | Business Rule | Callers | Risk Level | Tests |
|----------|------|------|-------|--------|---------|-----------------|---------------|---------|-----------|-------|
| `calculate_max_allocation` | `allocation_service.py` | 29 | AllocationService | `allotment`, `import_item`, `unit_price` (optional) | `{max_quantity, max_value}` dict | SELECT on AllotmentModel.allotment_details (SUM), LicenseImportItemsModel; calls `ItemBalanceCalculator.calculate_available_quantity()`, `ItemBalanceCalculator.calculate_item_balance()` | Computes minimum of 4 constraints: (1) balanced_quantity, (2) available_quantity, (3) available_value_calculated / unit_price, (4) (required_value_with_buffer - allotted_value) / unit_price; returns max that passes all | Called by: `validate_allocation_amount()` (line 142); NOT called by `allocate_items()` (views_actions does its own inline validation instead) | **LOW** — purely computational, no side effects | Unused in primary allocate flow (inline validation used instead) |
| `calculate_allocation_value` | `allocation_service.py` | 94 | AllocationService | `quantity` (Decimal), `unit_price` (Decimal) | Decimal value = qty × price | None (pure calculation) | qty × unit_price with Decimal precision; no validation that inputs are positive or non-zero | Called by: `validate_allocation_amount()` (line 142); other services that need qty→value conversion | **LOW** — arithmetic only, no constraint enforcement | None observed |
| `validate_allocation_amount` | `allocation_service.py` | 113 | AllocationService | `allotment`, `import_item`, `quantity`, `value` | `(bool, str)` tuple — (is_valid, error_message) | Calls `calculate_max_allocation()` which selects balances | Checks: qty > 0, value > 0, qty ≤ max_quantity, value ≤ max_value; returns False + reason if any fail | Called by: `allocate_item()` (line 154); NOT called by `allocate_items()` view (inline checks used instead) | **LOW** — validation-only, no mutations | Unused in primary allocate flow |
| `allocate_item` | `allocation_service.py` | 154 | AllocationService | `allotment`, `import_item`, `qty`, `cif_fc`, `cif_inr`, `validate=True` | `AllotmentItems` instance (created/updated) | INSERT/UPDATE AllotmentItems; checks existing via `.filter().first()`, calls `LicenseValidationService.validate_allocation()` | Upserts AllotmentItems for (allotment, item): if exists, += quantities; if not, creates new row with is_boe=False | Called by: Legacy code path (views_actions.py uses inline logic instead); not in active use for POST /allocate-items | **MEDIUM** — upsert logic not atomic (race on `.first()` check); see MODULE_3_FORENSIC_AUDIT.md risk A3 | None observed in primary flow |
| `deallocate_item` | `allocation_service.py` | 207 | AllocationService | `allotment_item` (AllotmentItems instance) | None | DELETE AllotmentItems row IF not converted to BOE | Deletes AllotmentItems unless is_boe=True (prevents deleting BOE-converted items) | Called by: Legacy code path; views_actions.py uses `.delete()` directly instead | **LOW** — soft check only, no DB lock | None observed |
| `update_allocation` | `allocation_service.py` | 228 | AllocationService | `allotment_item`, `qty`, `cif_fc`, `cif_inr` | `AllotmentItems` instance (mutated) | UPDATE AllotmentItems; no concurrent lock | Updates qty/cif_fc/cif_inr by replacing (not += like allocate_item); **NO expiry check** (see MODULE_3_FORENSIC_AUDIT.md risk E2) | Called by: Legacy code path; not used in primary allocate flow | **MEDIUM** — lacks expiry validation; no transaction lock | None observed |
| `get_allocation_summary` | `allocation_service.py` | 278 | AllocationService | `allotment` | `{total_items, total_quantity, total_value, ...}` dict | SELECT on AllotmentItems (aggregates), LicenseImportItemsModel | Computes SUM(qty), SUM(cif_fc), COUNT(*) across all AllotmentItems for allotment; returns summary stats | Called by: Reporting/dashboard; not in primary allocate flow | **LOW** — aggregation-only, read-only | None observed |

---

### 3. SERVICE LAYER: VALIDATION

| Function | File | Line | Class | Inputs | Outputs | Database Access | Business Rule | Callers | Risk Level | Tests |
|----------|------|------|-------|--------|---------|-----------------|---------------|---------|-----------|-------|
| `validate_allotment_complete` | `validation_service.py` | 20 | AllotmentValidationService | `allotment` | `(bool, [missing_fields])` tuple | None (in-memory) | Checks required fields (company, item_name, required_quantity, unit_value_per_unit) are non-null/non-zero | Called by: Form validation, pre-create hooks | **LOW** — schema-level only | None observed |
| `validate_can_allocate` | `validation_service.py` | 50 | AllotmentValidationService | `allotment` | `(bool, str)` tuple | SELECT on AllotmentModel | Checks: (1) not is_boe (prevent allocation to bill-of-entry), (2) balanced_quantity >= 0 (not over-allocated) | Called by: Pre-allocation gate checks | **LOW** — simple guard checks | None observed |
| `validate_allocation_within_limits` | `validation_service.py` | 76 | AllotmentValidationService | `allotment`, `qty`, `cif_fc` | `(bool, str)` tuple | SELECT on AllotmentItems (SUM qty, cif_fc) | Checks: (qty + SUM(existing)) ≤ required_quantity; (cif_fc + SUM(existing_cif_fc)) ≤ required_value_with_buffer | Called by: Legacy validation (inline checks in allocate_items view instead) | **MEDIUM** — **NO transaction lock** during aggregate check (see MODULE_3_FORENSIC_AUDIT.md risk A1 reasoning) | None observed |
| `validate_unit_price_matches` | `validation_service.py` | 128 | AllotmentValidationService | `allotment`, `item`, `unit_price` | `(bool, str)` tuple | None | Checks: |calculated_unit_price - expected_unit_price| ≤ 0.01 (tolerance for rounding) | Called by: Legacy validation; not in primary allocate flow | **LOW** — not enforced in allocate_items | None observed |
| `check_allotment_fully_allocated` | `validation_service.py` | 163 | AllotmentValidationService | `allotment` | bool | SELECT on AllotmentItems (SUM cif_fc) | Checks: allotted_value >= (required_value × 0.99) — returns True if ≥99% of required value allocated | Called by: Reporting, completion checks | **LOW** — read-only determination | None observed |
| `get_remaining_allocation_capacity` | `validation_service.py` | 192 | AllotmentValidationService | `allotment` | `{remaining_quantity, remaining_value, available_capacity_qty, available_capacity_value}` dict | SELECT on AllotmentItems, AllotmentModel | Computes remaining headroom: qty = required - allocated, value = (required + buffer) - allocated | Called by: UI display, capacity indicators | **LOW** — computed summary | None observed |

---

### 4. SERVICE LAYER: FILTER & PLAN ENFORCEMENT

| Function | File | Line | Class | Inputs | Outputs | Database Access | Business Rule | Callers | Risk Level | Tests |
|----------|------|------|-------|--------|---------|-----------------|---------------|---------|-----------|-------|
| `plan_status_for` | `plan_enforcement.py` | 243 | Module function | `item` (LicenseImportItemsModel) | `{original_quantity, original_cif_fc, used_quantity, used_cif_fc, remaining_quantity, remaining_cif_fc}` dict OR None | Calls `group_ids_of()` + `plan_status_for_ids()`: SELECT on LicenseImportItemsModel siblings, LicenseItemPlan rows, AllotmentItems SUM | Returns plan cap constraint for item's group: Original (immutable planned qty), Used (live-summed allotments minus baseline snapshot), Remaining = Original - Used; None if no plan exists (unconstrained) | Called by: `allocate_items()` (line 761 in views_actions.py) to enforce cap; Allotment detail screens; plan status displays | **CRITICAL** — Live aggregation window is **NOT locked during check**, race condition A1 (see MODULE_3_FORENSIC_AUDIT.md); used twice in allocate flow (once at line 761, again inline) | `test_allocate_items_group_plan_cap.py`, `test_allocate_items_e1_group_plan_cap.py` |
| `plan_status_for_items` | `plan_enforcement.py` | 278 | Module function | `items` (list of LicenseImportItemsModel) | `{item_id: dict\|None}` dict mapping | ONE query for siblings across all licenses, ONE query for LicenseItemPlan, ONE query for AllotmentItems aggregates (batched) | Byte-identical to calling `plan_status_for(item)` once per item, but in fixed 3-4 queries instead of O(items) queries; returns `{item.id: status_dict or None}` | Called by: `available_licenses()` (line 355) to inject plan data into paginated response without N+1 queries | **MEDIUM** — Same race window as plan_status_for (aggregate not locked), but acceptable for read-only display | Tested indirectly in available_licenses flow |
| `available_value_bulk_map` | `condition_pool.py` | 292 | Module function | `items` (list of LicenseImportItemsModel) | `{item_id: Decimal}` dict mapping each item to its live available CIF value | Calls `LicenseBalanceCalculator.calculate_financial_balance_for_licenses()` (aggregates per license), `compute_condition_pools_bulk()` (condition-based pools), `ItemBalanceCalculator.calculate_item_attributed_balances_for_items()` (item-level CIF) | For each item: branches on condition_type (%, AU, open) to compute available_value exactly like `available_value_calculated` property does per-item, but batched | Called by: `available_licenses()` (line 313) to avoid re-computing property 100+ times per page; must match `available_value_calculated` branches exactly | **MEDIUM** — Complex condition-pool logic; keep in sync with `available_value_calculated` and `_resolve_available_value()` | Indirectly tested via available_licenses; no standalone tests observed |
| `compute_condition_pools_bulk` | `condition_pool.py` | 131 | Module function | `license_ids` (list) | `{license_id: {condition_type: Decimal}}` nested dict | ~5 fixed queries regardless of batch size: (1) distinct condition_type, (2-5) aggregate usage per condition per license (BOE, Allotment, Trade, Credit) | Pools imports with same %-condition (e.g., "40%") and tracks shared credit pool balance — deducts usage (BOE/Allotment/Trade) from available | Called by: `available_value_bulk_map()` to compute %-restricted pool balances; Ledger PDF generation | **MEDIUM** — Core calculation for restricted items; must correctly handle BOE/Allotment/Trade attribution | Tested indirectly via allocation tests with restricted items |

---

### 5. MODEL PROPERTIES & HELPERS

| Function | File | Line | Type | Inputs | Outputs | Database Access | Business Rule | Callers | Risk Level | Tests |
|----------|------|------|------|--------|---------|-----------------|---------------|---------|-----------|-------|
| `balanced_quantity` (property) | `models.py` | 172 | cached_property on AllotmentModel | None (self) | Decimal | SELECT on AllotmentItems (SUM qty) | **remaining qty = required_quantity - SUM(allotment_details.qty)**; clamped to 0 (never negative); **⚠️ CACHED** (see MODULE_3_FORENSIC_AUDIT.md risk A2) | Used by: `allocate_items()` (line 735 recomputes fresh instead of using cached); summary displays; UI balance indicators | **HIGH** — Cached property can return stale value if accessed across transaction boundaries; views_actions.py correctly avoids it (line 733-735 computes inline from required_quantity) | Implicitly tested via allocate; no direct staleness tests |
| `alloted_quantity` (property) | `models.py` | 187 | cached_property on AllotmentModel | None (self) | Decimal | SELECT on AllotmentItems (SUM qty) | **total allocated qty = SUM(allotment_details.qty)**; used for balance display and UI totals | Used by: Serializers, UI displays, balance calculations | **MEDIUM** — Cached, but less critical than balanced_quantity (used for display, not gating) | Implicitly tested via allocate tests |
| `allotted_value` (property) | `models.py` | 198 | cached_property on AllotmentModel | None (self) | Decimal | SELECT on AllotmentItems (SUM cif_fc) | **total allocated value = SUM(allotment_details.cif_fc)**; financial reporting | Used by: `calculate_max_allocation()` (line 68), serializers, dashboards | **MEDIUM** — Cached; used in constraint calc | Indirectly tested |
| `required_value` (property) | `models.py` | 160 | cached_property on AllotmentModel | None (self) | Decimal | None (in-memory) | **required_value = required_quantity × unit_value_per_unit**; quantized to 2 decimal places | Used by: UI display, plan comparison, balance checks | **LOW** — Pure arithmetic, no DB access | Tested implicitly |
| `available_value_calculated` (property) | `core.py` (license) | 1021 | @property on LicenseImportItemsModel | None (self) | Decimal | Calls condition_pool and balance calculator; complex branching on condition_type | **Live CIF balance for item**, accounting for: (1) special marker 0.01 → returns 0.01; (2) if item.condition_type is "X%" → pools.get(condition_type) else license_balance; (3) if condition_type not in pools → fallback to full license_balance; never uses stale `available_value` column | Called by: `allocate_items()` (line 722), serializers, filter_available_items | **CRITICAL** — Central to allocation validation; must be computed live (not cached); branches must match `available_value_bulk_map()` + `_resolve_available_value()` exactly | `test_allocate_items_cif_validation.py` (tests live vs stale balance) |
| `_update_balance_sync` (helper) | `models.py` | 329 | Module-level function | `item_id` | None | Calls `update_balance_values(item)` | Wrapper for transaction.on_commit() callback; ensures balance recomputation happens after AllotmentItems transaction commits | Called by: post_save signal (line 350) via transaction.on_commit() | **MEDIUM** — Signal chain entry; ensures sync ordering | Indirectly tested via allocation balance tests |
| `_to_decimal` (helper) | `models.py` | 28 | Module-level function | `value`, `default` (Decimal) | Decimal | None | Safely coerces value to Decimal with fallback default; handles None, string, Decimal, invalid input | Used by: Model calculations, validation throughout module | **LOW** — Pure conversion utility | None observed |
| `_license` (property) | `models.py` (AllotmentItems) | 258 | @property | None (self) | LicenseModel OR None | SELECT on LicenseImportItemsModel.license (1 FK dereference per call) | **Returns item.license** — convenience accessor for AllotmentItems.item.license | Used by: Serializers, display templates | **LOW** — Simple accessor; item can be null (see risk) | None observed |
| `serial_number` (property) | `models.py` (AllotmentItems) | 263 | @property | None (self) | str | SELECT on LicenseImportItemsModel (if item not prefetched) | **Returns item.serial_number** — convenience accessor | Used by: Export templates, serializers | **LOW** — Simple accessor | None observed |
| `product_description` (property) | `models.py` (AllotmentItems) | 271 | @property | None (self) | str | SELECT on LicenseImportItemsModel (if item not prefetched) | **Returns item.product_description** — convenience accessor | Used by: Export, serializers | **LOW** — Simple accessor | None observed |
| `license_expiry` (property) | `models.py` (AllotmentItems) | 294 | @property | None (self) | date OR None | SELECT on LicenseImportItemsModel + LicenseModel (FK chain) | **Returns item.license.license_expiry_date** — convenience accessor | Used by: Display, filtering | **LOW** — Simple accessor | None observed |

---

### 6. SIGNAL HANDLERS

| Function | File | Line | Trigger | Inputs | Outputs | Database Access | Business Rule | Callers | Risk Level | Tests |
|----------|------|------|---------|--------|---------|-----------------|---------------|---------|-----------|-------|
| `update_license_balance` | `signals.py` | 10 | Manual function call (from signals) | `license_item` (LicenseImportItemsModel) | None | Calls `update_balance_values()` which updates LicenseImportItemsModel columns | Wrapper that delegates to centralized balance recomputation; ensures consistent calculation | Called by: `update_is_allotted_on_save()` (line 38), `update_is_allotted_on_delete()` (line 64) | **MEDIUM** — On signal path; orchestrates balance sync | Tested indirectly via allocation balance tests |
| `update_is_allotted_on_save` | `signals.py` | 22 | post_save signal on AllotmentItems | `sender`, `instance` (AllotmentItems), `created`, `kwargs` | None | UPDATE AllotmentModel.is_allotted, calls update_license_balance() | On create/update of AllotmentItems: (1) set allotment.is_allotted = True, (2) update license balance | Triggered by: AllotmentItems.save() after allocate_items, update_allocation | **MEDIUM** — Signal chain; can race if multiple AllotmentItems saved rapidly | Indirectly tested via allocate tests; specific signal tests not observed |
| `update_is_allotted_on_delete` | `signals.py` | 41 | pre_delete signal on AllotmentItems | `sender`, `instance` (AllotmentItems), `kwargs` | None | UPDATE AllotmentModel.is_allotted, calls update_license_balance() via transaction.on_commit() | On delete of AllotmentItems: (1) check if allotment has remaining details, (2) if has_details → **DELETE ALL** details (⚠️ risk B2), (3) update license balance | Triggered by: AllotmentItems.delete() after delete_allotment_item() | **CRITICAL** — **Risk B2: deletes ALL details when checking for ANY** (line 56); logic appears inverted (should be "if NOT has_details"); see MODULE_3_FORENSIC_AUDIT.md risk B2 | Test coverage gap identified in MODULE_3_FORENSIC_AUDIT.md |

---

### 7. BALANCE CALCULATION HELPERS

| Function | File | Line | Class | Inputs | Outputs | Database Access | Business Rule | Callers | Risk Level | Tests |
|----------|------|------|-------|--------|---------|-----------------|---------------|---------|-----------|-------|
| `update_balance_values` | `calculate_balance.py` | [line unknown] | Module function | `import_item` (LicenseImportItemsModel) | None | UPDATE LicenseImportItemsModel (available_quantity, available_value columns) | Recomputes stored columns: (1) calculate_debited_quantity() = SUM(AllotmentItems.qty), (2) calculate_available_quantity() = original - debited, (3) calculate_available_value_calculated() = balance CIF from condition pools, (4) saves to DB | Called by: Signal chain after AllotmentItems save/delete; manual testing; nightly balance recalculation | **MEDIUM** — Core balance sync; must be idempotent (see MODULE_3_FORENSIC_AUDIT.md risk F3) | Tested indirectly; no explicit idempotency tests observed |
| `calculate_available_quantity` | `balance_calculator.py` | [line unknown] | ItemBalanceCalculator static method | `import_item` | Decimal | SELECT on LicenseImportItemsModel (stored columns) | **available_qty = original_quantity - SUM(AllotmentItems.qty where item_id matches)** — recomputes fresh (not using stale stored column) | Called by: `calculate_max_allocation()` (line 71 in allocation_service.py) | **LOW** — Fresh calculation, not cached | Indirectly tested |
| `calculate_item_balance` | `balance_calculator.py` | [line unknown] | ItemBalanceCalculator static method | `import_item` | Decimal | SELECT on LicenseImportItemsModel, condition pools | **available CIF balance** — computes via balance_calculator; branches on condition_type (%, AU, open) exactly like `available_value_calculated` | Called by: `calculate_max_allocation()` (line 72), plan enforcement, serializers | **MEDIUM** — Must match `available_value_calculated` branching | Tested indirectly |

---

### 8. SERIALIZERS

| Function | File | Line | Type | Inputs | Outputs | Database Access | Business Rule | Callers | Risk Level | Tests |
|----------|------|------|------|--------|---------|-----------------|---------------|---------|-----------|-------|
| `get_available_value` (method) | `license.py` (serializer) | 230 | SerializerMethodField | context (from available_value_bulk_map) | Decimal OR from bulk map | Uses context['available_value_map'] if provided, otherwise calls property | Returns item.available_value_calculated — used in list contexts via bulk map for performance | Called by: LicenseImportItemSerializer.to_representation() | **LOW** — Defers to bulk map if available | None observed |
| `AllotmentItemSerializer.get_*` methods | `serializers.py` | 32-80 | SerializerMethodFields | allotment_item (instance) | Various (str, date, choice) | SELECT on related License, LicenseItemName, export items (if not prefetched) | Accessors for nested data: license_number, license_date, expiry, registration, purchase_status, owner, transfer_status, condition_type | Called by: REST response serialization for AllotmentItems | **MEDIUM** — May trigger N+1 if related objects not prefetched | Indirectly tested via API responses |
| `AllotmentSerializer.create` | `serializers.py` | 173 | Method | `validated_data` dict | AllotmentModel instance | INSERT AllotmentModel | Creates new allotment with company, type, required_quantity, unit_value, etc. | Called by: POST /allotments | **LOW** — Standard create | Tested via create tests |
| `AllotmentSerializer.to_representation` | `serializers.py` | 192 | Method | `instance` (AllotmentModel) | JSON dict | Calls `get_display_label()`, balance properties (allotted_value, balanced_quantity) | Customizes output JSON; injects computed fields like display_label, allotment_details nested array | Called by: Response serialization | **MEDIUM** — References cached properties | Tested via API response tests |

---

### 9. HELPERS & UTILITIES

| Function | File | Line | Type | Inputs | Outputs | Database Access | Business Rule | Callers | Risk Level | Tests |
|----------|------|------|------|--------|---------|-----------------|---------------|---------|-----------|-------|
| `plan_grouping.group_ids_of` | `plan_enforcement.py` (imported from plan_grouping) | [imported] | Module function | `item` (LicenseImportItemsModel) | `[item_ids]` list of sibling item IDs | SELECT on LicenseImportItemsModel (siblings with same license + plan_group_key) | **Groups import items by (license_id, plan_group_key)** where plan_group_key = (HS code, product description) — used to enforce plan caps at group level, not per-item | Called by: `plan_status_for()` (line 274) | **MEDIUM** — Grouping logic; must correctly identify plan siblings | Tested indirectly via plan cap tests |
| `plan_grouping.plan_group_key` | `plan_enforcement.py` (imported from plan_grouping) | [imported] | Module function | `item` (LicenseImportItemsModel) | `(str, str)` tuple (hs_code, description) | SELECT on LicenseImportItemsModel.hs_code (FK deref) | **Returns (item.hs_code.code, item.product_description)** — plan group key for item; used to match item to its plan lines | Called by: `plan_status_for_ids()`, `plan_status_for_items()` | **LOW** — Simple key computation | Indirectly tested |
| `LicenseValidationService.validate_allocation` | `license/services/validation.py` (imported) | [not shown] | Service method | `allotment`, `import_item`, `qty`, `cif_fc` | `(bool, str)` or exception | Comprehensive multi-stage validation | Validates: license active, balance sufficient, restrictions honored, conditions met | Called by: `allocate_item()` in legacy code path (line 183 in allocation_service.py); NOT called by allocate_items view (inline checks used instead) | **MEDIUM** — Alternate validation path; not in primary flow | Not in primary flow tests |
| `filter_available_items` | `filter_service.py` | 264 | Method | `base_queryset`, `filters_dict` | Filtered QuerySet | Applies multiple .filter() / .exclude() / .distinct() calls in sequence | Orchestrates all filter types (quantity, value, expiry, hs_code, etc.); can trigger N+1 with .distinct() on M2M joins | Called by: `available_licenses()` endpoint | **MEDIUM** — Many .distinct() calls; see MODULE_3_FORENSIC_AUDIT.md for filtering architecture | Tested indirectly via available_licenses tests |
| `ItemBalanceCalculator.calculate_item_attributed_balances_for_items` | `balance_calculator.py` | [not shown] | Static method | `items` (list) | `{item_id: Decimal}` dict | SELECT on LicenseImportItemsModel (item-level CIF attribution) | **Batched calculation of item-attributed CIF balances** for items with positive item-level credits (vs license-level) | Called by: `available_value_bulk_map()` (line 331 in condition_pool.py) | **LOW** — Read-only aggregation | Indirectly tested |

---

## CROSS-FUNCTION DEPENDENCIES & CALL GRAPH

```
POST /allocate-items (AllotmentActionViewSet.allocate_items, views_actions.py:625)
  ├─ transaction.atomic wrapper
  ├─ LicenseImportItemsModel.select_for_update().get(id) — LOCK row
  ├─ license_expiry_date < today() — HARD FAIL
  ├─ available_quantity check — HARD FAIL
  ├─ available_value_calculated property — HARD FAIL (calls condition_pool)
  │  ├─ condition_pool._resolve_available_value(item, balance_map, pools_map)
  │  ├─ condition_pool.available_value_bulk_map() — if context provided
  │  ├─ compute_condition_pools_bulk() — aggregates per license
  │  └─ LicenseBalanceCalculator.calculate_financial_balance_for_licenses()
  ├─ balanced_quantity (via required_quantity - SUM, computed inline) — HARD FAIL
  ├─ plan_status_for(license_item) — plan cap check — HARD FAIL
  │  ├─ plan_grouping.group_ids_of(item) — SELECT siblings
  │  ├─ plan_status_for_ids(gids) — SELECT plans + AllotmentItems SUM
  │  └─ baseline_used - current_used logic
  ├─ AllotmentItems.objects.filter(allotment, item).first() — check for upsert
  │  ├─ If exists: += qty, cif_fc, cif_inr → save()
  │  └─ If not: create()
  ├─ POST_SAVE signal triggered:
  │  ├─ update_is_allotted_on_save() (signals.py:22)
  │  │  ├─ allotment.is_allotted = True
  │  │  └─ update_license_balance(item) — via transaction.on_commit()
  │  │     └─ update_balance_values(item) — UPDATE available_quantity column
  │  │        ├─ calculate_available_quantity() — fresh SUM
  │  │        ├─ calculate_item_balance() — condition pools
  │  │        └─ LicenseImportItemsModel.save()
  │  └─ Materialized view refresh signals (separate)
  ├─ [IF plan_line_id provided]
  │  ├─ LicenseItemPlan.select_for_update().get(id) — LOCK for decrement
  │  ├─ remaining_qty = max(0, current - qty)
  │  └─ LicenseItemPlan.save()
  └─ Response with created_items, errors, updated allotment

GET /available-licenses (AllotmentActionViewSet.available_licenses, views_actions.py:42)
  ├─ AllotmentModel.objects.prefetch_related(...)
  ├─ [IF debit_based_on='plan']
  │  └─ _available_licenses_plan_mode(request, allotment)
  ├─ [ELSE Actual mode]
  │  ├─ Build base queryset with select_related/prefetch_related
  │  ├─ Apply 15+ sequential filters via LicenseFilterService
  │  ├─ Paginate: slice + count
  │  ├─ ONE CALL: available_value_bulk_map(paginated_items) — line 313
  │  │  ├─ LicenseBalanceCalculator.calculate_financial_balance_for_licenses()
  │  │  ├─ compute_condition_pools_bulk(license_ids)
  │  │  └─ ItemBalanceCalculator.calculate_item_attributed_balances_for_items()
  │  ├─ ONE CALL: plan_map_for_import_items(page_item_ids) — line 321
  │  ├─ ONE CALL: billed_no_boe_bulk_map(page_item_ids) — line 323
  │  ├─ Serialize with context={'available_value_map': ...}
  │  │  └─ LicenseImportItemSerializer.get_available_value(context)
  │  ├─ ONE CALL: plan_status_for_items(paginated_items) — line 355
  │  └─ Response with paginated results + plan status

DELETE /delete-item/{item_id} (AllotmentActionViewSet.delete_allotment_item, views_actions.py:878)
  ├─ transaction.atomic wrapper
  ├─ AllotmentItems.get_object_or_404(id, allotment_id)
  ├─ LicenseImportItemsModel.select_for_update().get(item_id) — LOCK row
  ├─ AllotmentItems.delete()
  ├─ PRE_DELETE signal triggered:
  │  └─ update_is_allotted_on_delete() (signals.py:41)
  │     └─ update_license_balance(item) — via transaction.on_commit()
  │        └─ update_balance_values(item)
  └─ Response with success message
```

---

## DATABASE ACCESS SUMMARY

| Operation | Functions | Lock Type | Isolation Concern |
|-----------|-----------|-----------|------------------|
| Read available_quantity (stored) | allocate_items line 694 | None (snapshot) | Stale between page load and submit (mitigated by line 722 live balance check) |
| Read available_value_calculated (live) | allocate_items line 722, available_licenses, serializers | None | Calls condition_pool + balance calculator; recomputed fresh each time |
| Read plan_status_for (live) | allocate_items line 761, available_licenses line 355 | None | **RACE WINDOW** (see MODULE_3_FORENSIC_AUDIT.md risk A1) — aggregate not locked |
| Read balanced_quantity (cached property) | allocate_items line 735 recomputes inline | None | Cached property not used; inline fresh computation (line 733-735) |
| Write LicenseImportItemsModel | select_for_update line 671 | ROW-LEVEL LOCK | Held for duration of allocate_items transaction (667-852) |
| Write AllotmentItems | allocate_items lines 795, 802 | Transaction (no explicit lock) | Multiple AllotmentItems in one POST can race on .first() check (risk A3) |
| Write LicenseItemPlan (plan line) | select_for_update line 836 | ROW-LEVEL LOCK | Locked only during decrement (line 843), not during cap check (line 761) |
| Write AllotmentModel.is_allotted | Signal handler line 33 | Transaction | Committed after AllotmentItems.save() |
| Update available_quantity column | update_balance_values via signal | Transaction | Committed via transaction.on_commit() after AllotmentItems transaction |

---

## BUSINESS RULES ENFORCEMENT MATRIX

| Rule | Enforced By | Location | Timing | Guaranteed? | Bypass Risk |
|------|-------------|----------|--------|-------------|------------|
| License not expired | expiry check | allocate_items:680 | Pre-allocate | ✅ Yes | ⚠️ B2: no re-check on update_allocation() |
| Available quantity sufficient | available_quantity check | allocate_items:694 | Pre-allocate | ✅ Yes (select_for_update locks) | ⚠️ Stale between page load & confirm (mitigated by line 722) |
| Available value sufficient | available_value_calculated check | allocate_items:722 | Pre-allocate | ✅ Yes (live computed) | ⚠️ O(1) per item in batch; recomputes condition pools |
| Allotment balance not exceeded | balanced_quantity check | allocate_items:735 | Pre-allocate | ✅ Yes (computed fresh inline) | None observed |
| Plan cap not exceeded | plan_status_for check | allocate_items:761 | Pre-allocate | ⚠️ PARTIAL (see A1) | ⚠️ A1: race window between read & lock |
| Allocation upsert atomicity | unique_together on (item, allotment) | models.py:248 | Create/Update | ⚠️ PARTIAL | ⚠️ A3: .first() check not under lock |
| Plan line balance decremented | Explicit decrement | allocate_items:836-844 | Post-allocate | ✅ Yes (select_for_update) | ⚠️ D1: stale plan_line_id caught gracefully, allocation still succeeds |
| License balance recalculated | Signal chain + on_commit | signals.py:22, models.py:354 | Post-allocate | ✅ Yes (synchronous) | ⚠️ E3: if update_balance_values() throws, balance stale |
| Allotment.is_allotted set | Signal handler | signals.py:22, 33 | Post-allocate | ✅ Yes | None observed |

---

## TEST COVERAGE ASSESSMENT

| Test File | Functions Tested | Gaps | Risk Level |
|-----------|------------------|------|-----------|
| `test_allocate_items_cif_validation.py` | available_value_calculated (live vs cached), allocate_items validation chain | Zero balance, negative balance, concurrent allocations | **HIGH** — Stale balance rejection tested, but concurrent race untested |
| `test_allocate_items_expiry_check.py` | License expiry gate, multi-condition types | Expiry during transaction window (unlikely edge case) | **MEDIUM** — Boundary cases well-covered |
| `test_allocate_items_group_plan_cap.py` | Plan consolidation, group cap enforcement, sibling independence | Concurrent re-planning mid-allocate (A1 scenario) | **HIGH** — Group logic correct, but race untested |
| `test_allocate_items_e1_group_plan_cap.py` | E1-specific HSN grouping, independent caps | >2-sibling scenarios | **MEDIUM** — E1 edge case covered |
| `test_allocate_items_plan_line_balance.py` | Plan line per-line balance decrement, stale plan_line_id graceful handling | Plan line value mismatch (unit_price change post-alloc) | **MEDIUM** — Stale reference accepted as design |
| `test_available_licenses_filters.py` | Filter combinations, stale balance handling in list context | N+1 queries in filter chain, filter combinations | **LOW** — Filters tested, but not performance |
| **Missing** | Race condition A1 (concurrent allocations on same item), race condition A3 (AllotmentItems upsert), signal B2 (delete cascade), concurrent re-planning | Multiple simultaneous allocate_items on same item | **CRITICAL** — Concurrency untested |

---

## RISK SUMMARY & REMEDIATION

| Risk ID | Severity | Likelihood | Functions Affected | Fix Strategy | Effort |
|---------|----------|-----------|---------------------|-------------|--------|
| **A1** | CRITICAL | Medium | `allocate_items()`, `plan_status_for()` | Move plan cap check BEFORE select_for_update() lock, or lock LicenseItemPlan rows during cap check | 2-3 days |
| **A3** | HIGH | Medium | `allocate_items()` (line 788) | Use select_for_update() on AllotmentItems.objects before .first() check | 1 day |
| **B2** | CRITICAL | Low | `update_is_allotted_on_delete()` (signals.py:56) | Fix logic: delete only the instance being deleted, not all details | 1 hour |
| **D1** | HIGH | Low | `allocate_items()` (line 846) | Log DoesNotExist exception; return error to user instead of silent pass | 2 hours |
| **E2** | MEDIUM | Low | `update_allocation()` (allocation_service.py:228) | Add expiry check matching allocate_items (line 680) | 1 hour |
| **E3** | MEDIUM | Low | `delete_stock` signal (models.py:360) | Re-raise exception if update_balance_values() fails; don't swallow errors | 2 hours |

---

## FILE LOCATIONS REFERENCE

| Component | File Path |
|-----------|-----------|
| View entry points | `/backend/apps/allotment/views_actions.py` |
| Main viewset | `/backend/apps/allotment/views.py` |
| Allocation service | `/backend/apps/allotment/services/allocation_service.py` |
| Validation service | `/backend/apps/allotment/services/validation_service.py` |
| Models | `/backend/apps/allotment/models.py` |
| Signals | `/backend/apps/allotment/signals.py` |
| Plan enforcement | `/backend/apps/license/services/plan_enforcement.py` |
| Condition pool | `/backend/apps/license/services/condition_pool.py` |
| Balance calculator | `/backend/apps/license/services/balance_calculator.py` |
| Balance script | `/backend/apps/core/scripts/calculate_balance.py` |
| Serializers | `/backend/apps/allotment/serializers.py` |
| License serializers | `/backend/apps/license/serializers/license.py` |
| Tests | `/backend/apps/allotment/tests/test_allocate_items_*.py` |

---

**End of MODULE_3_MASTER_FUNCTION_INVENTORY.md**

Generated: 2026-08-10 | Source: MODULE_3_FORENSIC_AUDIT.md + complete codebase analysis
