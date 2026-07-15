# License Balance Calculations — Complete Reference

> **Source of truth** — generated from actual implementation in `balance_service.py`.  
> Last updated: 2026-07-15 (feature/V1, commit 362cc9ac).

---

## 1. Overview

The license balance system tracks how much of a license's authorised import value (CIF) has been consumed. This drives:
- Alerts: `is_null` flag when balance < $500; `is_expired` when past expiry date
- Validation: prevents allotments that exceed available plan
- Dashboard: KPI statistics, utilisation charts
- Reports: balance report, ledger report

The system uses **two levels of balance**:
1. **License-level**: `LicenseBalance.balance_cif` — remaining CIF in foreign currency
2. **Item-level**: `LicenseImportItemsModel.available_quantity` — remaining quantity per import item

---

## 2. License-Level Balance Formula

**Source**: `balance_service.recompute_license_balance(license_id)`  
**File**: `backend/apps/license/services/balance_service.py`

```
balance_cif = max(0, credit − debit − allotment − trade)
```

Quantized to 2 decimal places using `ROUND_DOWN`.

### 2.1 Credit Component

```python
# _compute_credit(license_id)
SUM(LicenseExportItemModel.cif_fc WHERE license_id = <id>)
```

- **Table**: `license_licenseexportitemmodel`
- **Field**: `cif_fc` (Decimal 15,2)
- **Meaning**: Total CIF in foreign currency authorised on the license
- **Null safety**: Returns `Decimal("0")` if no export items

### 2.2 Debit Component

```python
# _compute_debit(license_id)
SUM(RowDetails.cif_fc WHERE
    sr_number__license_id = <id>
    AND transaction_type = 'D'  # Note: 'D' not 'DEBIT'
    AND bill_of_entry__license_trades__isnull = True
)
```

- **Table**: `bill_of_entry_rowdetails`
- **Path**: `RowDetails → sr_number (LicenseImportItemsModel) → license_id`
- **Filter 1**: `transaction_type = 'D'` — only debit rows (not credit)
- **Filter 2**: `bill_of_entry__license_trades__isnull = True` — excludes BOEs linked to trade transactions (to avoid double-counting when the trade module also deducts)
- **Null safety**: Returns `Decimal("0")` if no debit rows

> ⚠️ `transaction_type` in the DB uses single-char 'D' for debit and 'C' for credit, matching `TYPE_CHOICES = (("C", "Credit"), ("D", "Debit"))` in boe/models.py.

### 2.3 Allotment Component

```python
# _compute_allotment(license_id)
SUM(AllotmentItems.cif_fc WHERE
    item__license_id = <id>
    AND allotment__bill_of_entry__isnull = True
)
```

- **Table**: `allotment_allotmentitems`
- **Path**: `AllotmentItems → item (LicenseImportItemsModel) → license_id`
- **Filter**: `allotment__bill_of_entry__isnull = True` — only **pending** allotments not yet converted to a BOE
- **Meaning**: CIF reserved but not yet physically imported
- **When an allotment is linked to a BOE** via `BillOfEntryModel.allotment` (M2M), it exits this component and the corresponding RowDetails enter the debit component instead

### 2.4 Trade Component

```python
# _compute_trade(license_id)
SUM(LicenseTradeLine.cif_fc WHERE
    sr_number__license_id = <id>
    AND trade__direction = 'SALE'
)
```

- **Table**: `trade_licensetradelline`
- **Path**: `LicenseTradeLine → sr_number (LicenseImportItemsModel) → license_id`
- **Filter**: `direction = 'SALE'` — only outgoing trades reduce balance
- **Meaning**: CIF consumed by trade sales (separate from BOE debits)

---

## 3. Item-Level Balance Formula

**Source**: `balance_service._update_item_level_balances(license_id)`  
**Called**: Inside `recompute_license_balance()` in the same `transaction.atomic()` block.

For each `LicenseImportItemsModel` row belonging to the license:

```
debited_quantity  = SUM(RowDetails.qty  WHERE sr_number_id = <item_id> AND transaction_type = 'D')
debited_value     = SUM(RowDetails.cif_fc WHERE same)

allotted_quantity = SUM(AllotmentItems.qty   WHERE item_id = <item_id> AND allotment.bill_of_entry IS NULL AND allotment.type = 'AT')
allotted_value    = SUM(AllotmentItems.cif_fc WHERE same)

available_quantity = max(0, item.quantity − debited_quantity − allotted_quantity)
```

