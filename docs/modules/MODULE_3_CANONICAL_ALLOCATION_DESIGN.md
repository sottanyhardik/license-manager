# Module 3: CanonicalAllocationService Specification

**Status:** Design Complete, 10 Forensic Findings Documented, 4 Blocking Business Decisions  
**Created:** 2026-08-10 (Module 3 consolidation workflow)  
**Audience:** Backend engineers implementing Module 3

---

## CRITICAL UPFRONT DISCOVERY

**There are TWO allocation implementations that fundamentally disagree:**

| | Production (Live) | Testing (Dead) |
|---|---|---|
| **Location** | `views_actions.py:623-876` | `allocation_service.py:23-308` |
| **Entry point** | `POST /api/allocate-items/` | Nothing (only tests) |
| **Test coverage** | 5 narrow files | **17 Module 3 scenarios** |
| **Impact** | All user requests | Zero production traffic |

**Consequence:** The 17-scenario test suite passes because it exercises code NO USER EVER TOUCHES. This is why 10 critical defects went unnoticed in production.

Example: Scenario 7 ("cross-company allocation raises error") passes against `AllocationService`, but the **live endpoint has zero company isolation checks**.

---

## 10 FORENSIC FINDINGS (F1-F10)

### F1 — Concurrent Over-Allocation (CRITICAL)

**Where:** `views_actions.py:671` locks the import item, then reads `available_quantity` at `:694`

**Problem:** Lock serializes the transaction but not the invariant. `available_quantity` is rewritten by `update_balance_values()` in a `transaction.on_commit()` hook after the lock releases.

**Attack:** Request A acquires lock, reads available=1000. Request B waits. A commits. `available_quantity` decremented to 500. B acquires lock, reads **stale** available=1000, allocates 800. Total allocated: 1800 against a 1000 pool.

**Fix:** Compute `item.available_qty` from a **live aggregate** inside the transaction (`SUM(AllotmentItems.qty)` executed NOW, not from the denormalized column).

---

### F2 — Intra-Request Over-Allocation (CRITICAL)

**Where:** `views_actions.py:733` reads `allotment.alloted_quantity` inside the per-allocation loop

**Problem:** `alloted_quantity` is a `@cached_property`. Caches on iteration 1, never invalidated.

**Attack:** Request contains 3 lines, each quantity = `required_quantity / 3`. Line 1 validates against total `0 + qty` (pass). Line 2 validates against **cached** total `0 + qty` (pass). Line 3 validates against **cached** total `0 + qty` (pass). Total allocated: `3 × (required_quantity / 3)` = `required_quantity`. But the cache never saw lines 2 and 3.

**Fix:** Use a running in-memory ledger. After each successful allocation, decrement the ledger for the next iteration.

---

### F3 — Inconsistent Response (HIGH)

**Where:** `views_actions.py:865` calls `refresh_from_db()` but doesn't clear cached properties

**Problem:** Response serializes `alloted_quantity` (stale cache), `allotted_value` (stale cache), and `balanced_quantity` (fresh, never touched in loop). Client receives contradictory numbers.

**Fix:** Re-fetch the allotment with a fresh instance (`AllotmentModel.objects.get(pk=...)`) so no cached property survives.

---

### F4 — Broken Exception Handling (HIGH)

**Where:** `views_actions.py:859-862` uses bare `except Exception` inside `@transaction.atomic()`

**Problem:** Any `DatabaseError` marks the transaction for rollback. The handler swallows it. The next iteration issues a query → `TransactionManagementError`. Django requires a **nested savepoint** per iteration to catch and continue.

**Fix:** Use `with transaction.atomic():` nested inside the loop (creates implicit savepoint). Alternatively, switch to `best_effort` mode semantics.

---

### F5 — Partial Commit Reported as Success (HIGH)

**Where:** `views_actions.py:876` returns 201 whenever `created_items` is non-empty

**Problem:** Per-item failures are collected into `errors[]` while earlier successes commit. HTTP 201 Created is a lie when half the request failed.

**Fix:** Return `201` only if ALL items succeeded. Return `400` if ANY item failed in `strict` mode. Return `207 Multi-Status` if `best_effort` mode and both lists are non-empty.

---

### F6 — No Authorization Scoping (HIGH)

**Where:** `views_actions.py:648` and `:671` use bare `.objects.get()`

**Problem:** `get_object_or_404(AllotmentModel, pk=pk)` is unscoped. `AllotmentPermission` is role-only (`BaseRolePermission` has no `has_object_permission`), and users carry no company scope. Any `ALLOTMENT_MANAGER` can allocate any licence item to any allotment.

**Same hole:** `views.py:309-330` (`destroy_allotment` uses `objects.get(pk=pk)`)

**Fix:** Scope both queries to the caller's company (once D1 defines what that means).

---

### F7 — No Lower-Bound Validation (MEDIUM)

**Where:** `views_actions.py` never validates `qty > 0` or `cif_fc > 0`

