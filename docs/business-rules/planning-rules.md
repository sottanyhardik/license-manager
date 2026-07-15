# License Planning Rules

> **Source of truth** — generated from actual implementation.  
> Last updated: 2026-07-15 (feature/V1).

---

## 1. What Is Planning?

Planning is a **forward reservation system** that limits how much of an import item's authorised quantity can be allotted. Before allotting, an operator creates a `LicenseItemPlan` row that sets the maximum allowed allotment for that import item.

**Purpose**: Prevents uncoordinated over-allotment when multiple operators work concurrently. Also provides visibility into planned vs. actual usage.

**Key property**: Planning is **optional** — if no `LicenseItemPlan` row exists for an import item, allotments are unrestricted. This ensures backward compatibility with legacy data that predates the planning module.

---

## 2. LicenseItemPlan Model

**Table**: `license_licenseitemplan`  
**File**: `backend/apps/license/models/license.py`

| Field | Type | Description |
|---|---|---|
| `import_item` | FK → LicenseImportItemsModel | The import item being planned (CASCADE delete) |
| `license` | FK → LicenseDetailsModel | Parent license (CASCADE delete) |
| `item_name` | FK → core.ItemNameModel (nullable) | Optional item name override |
| `planned_quantity` | Decimal(15,3) | **Available quantity for allotment** — decremented when allotments are created |
| `unit_price` | Decimal(15,2) | Unit price for CIF calculation |
| `planned_cif_fc` | Decimal(15,2) | **Available CIF FC for allotment** — decremented when allotments are created |
| `planned_cif_inr` | Decimal(15,2) | Available CIF INR |
| `note` | CharField(500) | Planning notes |

The model inherits from `AuditModel` (created_at, updated_at, created_by, modified_by).

---

## 3. Planning Lifecycle

```
1. Create LicenseItemPlan (via POST /api/v1/licenses/{id}/item-plans/)
   → planned_quantity = 500 KG, planned_cif_fc = 5000.00

2. Create Allotment (qty=100, cif_fc=1000)
   → _validate_plan_availability: 100 <= 500 ✓, 1000 <= 5000 ✓
   → _adjust_plan(delta=-100, delta_cif=-1000)
   → planned_quantity = 400 KG, planned_cif_fc = 4000.00

3. Create another Allotment (qty=450, cif_fc=4500)
   → _validate_plan_availability: 450 > 400 ✗  → ValidationError raised!

4. Delete Allotment from step 2 (qty=100, cif_fc=1000)
   → _adjust_plan(delta=+100, delta_cif=+1000)
   → planned_quantity = 500 KG, planned_cif_fc = 5000.00  (fully restored)
```

---

## 4. Over-Allotment Prevention

**Function**: `_validate_plan_availability(import_item_id, qty_requested, cif_fc_requested)`  
**File**: `backend/apps/allotment/services/allotment_service.py`  
**Called from**: `create_allotment()` inside `transaction.atomic()`

```python
plan = LicenseItemPlan.objects.select_for_update().filter(import_item_id=...).first()

if plan is None:
    return   # No plan — no restriction

if qty_requested > plan.planned_quantity:
    raise ValidationError(...)

if cif_fc_requested > plan.planned_cif_fc:
    raise ValidationError(...)
```

**Concurrency safety**: `select_for_update()` acquires a row lock on the plan row. Two concurrent allotments targeting the same import item cannot both pass validation simultaneously — the second waits for the first transaction to commit before running its check.

---

## 5. Plan Adjustment

**Function**: `_adjust_plan(import_item_id, qty_delta, cif_fc_delta, cif_inr_delta)`  
**File**: `backend/apps/allotment/services/allotment_service.py`

Uses `F()` expressions for atomic database arithmetic:
```python
plan_qs.update(
    planned_quantity=models.F("planned_quantity") + qty_delta,
    planned_cif_fc=models.F("planned_cif_fc") + cif_fc_delta,
    planned_cif_inr=models.F("planned_cif_inr") + cif_inr_delta,
)
```

- **On allotment create**: `qty_delta < 0`, `cif_fc_delta < 0` (consume plan)
- **On allotment delete**: `qty_delta > 0`, `cif_fc_delta > 0` (restore plan)
- **If no plan exists**: no-op (function returns early)

---

## 6. update_allotment and Planning

`update_allotment()` only updates AllotmentModel header fields, NOT AllotmentItems. Item-level edits go through separate AllotmentItems endpoints. Therefore, `update_allotment()` does NOT call `_adjust_plan()`.

If an operator needs to change an allotment's qty or cif, they should:
1. Delete the allotment → plan is restored
2. Create a new allotment with updated values → plan is decremented again

---

## 7. API

**Base**: `POST /api/v1/licenses/{license_pk}/item-plans/`  
**Permission**: `LicensePermission` (write = LICENSE_MANAGER role)

| Method | URL | Description |
|---|---|---|
| GET | `/licenses/{id}/item-plans/` | List plans for a license |
| POST | `/licenses/{id}/item-plans/` | Create a plan for an import item |
| GET | `/licenses/{id}/item-plans/{pk}/` | Retrieve specific plan |
| PATCH | `/licenses/{id}/item-plans/{pk}/` | Update planned values |
| DELETE | `/licenses/{id}/item-plans/{pk}/` | Delete plan (makes item unrestricted) |

**Request body** (POST):
```json
{
  "import_item": 42,
  "planned_quantity": "500.000",
  "planned_cif_fc": "5000.00",
  "planned_cif_inr": "415000.00",
  "note": "FY 2025-26 planning"
}
```

---

## 8. Frontend Display

The `LicenseImportItems` table includes a **Planned** column (blue text) between Total Qty and Allotted:

| Sr | HS Code | Description | Total Qty | **Planned** | Allotted | Debited | Available | CIF FC |
|---|---|---|---|---|---|---|---|---|
| 1 | 84071000 | Engine parts | 1000.000 | **400.000** | 100.000 | 200.000 | 700.000 | 50000.00 |

- Displays `planned_quantity` from `LicenseItemPlan` if a plan exists
- Shows `—` if no plan row exists for the item (unrestricted)

The value comes from `ImportItemSerializer.get_planned_quantity()` which queries `LicenseItemPlan.objects.filter(import_item_id=obj.pk).first()`.

---

## 9. Known Limitations

| Issue | Details |
|---|---|
| N+1 in serializer | `get_planned_quantity` makes one DB query per import item during serialization. Acceptable for detail view (typically 2-20 items) but would need optimization for bulk list views. |
| No edit-delta for item updates | `update_allotment` doesn't handle item qty changes — operators must delete + recreate |
| Single plan per item | The API/model allows multiple LicenseItemPlan rows per item; the serializer reads only the first. Business logic should enforce one plan per item. |