All values quantized: `available_quantity` to 3dp, values to 2dp, using `ROUND_DOWN`.

**Implementation**: Uses two bulk aggregation queries (one for debit_map, one for allot_map) then a single `bulk_update()` for changed items. This is O(1) queries regardless of number of items.

---

## 4. Balance Recompute Execution

```
transaction.atomic()
  ├── select_for_update() on LicenseDetailsModel (prevents concurrent race)
  ├── _compute_credit()
  ├── _compute_debit()
  ├── _compute_allotment()
  ├── _compute_trade()
  ├── balance = max(0, credit - debit - allotment - trade)
  ├── LicenseBalance.update_or_create(balance_cif=balance, ledger_date=today)
  ├── LicenseFlags.update_or_create(is_null=balance<500, is_expired=expiry<today)
  └── _update_item_level_balances() — updates all item-level fields
```

**Celery Task**: `recompute_license_balance_task(license_id)` with `acks_late=True, reject_on_worker_lost=True, max_retries=3`.

---

## 5. Balance Recompute Triggers

| Event | Trigger Code | Mechanism |
|---|---|---|
| Allotment created | `allotment_service.create_allotment()` | `transaction.on_commit(_dispatch(item_ids))` |
| Allotment updated | `allotment_service.update_allotment()` | `transaction.on_commit(_dispatch(item_ids))` |
| Allotment deleted | `allotment_service.delete_allotment()` | `transaction.on_commit(_dispatch(item_ids))` |
| BOE RowDetails saved | `post_save` signal on `RowDetails` | `transaction.on_commit(_dispatch_balance_recompute(license_id))` |
| BOE RowDetails deleted | `post_delete` signal on `RowDetails` | `transaction.on_commit(_dispatch_balance_recompute(license_id))` |
| Manual recompute | `POST /api/v1/licenses/{id}/recompute_balance/` | Direct Celery dispatch |
| Import item CRUD | `license_service.create/update/delete_import_item()` | Celery dispatch |

> **Note**: `_dispatch` in allotment_service resolves license_ids from item_ids via `LicenseImportItemsModel.objects.filter(pk__in=item_ids).values_list("license_id")` — this fixes a historical bug where import item IDs were incorrectly passed as license IDs.

---

## 6. BOE Scenario A: Direct Debit (No Allotment)

**Scenario**: User creates a BOE directly without first creating an allotment.

```
State 0: credit=10000, debit=0, allotment=0
  balance_cif = 10000 - 0 - 0 = 10000

State 1: BOE RowDetails created (cif_fc=3000)
  allotment unchanged (no allotment was created)
  debit += 3000
  balance_cif = 10000 - 3000 - 0 = 7000 ✓

State 2: BOE RowDetails deleted
  debit -= 3000
  balance_cif = 10000 - 0 - 0 = 10000 ✓ (restored)
```

**Item-level impact**: `available_quantity` decreases by `RowDetails.qty`.

---

## 7. BOE Scenario B: From Allotment

**Scenario**: User first creates an Allotment (reserving balance), then creates a BOE linked to that allotment.

```
State 0: credit=10000, debit=0, allotment=0
  balance_cif = 10000

State 1: Allotment created (cif_fc=3000, no BOE link yet)
  allotment__bill_of_entry IS NULL → allotment += 3000
  LicenseItemPlan.planned_quantity -= allot_qty (planning decremented)
  balance_cif = 10000 - 0 - 3000 = 7000

State 2: BOE created, allotment linked via boe.allotment.set([allotment])
  allotment__bill_of_entry IS NOT NULL → allotment drops OUT of component → allotment = 0
  RowDetails created (cif_fc=3000) → debit += 3000
  balance_cif = 10000 - 3000 - 0 = 7000  ✓ (same!)

  NET CHANGE from State 1 → State 2: ZERO (the reservation became a real debit)

State 3: BOE deleted
  RowDetails removed → debit -= 3000
  BOE-allotment link removed → allotment IS NULL again → allotment += 3000
  balance_cif = 10000 - 0 - 3000 = 7000  ✓ (back to reservation state)

State 4: Allotment deleted
  allotment drops out → allotment = 0
  LicenseItemPlan.planned_quantity += allot_qty (planning restored)
  balance_cif = 10000 - 0 - 0 = 10000  ✓ (fully restored)
```

---

## 8. Mathematical Proof: No Double-Deduction

The formula prevents double-deduction by design:

| State | Allotment component | Debit component | Total deducted |
|---|---|---|---|
| No allotment, no BOE | 0 | 0 | 0 |
| Allotment created | +A | 0 | A |
| BOE from allotment created | 0 (allotment exits) | +B | B |
| If A == B (reservation = actual): | 0 | B | B (= A) |

The allotment component and the BOE debit are **mutually exclusive for the same value**:
- Allotment counts only when `allotment.bill_of_entry IS NULL`
- When a BOE is linked: allotment exits the formula, BOE enters

---

## 9. Concurrency Protection

### 9.1 License-level (recompute_license_balance)
```python
LicenseDetailsModel.objects.select_for_update().get(pk=license_id)
```
All reads and writes happen inside `transaction.atomic()` with a row lock. Two concurrent recomputes cannot race.

### 9.2 Item-level (allotment_service)
```python
LicenseItemPlan.objects.select_for_update().filter(import_item_id=...)
```
Planning validation and adjustment both use `select_for_update()` inside `transaction.atomic()`. Prevents two concurrent allotments from each reading the same plan value and both thinking they fit within the limit.

### 9.3 Celery task delivery
All recompute tasks use `acks_late=True, reject_on_worker_lost=True`. If a worker crashes mid-execution, the message is re-queued (not lost).

### 9.4 on_commit pattern
Balance recompute is dispatched via `transaction.on_commit()` — the Celery task is only enqueued after the DB transaction commits. This prevents a task from seeing inconsistent data.

---

## 10. Planning Formula

When an allotment is created with `qty=Q, cif_fc=C` against import item `X`:

```
LicenseItemPlan.planned_quantity -= Q   (via F() expression, atomic)
LicenseItemPlan.planned_cif_fc   -= C   (via F() expression, atomic)
```

When an allotment is deleted:
```
LicenseItemPlan.planned_quantity += Q   (exact reversal)
LicenseItemPlan.planned_cif_fc   += C   (exact reversal)
```

**Guard**: Before creating an allotment, `_validate_plan_availability` checks:
```
if Q > plan.planned_quantity: raise ValidationError
if C > plan.planned_cif_fc:   raise ValidationError
```

If no `LicenseItemPlan` row exists for the import item: no restriction (backward compatible).

---

## 11. Example Calculation

**License**: DFIA/2024/001  
**Export item**: 10,000 kg of engineered goods at $50,000 CIF

```
credit = 50,000.00 USD

// Allotment 1: 10,000 kg, $5,000 CIF
allotment = 5,000.00

balance = 50,000 - 0 - 5,000 - 0 = 45,000.00 USD
is_null = False (45,000 >= 500)

// BOE raised, allotment linked:
allotment = 0  (exits because bill_of_entry IS NOT NULL)
debit     = 4,950.00  (actual CIF slightly different from allotment)

balance = 50,000 - 4,950 - 0 - 0 = 45,050.00 USD  (allotment was $5,000 but actual debit was $4,950)
```

---

## 12. NULL Threshold & Expiry Logic

```python
_NULL_THRESHOLD = Decimal("500")

is_null    = balance_cif < 500           # True when nearly exhausted
is_expired = license_expiry_date < today  # True when past expiry
```

Both flags are written in the same atomic transaction as `balance_cif`. The dashboard counts licenses by these flags for its KPI stats.

---

## 13. Edge Cases

| Case | Behavior |
|---|---|
| No export items | `credit = 0`, balance = 0 |
| No debit/allotment | `balance = credit` (full authorisation unused) |
| Debit > credit | `balance = max(0, negative) = 0` |
| Concurrent allotments | `select_for_update` on LicenseItemPlan prevents both from succeeding if combined > plan |
| License deleted mid-task | `LicenseDetailsModel.DoesNotExist` caught, task exits silently with WARNING log |
| AllotmentItems with null item | Excluded via `.exclude(item_id__isnull=True)` before dispatch |
| RowDetails with null sr_number | Signal handler checks `if sr is None: return` |
| Zero-value allotment | Valid, passes validation, no plan impact (0 − 0 = 0) |

---

## 14. Related Files

| File | Role |
|---|---|
| `backend/apps/license/services/balance_service.py` | **THE** canonical balance calculation |
| `backend/apps/allotment/services/allotment_service.py` | _dispatch fix, _adjust_plan, _validate_plan |
| `backend/apps/bill_of_entry/models.py` | update_stock / delete_stock signals |
| `backend/apps/license/tasks.py` | recompute_license_balance_task |
| `backend/tests/balance/test_balance_system.py` | 21 business rule tests |
| `backend/tests/integration/test_license_workflows.py` | Integration tests |