**Problem:** Coerce via `Decimal(str(...))`. `.objects.create()` does not run `MinValueValidator`. A negative `qty` passes every check and **inflates** the balance.

**Fix:** Explicitly check `qty > 0` and `cif_fc > 0` during request shape validation (Phase 0).

---

### F8 — Client-Supplied Money Not Validated (MEDIUM)

**Where:** `views_actions.py:664` accepts `cif_fc` and `cif_inr` from the request

**Problem:** Never reconciled against `qty × unit_value_per_unit` or `cif_fc × exchange_rate`.

**Fix:** Either (a) derive `cif_fc` from `qty × allotment.unit_value_per_unit` and reject the client value, or (b) validate `|cif_fc - qty × unit_price| <= tolerance` (define tolerance per D2).

---

### F9 — Plan-Line Drawdown Loses Real CIF (MEDIUM)

**Where:** `views_actions.py:844` recomputes `remaining_cif_fc = new_remaining_qty × plan_line.unit_price`

**Problem:** Discards the actual `cif_fc` allotted. Over-draw is silently clamped instead of rejected.

**Example:** Plan line has `remaining_qty=10, remaining_cif_fc=100, unit_price=10`. Allocation requests `qty=11, cif_fc=110`. Line 842 clamps `remaining_qty` to `max(0, 10-11) = 0`. Line 844 recomputes `remaining_cif_fc = 0 × 10 = 0`. The plan shows zero remaining, but the licence's CIF pool was drawn by 110 (not 100). Next allocation checks plan-remaining=0 and rejects. **The 10 units of CIF are lost.**

**Fix:** Decrement by the actual `cif_fc` allotted. If either would go negative, emit `PLAN_LINE_EXCEEDED` (an error) instead of clamping.

---

### F10 — Float Arithmetic in Balance Writer (LOW)

**Where:** `calculate_balance.py:92-97` computes availability via `to_float()`

**Problem:** Precision loss. `_update_balance_sync()` swallows every exception, so a failed refresh is invisible.

**Fix:** Use Decimal throughout. Surface balance refresh failures as `BALANCE_REFRESH_FAILED` → rollback.

---

## 4 BLOCKING BUSINESS DECISIONS (D1-D4)

### D1 — Define Company Boundary (BLOCKING)

**Issue:** Licences have no company FK. Users have no company scope.

**Options:**
- **(a) Hard reject:** Allocate only if `license.ownership.current_owner == allotment.company`
- **(b) Warn, allow:** Cross-company is legal; only log it
- **(c) No check:** Scenario 7 (cross-company rejection) is deleted; rule does not exist

**Evidence:** `AllotmentModel.related_company` exists to model a second party, suggesting (b)/(c).

**Impact:** Blocks F6 authorization implementation and Scenario 7 acceptance.

---

### D2 — CIF Validation: Authoritative or Derived? (BLOCKING)

**Issue:** `cif_fc` arrives from the request (F8). Is it a user input to validate, or derived from `qty × unit_price`?

**Options:**
- **(a) Authoritative:** Client sends it; validate against tolerance band (define band, define rounding)
- **(b) Derived:** Ignore client input; compute as `qty × allotment.unit_value_per_unit`

**Evidence:** Inconsistent today — `cif_fc` is serialized but `cif_inr` is never set.

**Impact:** Changes API contract and view logic significantly.

---

### D3 — Allotment Approval Gate (BLOCKING)

**Issue:** `AllotmentModel.is_approved` field exists but gates nothing.

**Question:** Should allocation be rejected if the allotment is not approved?

**Options:**
- **(a) Yes:** Add `ALLOTMENT_NOT_APPROVED` error
- **(b) No:** Field is informational; remove from allocation checks

**Impact:** Blocks test scenario acceptance.

---

### D4 — Decimal Precision Alignment (BLOCKING)

**Issue:** `available_quantity` is `round(value, 0)` in float, then `round(value, 2)`. `AllotmentItems.qty` is `Decimal(places=3)`.

**Problem:** A 3-dp allocation against a 2-dp ceiling can under- or over-shoot by ±0.005.

**Fix:** Pick one precision, quantize ceilings with `ROUND_DOWN`, quantities with `ROUND_HALF_UP`.

**Impact:** Changes validation thresholds; needs reconciliation against existing data.

---

## SERVICE INTERFACE

