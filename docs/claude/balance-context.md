# Balance & Planning — Claude Context

> **Read this before ANY change to balance, allotment, or BOE code.**  
> This document is optimized for AI-assisted development — every critical detail in one place.

---

## What This System Does

Tracks how much of a license's **authorised CIF (Cost Insurance Freight)** has been consumed through imports. Three modes of consumption:

1. **Allotment** — reservation before physical import (reduces available balance prospectively)
2. **BOE Debit** — actual import recorded (reduces balance definitively)
3. **Trade Sale** — license sold to another party (reduces balance)

---

## THE Formula (never change without understanding this)

```python
# balance_service.py: recompute_license_balance(license_id)

balance_cif = max(0, credit - debit - allotment - trade)

credit    = SUM(LicenseExportItemModel.cif_fc   WHERE license_id=X)
debit     = SUM(RowDetails.cif_fc               WHERE sr_number__license_id=X
                                                  AND transaction_type='D'
                                                  AND bill_of_entry__license_trades__isnull=True)
allotment = SUM(AllotmentItems.cif_fc            WHERE item__license_id=X
                                                  AND allotment__bill_of_entry__isnull=True)
trade     = SUM(LicenseTradeLine.cif_fc          WHERE sr_number__license_id=X
                                                  AND trade__direction='SALE')
```

**CRITICAL**: The `allotment` component only counts allotments WHERE `allotment.bill_of_entry IS NULL`. When a BOE is linked to an allotment via `BillOfEntryModel.allotment` (M2M), the allotment drops OUT of the allotment component and the corresponding RowDetails enter the debit component. This prevents double-counting.

---

## Files to Read Before Changing

| Change type | Must read |
|---|---|
| Any balance logic | `backend/apps/license/services/balance_service.py` |
| Allotment CRUD | `backend/apps/allotment/services/allotment_service.py` |
| BOE create/delete | `backend/apps/bill_of_entry/models.py` (signals section) |
| Balance display | `frontend/src/features/licenses/components/LicenseBalancePanel.tsx` |
| Item balance display | `frontend/src/features/licenses/components/LicenseImportItems.tsx` |
| Planning | `backend/apps/license/models/license.py` (LicenseItemPlan) |

---

## Critical Bugs Fixed (do not revert)

### Bug 1: `_dispatch` was passing wrong IDs
**File**: `allotment_service.py`  
**Old code** (WRONG): `recompute_license_balance_task.delay(iid)` where `iid` was `LicenseImportItemsModel.id`  
**New code** (CORRECT): Resolves `license_id` via `LicenseImportItemsModel.objects.filter(pk__in=item_ids).values_list("license_id")`  
**Symptom if reverted**: Balance never recomputes after allotment operations. Silent failure.

### Bug 2: BOE signals called non-existent legacy module
**File**: `bill_of_entry/models.py`  
**Old code** (WRONG): `from apps.core.scripts.calculate_balance import update_balance_values` → ImportError silently caught  
**New code** (CORRECT): `_dispatch_balance_recompute(license_id)` dispatches `recompute_license_balance_task.delay(license_id)`  
**Symptom if reverted**: Balance never recomputes after BOE row create/delete. Silent failure.

### Bug 3: _safe_get_model was silently zeroing balances
**File**: `balance_service.py`  
**Old code** (WRONG): `_safe_get_model(app_label, model_name)` returned `None` and logged at DEBUG on LookupError  
**New code** (CORRECT): Direct lazy imports in each `_compute_*` function; any ImportError surfaces loudly  
**Symptom if reverted**: A typo in an app_label/model_name string would silently return `Decimal(0)` for entire balance components.

---

## Balance Recompute Is ALWAYS Async

**Never** call `recompute_license_balance()` synchronously from a request handler.  
Always use: `recompute_license_balance_task.delay(license_id)`  
The task dispatches via `transaction.on_commit()` so it only fires after the DB transaction commits.

---

## Planning Rules (LicenseItemPlan)

- **One plan per import item** (enforced by API logic; not by DB unique constraint — TODO)
- If no plan row exists for an import item: allotment is **unrestricted** (backward compatible)
- Create allotment → `_adjust_plan(qty_delta=-allot_qty, ...)` decrements plan
- Delete allotment → `_adjust_plan(qty_delta=+allot_qty, ...)` restores plan
- Before create: `_validate_plan_availability()` with `select_for_update()` prevents over-allotment
- `update_allotment()` does NOT adjust the plan (only header fields change)

---

## Concurrency Guards (NEVER remove)

```python
# In recompute_license_balance:
LicenseDetailsModel.objects.select_for_update().get(pk=license_id)

# In _update_item_level_balances:
LicenseImportItemsModel.objects.select_for_update().filter(license_id=license_id)

# In _validate_plan_availability:
LicenseItemPlan.objects.select_for_update().filter(import_item_id=...)

# In _adjust_plan:
LicenseItemPlan.objects.select_for_update().filter(import_item_id=...)

# In get_next_invoice_number (trade):
LicenseTrade.objects.select_for_update().filter(...)
```

All of these are inside `transaction.atomic()`. Never move these outside the transaction.

---

## Item-Level vs License-Level Fields

| Field | Level | Table | Updated by |
|---|---|---|---|
| `balance_cif` | License | `license_licensebalance` | `recompute_license_balance()` |
| `available_quantity` | Item | `license_licenseimportitemsmodel` | `_update_item_level_balances()` |
| `debited_quantity` | Item | same | same |
| `allotted_quantity` | Item | same | same |
| `planned_quantity` | Item | `license_licenseitemplan` | `_adjust_plan()` in allotment_service |

Item-level fields are updated in the **same transaction** as the license-level balance. They are always consistent at commit time.

---

## Test Files for Balance

| File | What it tests |
|---|---|
| `backend/tests/balance/test_balance_system.py` | 21 unit tests: all formulas, scenarios, planning |
| `backend/tests/integration/test_license_workflows.py` | ~50 integration tests: BR-01 through BR-08 |
| `backend/tests/allotment/test_allotment.py` | Dispatch correctness, type choices |

---

## Common Pitfalls

1. **Never compare `transaction_type` to 'DEBIT'** — the DB value is single-char `'D'` (`TYPE_CHOICES = (("C","Credit"),("D","Debit"))`)
2. **Balance is stale after BOE creation** until Celery task runs — UI may briefly show old value
3. **`allotment__bill_of_entry__isnull=True`** traverses M2M reverse relation — if boe.allotment.set() is not called, allotment stays in the allotment component even after BOE creation
4. **Don't use `q2()` for `pct`/`rate_pct`** before dividing by 100 — use `Decimal(str(value))` instead
