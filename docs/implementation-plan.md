# Implementation Plan — Approved Business Decisions

> **Date**: 2026-07-15  
> **Scope**: BD-001 (Allotment Validation), BD-002 (Duplicate Items Grouping), BD-003 (Negative Balance)  
> **Status**: Documentation complete. Awaiting engineering sign-off before code changes begin.  
> **Rule**: No code changes until this plan is reviewed and approved.

---

## Pre-Implementation Checklist

Before writing any code for any BD:

- [ ] Run existing test suite: `pytest backend/tests/ -q` → must be 165 passed
- [ ] Read `docs/claude/balance-context.md` (invariants to preserve)
- [ ] Read `docs/playbooks/balance-module-playbook.md` (change checklist)
- [ ] Verify `docs/business-decisions.md` BD entry is marked APPROVED

---

## BD-001: Allotment Validation Against Available Balance

### Complexity: MEDIUM

### Implementation Order

**Step 1 — Add balance-level validation function** (backend only)

File: `backend/apps/allotment/services/allotment_service.py`

New function `_validate_balance_availability(license_id, items_data)`:

```python
def _validate_balance_availability(
    license_id: int,
    items_data: list[dict],
) -> None:
    """
    Validate that the allotment batch does not exceed available balance.
    
    Two checks:
    1. Per-item: allotment qty <= item.available_quantity
    2. License-level: total allotment CIF <= balance_cif
    
    Both use select_for_update() to prevent concurrent races.
    Must be called inside transaction.atomic().
    
    Raises ValidationError (atomic — no partial writes possible).
    """
    from apps.license.models import LicenseBalance, LicenseImportItemsModel

    # Lock balance row for the license
    try:
        balance = LicenseBalance.objects.select_for_update().get(license_id=license_id)
        available_cif = balance.balance_cif
    except LicenseBalance.DoesNotExist:
        available_cif = Decimal("0")

    total_allotment_cif = sum(
        Decimal(str(item.get("cif_fc") or 0)) for item in items_data
    )

    if total_allotment_cif > available_cif:
        raise ValidationError(
            f"Total allotment CIF {total_allotment_cif} exceeds available license "
            f"balance {available_cif}."
        )

    # Per-item quantity check
    item_ids = [item.get("item") for item in items_data if item.get("item")]
    items = {
        item.pk: item
        for item in LicenseImportItemsModel.objects.select_for_update().filter(
            pk__in=item_ids
        )
    }
    for item_dict in items_data:
        item_id = item_dict.get("item")
        qty_requested = Decimal(str(item_dict.get("qty") or 0))
        if not item_id:
            continue
        item = items.get(item_id)
        if item and qty_requested > item.available_quantity:
            raise ValidationError(
                f"Requested quantity {qty_requested} exceeds available quantity "
                f"{item.available_quantity} for import item SR-{item.serial_number}."
            )
```

**Step 2 — Call the new validator from `create_allotment`**

In `create_allotment()`, after the existing `_validate_plan_availability` calls, add:

```python
# Validate against ACTUAL available balance (BD-001)
# First resolve the license_id from the first item's import item
if items_data:
    first_item_id = items_data[0].get("item")
    if first_item_id:
        from apps.license.models import LicenseImportItemsModel
        try:
            license_id = LicenseImportItemsModel.objects.get(
                pk=first_item_id
            ).license_id
            _validate_balance_availability(license_id, items_data)
        except LicenseImportItemsModel.DoesNotExist:
            pass  # item validation will catch this
```

**Step 3 — Write tests**

File: `backend/tests/allotment/test_allotment.py` or new `backend/tests/balance/test_bd001_allotment_validation.py`

Required tests:
- `test_allotment_rejected_when_exceeds_license_cif_balance`
- `test_allotment_rejected_when_item_qty_exceeds_available_qty`
- `test_allotment_allowed_when_within_balance`
- `test_allotment_concurrent_requests_safe` (uses `select_for_update`)
- `test_allotment_partial_rejection_no_partial_writes`

**Step 4 — Frontend error display**

Existing `AllotmentForm.tsx` already shows `ValidationError` from server. Verify the new error messages display correctly.

### Migration Requirements

None — no new DB fields.

### Backward Compatibility

