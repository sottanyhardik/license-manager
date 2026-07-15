# Business Decision Log

> **Domain decisions and their rationale.**  
> Preserved so future developers understand WHY rules exist, not just WHAT they are.  
> Last updated: 2026-07-15 (feature/V1).

---

## BD-001: Allotment Cannot Exceed Available Balance ✅ APPROVED

**Decision date**: 2026-07-15  
**Status**: APPROVED — awaiting implementation

**Decision**: An allotment is a reservation. A reservation must never exceed what is currently available. Validation must enforce both quantity (per item) and CIF FC (per license).

### Validation Rules (approved)

**Item-level check** (for each AllotmentItem being created):
```
allotment.qty <= LicenseImportItemsModel.available_quantity
```

**License-level check** (for the entire allotment batch):
```
SUM(allotment_items.cif_fc) <= LicenseBalance.balance_cif
```

Both checks must:
- Run inside `transaction.atomic()`
- Use `select_for_update()` on the target row to prevent concurrent races
- Reject atomically — no partial writes
- Return clear validation errors identifying which limit was exceeded

**Rationale**: Allotments are forward reservations. Allowing over-reservation would cause `balance_cif` to go negative before any physical import occurs, making the license appear exhausted before actual consumption.

### Current Implementation Gap

`_validate_plan_availability()` in `allotment_service.py` only checks against `LicenseItemPlan` (the optional forward-planning model). It does NOT check:
- `LicenseBalance.balance_cif` (actual available CIF on license)
- `LicenseImportItemsModel.available_quantity` (actual available qty per import item)

If no `LicenseItemPlan` row exists, there is currently ZERO validation.

### Files Affected by Implementation

| File | Change Required |
|---|---|
| `backend/apps/allotment/services/allotment_service.py` | Add `_validate_balance_availability(license_id, items_data)` function; call it inside `create_allotment()` |
| `backend/apps/license/models/license.py` | Read `LicenseBalance.balance_cif` and `LicenseImportItemsModel.available_quantity` |
| `backend/apps/allotment/serializers.py` | Error response shape for the new validation |
| `backend/tests/allotment/test_allotment.py` | Add test: over-qty rejected; Add test: over-CIF rejected; Add test: concurrent safe |
| `frontend/src/features/allotments/components/AllotmentForm.tsx` | Display validation error messages from new guards |
| `docs/business-rules/business-rule-index.md` | Add rules ALLOT-008, ALLOT-009 |

### Concurrency Safety Requirement

The new check must use `select_for_update()` on both:
1. `LicenseBalance.objects.select_for_update().get(license_id=...)` — to lock the license balance row
2. `LicenseImportItemsModel.objects.select_for_update().filter(pk__in=item_ids)` — to lock each item row

This prevents two concurrent allotment requests each "seeing" sufficient balance and both passing validation.

---

## BD-002: Duplicate Import Items — Grouped for Planning/Reports, Raw for Transactions ✅ APPROVED

**Decision date**: 2026-07-15  
**Status**: APPROVED — awaiting implementation

**Decision**: Import Item rows must NEVER be merged in storage. Every original row must remain. However, for planning and reporting, duplicate Import Items must be grouped.

### Grouping Key: `ItemNameModel`

The canonical grouping key is **`ItemNameModel.id` / `ItemNameModel.name`**.

Evidence:
- `LicenseImportItemsModel.items` is a `ManyToManyField` to `core.ItemNameModel`
- `ItemNameModel.name` is `unique=True` — each distinct item has a canonical name
- The serial_number field (`LicenseImportItemsModel.serial_number`) is a legal row identifier (DGFT-assigned SR number) — it cannot be used as a grouping key

### How Grouping Works

```
License rows (stored as-is):
  SR-001: Dietary Fiber — 500 KG (items M2M → ItemNameModel id=42 "Dietary Fiber")
  SR-002: Dietary Fiber — 300 KG (items M2M → ItemNameModel id=42 "Dietary Fiber")
  SR-003: Dietary Fiber — 200 KG (items M2M → ItemNameModel id=42 "Dietary Fiber")

Grouped view (for planning/reports):
  ItemNameModel id=42 "Dietary Fiber" — 1000 KG (SUM of SR-001 + SR-002 + SR-003)
```

### Where Raw Rows Must Be Used (no grouping)

| Feature | Why |
|---|---|
| Allotment creation | Allotments reference specific SR numbers (AllotmentItems.item FK → LicenseImportItemsModel) |
| BOE RowDetails | RowDetails.sr_number FK → individual import item row |
| Ledger | Each SR transaction must be traceable |
| Audit trail | Historical records are SR-specific |
| AllotmentItems | `unique_together = (item, allotment)` enforces per-SR uniqueness |

### Where Grouped View Must Be Used

