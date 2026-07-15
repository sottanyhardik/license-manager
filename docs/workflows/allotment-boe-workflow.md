# Allotment → BOE Workflow

> **Business workflows for Allotment and Bill of Entry modules.**

---

## Workflow 1: Create Allotment (AT type)

### Preconditions
- License exists with at least one import item
- Company exists in masters
- User has `ALLOTMENT_MANAGER` role
- If planning enabled: `LicenseItemPlan` row exists for the import item

### User Steps
1. Navigate to `/allotments` → "New Allotment"
2. Select company, allotment type (AT=Allotment, TR=Transfer)
3. Set required_quantity, exchange_rate, item_name, port
4. Add line items: select import item (SR), enter qty and cif_fc
5. Review totals → "Create"

### Backend Flow
```
POST /api/v1/allotments/
  → AllotmentPermission (ALLOTMENT_MANAGER required)
  → AllotmentSerializer.is_valid()
    → validates company FK, port FK
    → validates AllotmentItems structure
  → allotment_service.create_allotment(data, user)
    → transaction.atomic():
      1. For each item: _validate_plan_availability(item_id, qty, cif_fc)
         → select_for_update() on LicenseItemPlan
         → ValidationError if qty > plan.planned_quantity
      2. AllotmentModel.save()
      3. For each item:
         → AllotmentItems.save()
         → _adjust_plan(item_id, qty_delta=-qty, cif_fc_delta=-cif_fc)
      4. on_commit: _dispatch(item_ids)
         → resolves license_ids from item_ids
         → recompute_license_balance_task.delay(license_id) per license
```

### Database Changes
| Table | Change |
|---|---|
| `allotment_allotmentmodel` | INSERT |
| `allotment_allotmentitems` | INSERT per line item |
| `license_licenseitemplan` | UPDATE: planned_qty -= allot_qty (per item) |
| `license_licensebalance` | UPSERT (via Celery, async) |
| `license_licenseimportitemsmodel` | UPDATE: allotted_qty += allot_qty (via Celery) |

### Side Effects
1. `LicenseItemPlan.planned_quantity` decremented atomically
2. `LicenseBalance.balance_cif` decreases (allotment now counted in formula)
3. `LicenseImportItemsModel.allotted_quantity` increases
4. Dashboard "total_allotments" count increments

### Failure & Rollback
| Failure | Behavior |
|---|---|
| qty > planned_quantity | 400 ValidationError; no rows written (transaction rollback) |
| Company not found | 400 |
| Celery broker down | Allotment saved; balance NOT updated; logs ERROR; future manual recompute needed |

---

## Workflow 2: Delete Allotment

### Preconditions
- Allotment exists and is NOT linked to a BOE (deletion of consumed allotments has no plan to restore)
- User has `ALLOTMENT_MANAGER` role

### Backend Flow
```
DELETE /api/v1/allotments/{id}/
  → allotment_service.delete_allotment(allotment_id, user)
    → transaction.atomic():
      1. Collect plan_adjustments BEFORE delete:
         SELECT item_id, qty, cif_fc, cif_inr FROM allotment_allotmentitems
         WHERE allotment_id=X (before cascade removes them)
      2. AllotmentModel.objects.filter(pk=X).delete()
         → CASCADE deletes AllotmentItems
      3. Restore plan for each item:
         _adjust_plan(item_id, qty_delta=+qty, cif_fc_delta=+cif_fc)
      4. on_commit: _dispatch(item_ids) → recompute_license_balance_task
```

### Database Changes
| Table | Change |
|---|---|
| `allotment_allotmentmodel` | DELETE |
| `allotment_allotmentitems` | DELETE (CASCADE) |
| `license_licenseitemplan` | UPDATE: planned_qty += allot_qty (restored) |
| `license_licensebalance` | UPSERT (async): balance_cif increases |
| `license_licenseimportitemsmodel` | UPDATE (async): allotted_qty decreases |

---

## Workflow 3: Create BOE (Scenario A — No Allotment)

### Business Context
Importer receives goods and ICEGATE issues a Bill of Entry. The importer enters this directly into the system without a prior allotment.

### Preconditions
- License exists with import items
- User has `BOE_MANAGER` role
- Company and port exist in masters

### User Steps
1. Navigate to `/boe` → "New Bill of Entry"
2. Enter: BOE number, date, company, port
3. Add rows: select SR number (import item), enter qty, cif_fc, cif_inr
4. Transaction type = Debit (D)
5. Save