Existing allotments without plans: now subject to the balance check. In production data, some allotments may exist that exceed the current balance (because the check didn't exist before). A data audit should be run before activating this.

---

## BD-002: Duplicate Import Items — Grouped View

### Complexity: LOW-MEDIUM (additive — no existing behavior changed)

### Implementation Order

**Step 1 — Add grouping helper to balance_service.py**

```python
def group_import_items_by_name(license_id: int) -> list[dict]:
    """
    Group LicenseImportItemsModel rows by ItemNameModel for planning/reports.
    
    Rows are NEVER merged in storage. This returns a computed view only.
    Preserves raw rows for allotment, BOE, audit.
    
    Grouping key: ItemNameModel.id (unique name in the system)
    
    Returns list of dicts: [{
        'item_name_id': int,
        'item_name': str,
        'total_quantity': Decimal,
        'available_quantity': Decimal,  # SUM across all rows for this name
        'debited_quantity': Decimal,
        'allotted_quantity': Decimal,
        'sr_numbers': list[int],        # for traceability back to raw rows
        'row_ids': list[int],           # raw row PKs
    }]
    """
    from apps.license.models import LicenseImportItemsModel
    from django.db.models import Sum
    from collections import defaultdict

    items = (
        LicenseImportItemsModel.objects
        .filter(license_id=license_id)
        .prefetch_related("items")  # ItemNameModel M2M
    )

    groups: dict = defaultdict(lambda: {
        'total_quantity': Decimal("0"),
        'available_quantity': Decimal("0"),
        'debited_quantity': Decimal("0"),
        'allotted_quantity': Decimal("0"),
        'sr_numbers': [],
        'row_ids': [],
    })

    for item in items:
        # Use first linked ItemNameModel as the canonical group key
        item_names = list(item.items.all())
        if item_names:
            key_id = item_names[0].id
            key_name = item_names[0].name
        else:
            # Fallback: use description as group key (ungroupable items)
            key_id = f"desc:{item.description}"
            key_name = item.description or f"SR-{item.serial_number}"

        g = groups[(key_id, key_name)]
        g['total_quantity'] += item.quantity or Decimal("0")
        g['available_quantity'] += item.available_quantity or Decimal("0")
        g['debited_quantity'] += item.debited_quantity or Decimal("0")
        g['allotted_quantity'] += item.allotted_quantity or Decimal("0")
        g['sr_numbers'].append(item.serial_number)
        g['row_ids'].append(item.pk)

    return [
        {
            'item_name_id': k[0],
            'item_name': k[1],
            **v,
        }
        for k, v in sorted(groups.items(), key=lambda x: x[0][1])
    ]
```

**Step 2 — Add grouped endpoint to license views**

```
GET /api/v1/licenses/{id}/items/grouped/
```

Returns the grouped view. Used by planning and report UIs.

**Step 3 — Update report services**

`balance_report.py`, `item_report.py`, `pivot_report.py` should optionally accept `grouped=True` parameter and return grouped data.

**Step 4 — Frontend display**

`LicenseImportItems.tsx`: Add a toggle "Group by item name" that switches between raw and grouped views.

### What Does NOT Change

- `AllotmentItems.item` FK → `LicenseImportItemsModel` (still SR-level)
- `RowDetails.sr_number` FK → `LicenseImportItemsModel` (still SR-level)
- All existing BOE, allotment, ledger behavior
- `LicenseItemPlan` structure (still per SR row)

### Migration Requirements

None — no new DB fields. Purely additive.

---

## BD-003: Negative Balance Tracking

### Complexity: HIGH (formula change + new model field + alerting)

### Implementation Order

**Step 1 — Formula change in balance_service.py** (HIGHEST RISK)

Read `backend/apps/license/services/balance_service.py` fully.

**Change 1**: Remove `max(_DEC_0, ...)` from `balance_cif`:
```python
# BEFORE:
balance = max(_DEC_0, raw_balance).quantize(_TWO_PLACES, rounding=ROUND_DOWN)

# AFTER:
balance = raw_balance.quantize(_TWO_PLACES, rounding=ROUND_DOWN)
```

**Change 2**: Remove `max(_DEC_0, ...)` from `available_quantity`:
```python
# BEFORE:
avail_qty = max(_DEC_0, total_qty - deb_qty - allt_qty).quantize(...)

# AFTER:
avail_qty = (total_qty - deb_qty - allt_qty).quantize(_THREE_PLACES, rounding=ROUND_DOWN)
```

**Change 3**: Add `is_negative_balance` flag logic:
```python
is_negative_balance = balance < _DEC_0
is_null = _DEC_0 <= balance < _NULL_THRESHOLD  # updated: only when balance >= 0
```

**Step 2 — Add `is_negative_balance` to LicenseFlags model**

Option B (DB-free interim approach):

```python
# In LicenseFlags model, add computed property:
@property
def is_negative_balance(self) -> bool:
    """True when license balance_cif < 0. Computed from LicenseBalance."""
    try:
        return self.license.balance.balance_cif < Decimal("0")
    except Exception:
        return False
```

Option A (preferred long-term): Add `is_negative_balance = models.BooleanField(default=False)` to the legacy DB table and Django model.

**Step 3 — ActivityLog event**

```python
# In recompute_license_balance(), after writing LicenseFlags:
if is_negative_balance:
    from apps.core.models import ActivityLog
    ActivityLog.objects.create(
        module="LICENSE",
        action="NEGATIVE_BALANCE",
        obj_id=license_id,
        description=f"Balance went negative: {balance}",
    )
```

**Step 4 — Dashboard KPI**

In `dashboard_service.get_dashboard_stats()`:
```python
negative_balance = Count("pk", filter=Q(
    flags__is_active=True,
    balance__balance_cif__lt=Decimal("0")
))
```

**Step 5 — Frontend warning badge**

`LicenseStatusBadge.tsx`: Add `NEGATIVE_BALANCE` variant (red/orange with ⚠ icon).
`LicenseBalancePanel.tsx`: Show red warning banner when `balance_cif < 0`.

### Tests Required (must be written before implementation)

```python
def test_balance_can_be_negative():
    """BD-003: BOE exceeding credit produces negative balance (not zero)."""
    
def test_is_negative_balance_flag():
    """BD-003: balance < 0 sets is_negative_balance = True."""
    
def test_is_null_not_set_when_negative():
    """BD-003: negative balance does NOT set is_null."""
    
def test_item_available_quantity_can_be_negative():
    """BD-003: item available_quantity may go negative."""
```

### Migration Requirements

**Option B (interim)**: No migration — computed property only.  
**Option A (preferred)**: `ALTER TABLE license_licenseflags ADD COLUMN is_negative_balance BOOLEAN DEFAULT FALSE;` — must be coordinated with legacy team.

### Backward Compatibility

**CRITICAL**: Existing `balance_cif` values in production DB are all `>= 0` (floored by current code). After the formula change, if a recompute runs on a license where `debit + allotment > credit`, the balance will correctly show negative. This is the INTENDED behavior per BD-003.

All existing tests that assert `balance_cif >= 0` must be updated to allow negative values where the test data warrants it.

---

## Regression Test Plan

After implementing all three BDs, the following regression tests must ALL pass:

### BD-001 Regression

| Test | Expected |
|---|---|
| Existing `test_create_allotment_allowed_without_plan` | Still passes (no plan = still need balance check) |
| New: `test_allotment_rejected_when_exceeds_balance_cif` | ValidationError raised |
| New: `test_allotment_rejected_when_item_qty_exceeds_available` | ValidationError raised |
| New: `test_allotment_allowed_when_within_balance` | Allotment created |

### BD-002 Regression

| Test | Expected |
|---|---|
| All existing allotment tests | Unchanged (still uses raw SR rows) |
| All existing BOE tests | Unchanged |
| New: `test_group_import_items_by_name_sums_correctly` | Groups produce correct totals |
| New: `test_group_preserves_raw_rows` | Raw rows unchanged after grouping |

### BD-003 Regression

| Test | Expected |
|---|---|
| `test_balance_never_negative` | **Must be updated** — now `test_balance_formula_all_components` |
| `test_over_allotment_rejected` | **Must be updated** — is_null logic changes |
| New: `test_balance_can_be_negative` | Passes with negative value |
| All 165 existing tests | Must still pass |

---

## Implementation Sequence

Recommended order to minimize risk:

1. **BD-002 first** (additive only — no existing behavior changes, lowest risk)
2. **BD-001 second** (adds new validation — existing allotments may fail in production data audit)
3. **BD-003 last** (formula change — highest impact, must be carefully tested)

Each BD gets its own PR/commit. Do not combine.
