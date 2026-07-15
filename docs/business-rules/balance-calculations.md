# License Balance Calculations — Complete Reference

> **Source of truth** — generated from actual implementation in `balance_service.py`.  
> Last updated: 2026-07-15 (feature/V1 + BD-001/BD-003 approvals).
>
> ⚠️ **PENDING IMPLEMENTATION**: BD-001 adds allotment validation against `balance_cif`.  
> ⚠️ **PENDING IMPLEMENTATION**: BD-003 removes the zero-floor from `balance_cif`.  
> Current implementation notes include both the current state AND the approved future state.

---

## 1. Overview

The license balance system tracks how much of a license's authorised import value (CIF) has been consumed. Three levels of tracking:

1. **License-level**: `LicenseBalance.balance_cif` — remaining CIF in foreign currency
2. **Item-level**: `LicenseImportItemsModel.available_quantity` — remaining quantity per SR row
3. **Planning**: `LicenseItemPlan.planned_quantity` — remaining plan allocation per item

---

## 2. License-Level Balance Formula

**Source**: `balance_service.recompute_license_balance(license_id)`  
**File**: `backend/apps/license/services/balance_service.py`

### CURRENT (pre-BD-003)

```python
raw_balance = credit - debit - allotment - trade
balance_cif = max(0, raw_balance).quantize(TWO_PLACES, ROUND_DOWN)  # FLOORS AT ZERO
```

### APPROVED (post-BD-003 — pending implementation)

```python
raw_balance = credit - debit - allotment - trade
balance_cif = raw_balance.quantize(TWO_PLACES, ROUND_DOWN)  # NO FLOOR — may be negative
```

**Rationale**: BOE creation cannot be blocked. When actual imports exceed the license authorization, the balance must reflect reality (negative), not a silently floored zero.

| Variable | Formula | Source |
|---|---|---|
| `credit` | `SUM(LicenseExportItemModel.cif_fc)` | Export items on the license |
| `debit` | `SUM(RowDetails.cif_fc WHERE type='D' AND no trade)` | BOE RowDetails (actual imports) |
| `allotment` | `SUM(AllotmentItems.cif_fc WHERE no BOE linked)` | Pending allotments |
| `trade` | `SUM(LicenseTradeLine.cif_fc WHERE direction='SALE')` | License sold to another party |

---

## 3. Item-Level Balance Formula

**Source**: `balance_service._update_item_level_balances(license_id)`

### CURRENT (pre-BD-003)

```python
available_quantity = max(0, quantity - debited_quantity - allotted_quantity)  # FLOORS AT ZERO
```

### APPROVED (post-BD-003 — pending implementation)

```python
available_quantity = (quantity - debited_quantity - allotted_quantity)  # NO FLOOR
```

**Key**: This formula operates per **SR row** (by `LicenseImportItemsModel.pk`). Duplicate items with the same `ItemNameModel` are NOT summed here — each SR row is computed independently.

---

## 4. Balance Flags

Updated per BD-003 approval:

### CURRENT

```python
is_null = balance < Decimal("500")   # True when nearly exhausted (or zero-floored)
is_expired = expiry_date < today
# No negative balance flag
```

### APPROVED (post-BD-003 — pending implementation)

```python
is_negative_balance = balance < Decimal("0")    # NEW — balance below zero
is_null = Decimal("0") <= balance < Decimal("500")  # Only relevant when balance >= 0
is_expired = expiry_date < today
```

**Dashboard impact**: A new `negative_balance_count` KPI will appear in `get_dashboard_stats()`.

---

## 5. BOE Scenario A: Direct Debit (No Allotment)

```
State 0: credit=10000, debit=0, allotment=0
  balance_cif = 10000

State 1: BOE RowDetails(cif_fc=3000, type='D') created
  debit = 3000
  balance_cif = 10000 - 3000 - 0 - 0 = 7000  ✓

State 2: BOE exceeds available (BD-003 case)
  BOE RowDetails(cif_fc=11000, type='D') created
  debit = 11000
  balance_cif = 10000 - 11000 - 0 - 0 = -1000  ← NEGATIVE (allowed per BD-003)
  is_negative_balance = True
  Alert: created, dashboard updated
```

---

## 6. BOE Scenario B: From Allotment (No Double-Deduction)

```
State 0: credit=10000, debit=0, allotment=0
  balance_cif = 10000

State 1: Allotment(cif_fc=2000) created
  allotment__bill_of_entry IS NULL → allotment = 2000
  balance_cif = 10000 - 0 - 2000 - 0 = 8000

State 2: BOE created, linked to allotment; RowDetails(cif_fc=2000)
  allotment exits formula (bill_of_entry IS NOT NULL) → allotment = 0
  debit += 2000
  balance_cif = 10000 - 2000 - 0 - 0 = 8000  ← UNCHANGED (no double-deduction)

State 2b (BD-003 case — BOE > allotment):
  BOE RowDetails(cif_fc=2500) while allotment was 2000
  allotment = 0 (exits), debit = 2500
  balance_cif = 10000 - 2500 - 0 - 0 = 7500  ← 500 more than reserved
  Not blocked, not flagged (still positive)
```

---

## 7. Allotment Validation (BD-001 — pending implementation)

### CURRENT (insufficient)

Only checks against `LicenseItemPlan` (optional). If no plan row exists, there is NO validation.

### APPROVED (pending implementation)

**Two new guards** added inside `create_allotment()`:

**Guard 1 — Item-level quantity** (per item in allotment):
```python
item = LicenseImportItemsModel.objects.select_for_update().get(pk=item_id)
if qty_requested > item.available_quantity:
    raise ValidationError(f"Requested qty {qty} exceeds available {item.available_quantity}")
```

**Guard 2 — License-level CIF** (total for all items):
```python
balance = LicenseBalance.objects.select_for_update().get(license_id=license_id)
total_cif = sum(item['cif_fc'] for item in items_data)
if total_cif > balance.balance_cif:
    raise ValidationError(f"Allotment CIF {total_cif} exceeds available balance {balance.balance_cif}")
```

Both use `select_for_update()` to prevent concurrent over-allotment.

---

## 8. Balance Recompute Triggers

| Event | Trigger Code | Mechanism |
|---|---|---|
| Allotment created | `allotment_service.create_allotment()` | `transaction.on_commit(_dispatch(item_ids))` |
| Allotment updated | `allotment_service.update_allotment()` | Same |
| Allotment deleted | `allotment_service.delete_allotment()` | Same |
| BOE RowDetails saved | `post_save` signal on `RowDetails` | `_dispatch_balance_recompute(license_id)` |
| BOE RowDetails deleted | `post_delete` signal on `RowDetails` | Same |
| Manual recompute | `POST /api/v1/licenses/{id}/recompute_balance/` | Direct Celery dispatch |

---

## 9. Concurrency Protection (unchanged)

All these `select_for_update()` guards remain:
- `recompute_license_balance`: locks `LicenseDetailsModel` row
- `_update_item_level_balances`: locks all `LicenseImportItemsModel` rows for the license
- `_validate_plan_availability`: locks `LicenseItemPlan` row (NEW: also locks `LicenseBalance` and `LicenseImportItemsModel`)

---

## 10. Related Documents

- `docs/business-decisions.md` — BD-001, BD-003 approvals
- `docs/business-rules/planning-rules.md` — LicenseItemPlan lifecycle
- `docs/business-rules/business-rule-index.md` — LIC-002, LIC-003 (updated)
- `docs/playbooks/balance-module-playbook.md` — Change checklist
- `docs/improvements/improvement-register.md` — BLV-001, BLV-005 (now resolved)