| Feature | Grouping |
|---|---|
| Planning (`LicenseItemPlan`) | One plan per `ItemNameModel` per license |
| Balance reports | Group `available_quantity` by `ItemNameModel` |
| Item utilisation reports | Group `debited_quantity` by `ItemNameModel` |
| Pivot reports | Group by SION norm class (already uses `ItemNameModel.sion_norm_class`) |
| Planning UI display | Show grouped totals alongside individual SR rows |

### Implementation Notes

**Grouping query**:
```python
from django.db.models import Sum

# Get all ItemNameModel IDs for a license:
LicenseImportItemsModel.objects
  .filter(license_id=license_id)
  .prefetch_related("items")

# Group by ItemNameModel:
# For each unique ItemNameModel, sum: quantity, available_quantity, debited_quantity, allotted_quantity
```

**`LicenseItemPlan` adjustment**: Currently `LicenseItemPlan` has `import_item` FK → `LicenseImportItemsModel` (one plan per SR row). Per BD-002, plans should be at the `ItemNameModel` level. This requires either:
- Changing `LicenseItemPlan.import_item` FK to point to `ItemNameModel` instead, OR
- Grouping multiple `LicenseItemPlan` rows by `ItemNameModel` when displaying

**Recommendation**: Keep the existing FK structure (backward compatible). Add a `_group_items_by_name(license_id)` helper function in `balance_service.py` that returns grouped totals.

### Files Affected by Implementation

| File | Change Required |
|---|---|
| `backend/apps/license/services/balance_service.py` | Add `group_import_items_by_name(license_id)` helper |
| `backend/apps/reports/services/balance_report.py` | Use grouped view for report output |
| `backend/apps/reports/services/item_report.py` | Group by ItemNameModel |
| `backend/apps/reports/services/pivot_report.py` | Group by ItemNameModel → norm_class |
| `backend/apps/license/serializers/license.py` | Add `ImportItemGroupedSerializer` for planning/reports |
| `backend/apps/license/views/license.py` | Add endpoint for grouped import items |
| `frontend/src/features/licenses/components/LicenseImportItems.tsx` | Add grouped summary row |
| `docs/business-rules/business-rule-index.md` | Add rules LIC-016, LIC-017 |

---

## BD-003: BOE May Exceed Available Balance — Negative Balance Tracking ✅ APPROVED

**Decision date**: 2026-07-15  
**Status**: APPROVED — awaiting implementation

**Decision**: BOE creation must never be blocked. Actual customs clearance may legitimately exceed the currently available balance. The system must allow it and track the negative balance with full alerting.

### Required Behavior

When `balance_cif < 0` after a BOE:
1. Record the negative balance correctly (no floor)
2. Set `LicenseFlags.is_negative_balance = True`
3. Create an `ActivityLog` event type `NEGATIVE_BALANCE`
4. Show visible warning in License UI (red badge)
5. Include in dashboard alerts (new "Negative Balance" KPI card)
6. Include in exception reports
7. Do NOT automatically reject, adjust, or reverse

### Example

```
Available CIF FC:  USD 100.00
BOE CIF FC:        USD 120.00
Balance after:     USD -20.00  (allowed — not blocked)
Status:            ⚠ NEGATIVE BALANCE
Alert:             Dashboard shows 1 license with negative balance
```

### Current Implementation Gap

`recompute_license_balance()` currently uses `max(_DEC_0, raw_balance)` which floors at 0. This must be removed for `balance_cif` calculation.

`_update_item_level_balances()` similarly floors `available_quantity` at 0. This also must allow negative.

No `is_negative_balance` flag exists in `LicenseFlags`. This requires a new DB field.

### Migration Consideration (CRITICAL)

`LicenseFlags` is `managed=False` — the table is owned by the legacy PostgreSQL database. Adding `is_negative_balance` requires:

**Option A** (preferred): Add the column to the legacy DB via the legacy backend's migration, then expose it in the new backend's model definition.

**Option B** (interim): Compute `is_negative_balance` dynamically from `balance_cif < 0` (a `@property` on the model or in the serializer). No DB change needed. Less efficient but unblocks frontend work.

**Recommendation**: Use Option B (computed property) for the initial implementation. Plan Option A as a follow-up migration.

### Formula Changes Required

**License-level** (`balance_service.recompute_license_balance`):
```python
# CURRENT (wrong — floors at zero):
balance = max(_DEC_0, raw_balance).quantize(...)

# NEW (allows negative):
balance = raw_balance.quantize(_TWO_PLACES, rounding=ROUND_DOWN)
# No max() wrapper
```

**Item-level** (`balance_service._update_item_level_balances`):
```python
# CURRENT (wrong — floors at zero):
avail_qty = max(_DEC_0, total_qty - deb_qty - allt_qty).quantize(...)

# NEW (allows negative):
avail_qty = (total_qty - deb_qty - allt_qty).quantize(_THREE_PLACES, rounding=ROUND_DOWN)
# No max() wrapper
```