```python
@dataclass(frozen=True)
class AllocationLine:
    item_id: int
    qty: Decimal
    cif_fc: Decimal
    cif_inr: Decimal | None = None
    plan_line_id: int | None = None

class CanonicalAllocationService:
    @classmethod
    def allocate(cls, request: AllocationRequest) -> AllocationResult:
        """Allocate items to an allotment.
        
        request.mode: "strict" (default) = all-or-nothing, or "best_effort" = per-line.
        Fixes F1-F10 and implements all 8 invariants (§8).
        """
        
    @classmethod
    def deallocate(cls, *, allotment_item_id: int, actor) -> AllocationResult:
        """Remove an allocation."""
        
    @classmethod
    def update_allocation(cls, *, allotment_item_id: int, qty, cif_fc, actor) -> AllocationResult:
        """Modify an existing allocation."""
        
    @classmethod
    def preview(cls, request: AllocationRequest) -> AllocationResult:
        """Validate without writing. Returns committed=False."""
        
    @classmethod
    def max_allocatable(cls, *, allotment, import_item, plan_line_id=None) -> AllocationCeiling:
        """Return the binding constraint and max qty/cif."""
```

---

## 8 INVARIANTS (Asserted Pre-Commit, Checked by `check_allocation_health` Management Command)

1. `SUM(AllotmentItems.qty) <= allotment.required_quantity`
2. `SUM(AllotmentItems.cif_fc) <= allotment.required_value + BUFFER (20 FC)`
3. `item.available_quantity >= 0` for every touched item
4. `used_qty + used_cif <= plan_original` for every plan group
5. `plan_line.remaining_qty >= 0` and `remaining_cif_fc >= 0`
6. `AllotmentItems.qty > 0` and `cif_fc > 0`
7. `AllotmentItems.cif_inr ≈ cif_fc × allotment.exchange_rate` (±0.01)
8. Outstanding allotment filter is `Q(bill_of_entry__isnull=True, type='AT')`

---

## ALGORITHM (Phase-by-Phase)

**Phase 0 — Shape Validation (no DB)**
- Reject empty lines, duplicate items, qty ≤ 0, cif_fc ≤ 0

**Phase 1 — Deterministic Locking**
- Lock allotment first, then all import items by PK order, then all plan lines
- Prevents deadlock between concurrent multi-item requests

**Phase 2 — Running In-Memory Ledger (Fixes F1, F2)**
- Compute **once** from live aggregates, NOT denormalized columns
- Decrement running ledger after each successful line
- Correctness no longer depends on post-commit hooks

**Phase 3 — In-Transaction Balance Refresh (Fixes F1)**
- Call `update_balance_values()` synchronously inside transaction
- Suppress post_save signal to avoid double refresh

**Phase 4 — Invariant Assertions**
- Violated invariant → rollback (it's a bug, not user error)

**Phase 5 — Fresh Snapshot**
- Re-fetch allotment with fresh instance (fixes F3)

---

## ERROR TAXONOMY

- Request shape: NO_LINES, DUPLICATE_ITEM, INVALID_QUANTITY, INVALID_CIF, VALUE_MISMATCH
- Existence: INVALID_ALLOTMENT, INVALID_LICENSE, ITEM_NOT_FOUND, PLAN_LINE_NOT_FOUND
- Authorization: NOT_AUTHORIZED, COMPANY_SCOPE_VIOLATION
- State: LICENSE_EXPIRED, ALLOTMENT_LOCKED, ALLOTMENT_NOT_APPROVED
- Capacity: INSUFFICIENT_QUANTITY, INSUFFICIENT_CIF, ALLOTMENT_EXCEEDED, PLAN_EXCEEDED
- Infrastructure: LOCK_TIMEOUT, BALANCE_REFRESH_FAILED, INTERNAL_ERROR

---

## MIGRATION PLAN (Behavior-Preserving, Staged)

1. Extract `views_actions.py:660-852` into `CanonicalAllocationService.allocate(mode="best_effort")`
2. Make endpoint a thin adapter; golden-master the endpoint's JSON (byte-identical)
3. Re-point Module 3 test suite from `AllocationService` to `CanonicalAllocationService`
4. **Failing scenarios are the deliverable — they expose real defects**
5. Fix in dependency order: F7/F4 first, then F2/F3, then F1, then F9
6. Delete `AllocationService` (nothing in production imports it)
7. Flip default to `strict` behind a settings flag
8. F6 (authorization) ships separately after D1 is decided

---

## ACCEPTANCE CRITERIA

- [ ] All 17 Module 3 scenarios pass against `CanonicalAllocationService`
- [ ] 5 existing `test_allocate_items_*.py` files pass unchanged (golden master)
- [ ] New tests for each finding: F1 (concurrent), F2 (intra-request), F3 (consistency), F4 (exception), F5 (partial), F7 (bounds), F9 (plan drawdown)
- [ ] `check_allocation_health` reports zero violations across existing dataset
- [ ] No cached property accessed inside service (grep in CI)
- [ ] Query count O(1) in lines (batched locks, no N+1)

---

## DEPENDENCIES & SEQUENCING

- **Blocks:** Nothing (can run in parallel with Module 2 freeze)
- **Blocked by:** D1, D2, D3 decisions (needed before code review)
- **Related modules:** Module 2 (plan enforcement), Module 4 (BOE), Module 5 (balance integrity)

---

**Status:** Ready for implementation once decisions D1-D4 are resolved.
