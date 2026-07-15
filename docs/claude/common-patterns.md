# Common Development Patterns — Claude Context

> **Recurring patterns used throughout the codebase.**

---

## 1. Service Layer Pattern

```
View → validates HTTP request → calls service
Service → transaction.atomic() → ORM writes → on_commit dispatch
```

**Never** access ORM from views. **Never** return HTTP Response from services.

```python
# views.py (correct)
def post(self, request):
    serializer = MySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    obj = my_service.create_thing(serializer.validated_data, request.user)
    return Response(EnvelopeMixin.wrap(data=OutSerializer(obj).data))

# service.py (correct)
def create_thing(data: dict, user) -> MyModel:
    with transaction.atomic():
        obj = MyModel(**data, created_by=user)
        obj.save()
        transaction.on_commit(lambda: some_task.delay(obj.pk))
    return obj
```

---

## 2. Envelope Response Pattern

```python
# All list responses (via StandardPagination) automatically:
{"success": true, "data": [...], "pagination": {...}}

# All detail/action responses (manual):
return Response(EnvelopeMixin.wrap(data=serializer.data))
return Response(EnvelopeMixin.wrap(data=data, message="Done."))
return Response(EnvelopeMixin.wrap(message="Deleted."), status=204)
```

---

## 3. Lazy Import Pattern (avoiding circular imports)

```python
# In service files, import cross-app models inside functions:
def _compute_debit(license_id):
    from apps.bill_of_entry.models import RowDetails   # lazy
    return RowDetails.objects.filter(...)...

# In on_commit callbacks, import tasks lazily:
def _task():
    from apps.license.tasks import recompute_license_balance_task  # lazy
    recompute_license_balance_task.delay(license_id)
```

---

## 4. select_for_update Pattern

```python
# Always inside transaction.atomic():
with transaction.atomic():
    obj = MyModel.objects.select_for_update().get(pk=id)
    obj.field = new_value
    obj.save()
```

Used for: balance recompute (LicenseDetailsModel lock), plan validation (LicenseItemPlan lock), invoice number generation (LicenseTrade lock).

---

## 5. update_or_create Pattern (B4 fix)

```python
# Use update_or_create instead of filter().update() — the latter is no-op on missing row
LicenseBalance.objects.update_or_create(
    license_id=license_id,
    defaults={"balance_cif": balance, "ledger_date": today},
)
```

---

## 6. on_commit Dispatch Pattern

```python
# Dispatch Celery tasks only AFTER transaction commits:
with transaction.atomic():
    # ... do database work ...
    transaction.on_commit(lambda: some_task.delay(pk))
    # NOT: some_task.delay(pk) ← would dispatch even if transaction rolls back
```

---

## 7. bulk_update Pattern (item-level balance)

```python
# For N items, collect changes then bulk_update (one query, not N):
to_update = []
for item in items:
    if item.field != new_value:
        item.field = new_value
        to_update.append(item)

if to_update:
    MyModel.objects.bulk_update(to_update, ["field"])
```

---

## 8. F() Expression Pattern (atomic arithmetic)

```python
# Atomic increment/decrement using F() — avoids read-modify-write races:
plan_qs.update(
    planned_quantity=models.F("planned_quantity") + qty_delta,
    planned_cif_fc=models.F("planned_cif_fc") + cif_fc_delta,
)
# This generates: UPDATE ... SET planned_quantity = planned_quantity + qty_delta
```

---

## 9. Decimal Precision Pattern

```python
_TWO_PLACES = Decimal("0.01")
_THREE_PLACES = Decimal("0.001")

# Quantize to 2dp (CIF values):
balance = raw_balance.quantize(_TWO_PLACES, rounding=ROUND_DOWN)

# Quantize to 3dp (quantities):
avail_qty = avail_qty.quantize(_THREE_PLACES, rounding=ROUND_DOWN)

# WRONG - use Decimal(str()), not float:
pct = Decimal(str(self.pct))  # ✓
pct = q2(self.pct)            # ✗ for division — loses precision
```

---

## 10. CeleryTaskTracker Pattern (pre-generated task ID)

```python
# Create tracker BEFORE apply_async (prevents race condition):
task_id = str(uuid.uuid4())
_make_tracker(task_name="my_task", task_id=task_id, args_payload={...})
result = my_task.apply_async(kwargs={...}, task_id=task_id)
# If worker picks up task before tracker INSERT commits → race
# Fixed by pre-generating and inserting first
```

---

## 11. IDOR Prevention Pattern (BOE rows)

```python
# Wrong — IDOR: any BOE_MANAGER can modify any row by ID:
row = RowDetails.objects.get(pk=row_id)

# Correct — scope to parent BOE:
row = RowDetails.objects.get(pk=row_id, bill_of_entry_id=boe_id)
# boe_id comes from URL: /bill-of-entries/{boe_id}/rows/{row_id}/
```

---

## 12. Frontend: Mutation with Cache Invalidation

```typescript
const mutation = useMutation({
  mutationFn: (data) => apiClient.post(ENDPOINTS.LICENSES.CREATE, data),
  onSuccess: (_data, _vars, _ctx) => {
    queryClient.invalidateQueries({ queryKey: ['licenses'] })          // list
  },
  onError: (err) => {
    toast.error(normaliseApiErrorString(err))
  },
})
```

For update mutations, also invalidate detail:
```typescript
onSuccess: (_data, { id }) => {
  queryClient.invalidateQueries({ queryKey: ['licenses'] })
  queryClient.invalidateQueries({ queryKey: ['licenses', id] })
}
```

---

## 13. Frontend: Error Normalization

```typescript
// shared/utils/errors.ts: normaliseApiErrorString(err)
// Returns a human-readable string from any axios error
// Handles: {errors: [{field, message}]}, {message: "..."}, network errors
```

Use this everywhere. Never manually extract error.response.data.

---

## 14. Types for API Responses

```typescript
// List response (unwrapped by interceptor):
{ data: T[], pagination: { count, next, previous, page, page_size, total_pages } }

// Detail response (unwrapped):
T  // the object directly

// Paginated hook pattern:
const { data } = useQuery({
  queryFn: async () => {
    const res = await apiClient.get<APIPaginatedData<License>>(ENDPOINTS.LICENSES.LIST)
    return res.data  // already unwrapped: { data: License[], pagination: {...} }
  }
})
```