**Flag logic** (`balance_service.recompute_license_balance`):
```python
# ADD:
is_negative_balance = balance < _DEC_0
is_null = _DEC_0 <= balance < _NULL_THRESHOLD  # only meaningful when balance >= 0

# WRITE:
LicenseFlags.objects.update_or_create(
    license_id=license_id,
    defaults={
        "is_null": is_null,
        "is_expired": is_expired,
        "is_negative_balance": is_negative_balance,  # NEW field (via Option B: property)
    },
)
```

### Files Affected by Implementation

| File | Change Required |
|---|---|
| `backend/apps/license/services/balance_service.py` | Remove `max(_DEC_0, ...)` from both formulas; add `is_negative_balance` logic |
| `backend/apps/license/models/license.py` | Add `is_negative_balance` to `LicenseFlags` (computed property or DB field) |
| `backend/apps/license/serializers/license.py` | Expose `is_negative_balance` in `LicenseFlagsSerializer` |
| `backend/apps/dashboard/services/dashboard_service.py` | Add `negative_balance` KPI count |
| `backend/apps/dashboard/serializers.py` | Expose negative balance count |
| `backend/apps/core/models/masters.py` | Add `NEGATIVE_BALANCE` to `ActivityLog.ACTION_CHOICES` |
| `backend/apps/reports/services/balance_report.py` | Include negative balance flag in output |
| `frontend/src/features/licenses/components/LicenseStatusBadge.tsx` | Add negative balance variant |
| `frontend/src/features/licenses/components/LicenseBalancePanel.tsx` | Show red warning when balance < 0 |
| `frontend/src/features/dashboard/components/StatCard.tsx` | New negative-balance card |
| `frontend/src/features/dashboard/pages/Dashboard.tsx` | Add negative balance stat |
| `docs/business-rules/business-rule-index.md` | Update LIC-003 (was "balance >= 0", now "balance may be negative") |
| `docs/business-rules/balance-calculations.md` | Remove "clamped to zero" section |

### Tests Required

| Test | Description |
|---|---|
| `test_balance_can_be_negative` | BOE exceeds credit → balance is negative (no floor) |
| `test_is_negative_balance_flag` | balance < 0 → is_negative_balance = True |
| `test_is_null_not_set_when_negative` | balance < 0 does NOT set is_null |
| `test_item_available_quantity_can_be_negative` | BOE qty > total qty → available_quantity < 0 |
| `test_boe_creation_never_rejected_for_balance` | Creating BOE with insufficient balance → allowed, not rejected |

---

## Previous Business Decisions

## BD-004: Balance Is Async, Never Synchronous
**(Previously BD-001 in original numbering)**  
**Status**: IMPLEMENTED — See `license/tasks.py`

## BD-005: managed=False For All Business Tables
**(Previously BD-002)**  
**Status**: IMPLEMENTED — All business models have `managed=False`

## BD-006: Planning Is Optional (No Restriction Without Plan)
**(Previously BD-003)**  
**Status**: IMPLEMENTED — `_validate_plan_availability` returns early when no `LicenseItemPlan` row exists. **Note**: BD-001 ABOVE adds validation against the actual balance even without a plan row.

## BD-007: Allotment Exits Balance Formula When BOE Is Linked
**(Previously BD-004)**  
**Status**: IMPLEMENTED — `allotment__bill_of_entry__isnull=True` filter

## BD-008: 3 Decimal Places for `pct` and `rate_pct`
**(Previously BD-005)**  
**Status**: IMPLEMENTED — `Decimal(str(pct))` before dividing by 100

## BD-009: Redis DB Isolation (Cache/Broker/Results Separated)
**(Previously BD-006)**  
**Status**: IMPLEMENTED — `/1`, `/2`, `/3` separation

## BD-010: `ooc_date` Must Remain CharField(255)
**(Previously BD-007)**  
**Status**: IMPLEMENTED — Raw ICEGATE text format

## BD-011: Celery Tasks Use `acks_late=True`
**(Previously BD-008)**  
**Status**: IMPLEMENTED — All financial tasks

## BD-012: `UserSerializer` Must Include `is_superuser`
**(Previously BD-009)**  
**Status**: IMPLEMENTED — Frontend RBAC navigation requires it

## BD-013: BOE Row Scoping Prevents IDOR
**(Previously BD-010)**  
**Status**: IMPLEMENTED — `bill_of_entry_id=boe_id` scoping on all row operations

---

## Open Questions

| # | Question | Context | Decision Required |
|---|---|---|---|
| OQ-1 | When does cutover happen? | Currently parallel-run | Product decision |
| OQ-2 | Should `LicenseItemPlan` be grouped by `ItemNameModel`? | BD-002 grouping | Engineering decision (see BD-002 notes) |
| OQ-3 | `is_negative_balance` as DB field vs computed property? | BD-003 | DB migration timing decision |
| OQ-4 | Should negative `available_quantity` be displayed or hidden in UI? | BD-003 item-level | UX decision |
| OQ-5 | JWT RS256 migration post-cutover? | ADR-006 | Architecture decision |