### Backend Flow
```
POST /api/v1/bill-of-entries/
  → BillOfEntryPermission
  → BillOfEntrySerializer.create()
    → BillOfEntryModel.save()
    → No allotment M2M set (Scenario A)
    → for each row: RowDetails.save()
      → post_save signal: update_stock(instance)
        → sr.license_id = 15
        → on_commit: recompute_license_balance_task.delay(15)
      → post_save signal: recalc_exchange_rate_on_row_save(instance)
        → on_commit: _recalculate_boe_exchange_rate(boe_id)
```

### Balance Impact
- `_compute_debit` increases by `RowDetails.cif_fc`
- `_compute_allotment` unchanged (no allotment)
- Net: `balance_cif` decreases by `RowDetails.cif_fc`

---

## Workflow 4: Create BOE (Scenario B — From Allotment)

### Business Context
Importer created an allotment (reserving balance) and now has the BOE to confirm actual import.

### Key Difference from Scenario A
- The BOE is linked to the allotment via `boe.allotment.set([allotment_obj])`
- This causes the allotment to exit `_compute_allotment()` filter
- The BOE debit enters `_compute_debit()`
- Net change: balance decreases only by the difference (usually zero if amounts match)

### Backend Flow
```
POST /api/v1/bill-of-entries/
  → BillOfEntrySerializer.create()
    → BillOfEntryModel.save()
    → boe.allotment.set(allotment_data)   ← CRITICAL: links allotment
      → AllotmentModel.is_boe = True
      → AllotmentModel.save()
    → RowDetails rows created
    → Signals fire → recompute dispatched
```

### Balance State Transition
```
Before BOE:
  allotment=1000, debit=0
  balance = credit - 0 - 1000 - 0 = credit - 1000

After BOE (from allotment, same amount):
  allotment=0 (exits filter), debit=1000
  balance = credit - 1000 - 0 - 0 = credit - 1000   (unchanged!)

If BOE amount ≠ allotment amount (e.g., BOE=900, allotment=1000):
  balance = credit - 900 - 0 - 0 = credit - 900   (100 returned to balance)
```

---

## Workflow 5: BOE Row Management

### Add Row to Existing BOE
```
POST /api/v1/bill-of-entries/{boe_id}/rows/
  → RowDetails.save()
  → post_save signal → recompute dispatch
```

### Edit Row (not frozen)
```
PATCH /api/v1/bill-of-entries/{boe_id}/rows/{row_id}/
  → boe_service.update_row_detail(row_id, data, user, boe_id)
    → RowDetails.objects.get(pk=row_id, bill_of_entry_id=boe_id)  ← IDOR prevention
    → check is_frozen → raise ValueError if True
    → RowDetailsSerializer.save()
    → post_save signal → recompute
```

### Delete Row (not frozen)
```
DELETE /api/v1/bill-of-entries/{boe_id}/rows/{row_id}/
  → boe_service.delete_row_detail(row_id, user, boe_id)
    → RowDetails.objects.get(pk=row_id, bill_of_entry_id=boe_id)  ← IDOR prevention
    → check is_frozen → raise ValueError if True
    → row.delete()
    → post_delete signal → recompute
```

---

## Workflow 6: Dispute Resolution

### When Disputes Occur
During ledger upload (`LedgerUploadView`), rows in the current BOE that are missing from the ICEGATE ledger get `is_dispute=True`.

### Resolving Single Row Dispute
```
POST /api/v1/bill-of-entries/{boe_id}/rows/{row_id}/resolve-dispute/
  Body: {license_item_id: 42}
  → boe_service.resolve_dispute_row(row_id, license_item_id, user, boe_id)
    → RowDetails.objects.get(pk=row_id, bill_of_entry_id=boe_id)
    → check is_dispute = True (else ValueError)
    → UPDATE: sr_number_id=42, is_dispute=False
```

### Resolving All Disputes on BOE
```
POST /api/v1/bill-of-entries/{boe_id}/resolve-dispute/
  → boe_service.resolve_dispute(boe)
    → RowDetails.objects.filter(bill_of_entry=boe, is_dispute=True).update(is_dispute=False)
```

---

## Rollback Scenarios

| Scenario | What happens | Recovery |
|---|---|---|
| BOE created, recompute fails | BOE rows exist, balance stale | Trigger manual recompute via `POST /licenses/{id}/recompute_balance/` |
| BOE deleted | RowDetails removed, post_delete signal fires, balance recomputed | Automatic |
| BOE allotment link removed | Allotment re-enters allotment formula, balance recomputed | Automatic on next recompute |
| Allotment deleted after BOE | Plan restored, balance recomputed (debit still counts) | Automatic |
