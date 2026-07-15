# Business Decision Log

> **Domain decisions and their rationale.**  
> Preserved so future developers understand WHY rules exist, not just WHAT they are.

---

## BD-001: Balance Is Async, Never Synchronous

**Decision**: License balance is never recomputed inline during a request. Always via Celery.

**Why**: 
- Balance formula requires 4 separate aggregate queries across 4 different tables
- Tables are owned by the legacy system; no transactions cross both apps
- Under concurrent load (multiple users creating allotments simultaneously), synchronous recompute would create locks held for too long
- A failed balance recompute should not fail the user's primary action (creating an allotment)

**Consequence**: Balance may lag by seconds after a user action. UI shows "Balance last updated: {ledger_date}".

**Alternatives Considered**:
- Inline recompute: rejected (too slow, locks too long)
- DB triggers: rejected (legacy DB owns DDL; cannot modify)
- Event sourcing: rejected (too complex for current phase)

---

## BD-002: managed=False For All Business Tables

**Decision**: All concrete models in the new backend have `managed = False`.

**Why**: 
- Tables are owned by the legacy backend (legacy/backend/)
- The legacy backend manages all DDL via its own migrations
- The new backend is a read/write proxy during the parallel-run phase
- Adding `managed = True` would cause Django to try to DROP and recreate legacy tables on `migrate`

**Consequence**: 
- `makemigrations` must never be run for accounts/core/license/allotment/boe/trade/tasks
- Field definitions in models.py must exactly match the legacy DB schema
- Any schema change requires coordination with the legacy team

**Open Question**: After final cutover, which app owns DDL going forward? → **Pending decision** (ADR to be written at cutover time)

---

## BD-003: Planning Is Optional (No Restriction Without Plan)

**Decision**: If no `LicenseItemPlan` row exists for an import item, allotments are unrestricted.

**Why**:
- Thousands of legacy licenses have no planning data
- Requiring planning would block all allotments on migrated licenses until plans are created
- Some operators prefer not to use planning (less administrative overhead)

**Consequence**: Over-allotment is possible for unplanned items. The balance formula still prevents over-consumption of the license balance itself, but planning is a pre-consumption control.

**Business Rule**: PLAN-001 — "Planning is optional"

---

## BD-004: Allotment Exits Balance Formula When BOE Is Linked

**Decision**: An allotment only counts in `_compute_allotment()` when `allotment.bill_of_entry IS NULL`.

**Why**: 
- When a BOE is raised against an allotment, the allotment "becomes" a real debit
- If both allotment AND debit were counted, the balance would be reduced twice for the same physical import
- The M2M relationship `BillOfEntryModel.allotment` provides the linkage signal

**Example**:
```
Allotment (cif_fc=1000): reduces balance by 1000 (reservation)
BOE from allotment (cif_fc=1000): 
  → allotment exits formula (bill_of_entry IS NOT NULL) → +1000 back
  → BOE debit enters formula → -1000
  → Net change: 0 (reservation became real debit at same amount)
```

**Assumption**: BOE amount ≈ allotment amount. If they differ, the delta reflects the actual difference.

**Known Risk**: If the allotment M2M is not set when creating a BOE from an allotment, both are counted simultaneously → double-deduction. The BOE serializer sets this M2M in `create()` and `update()`.

---

## BD-005: 3 Decimal Places for `pct` and `rate_pct`

**Decision**: Trade billing percentages (`pct`, `rate_pct`) are stored and computed at 3 decimal places.

**Why**:
- DGFT licenses sometimes specify exact percentages like 7.925% or 2.125%
- Rounding to 2dp before computation introduces errors:
  - 7.925% × 100,000 = 7,925.00 (correct)
  - q2(7.925) = 7.93 → 7.93% × 100,000 = 7,930.00 (wrong by Rs 5)
- For large CIF values, this rounding error compounds

**Rule**: Use `Decimal(str(pct))` NOT `q2(pct)` when pct/rate_pct is a percentage used for division.

**Tested by**: `test_trade.py::test_pct_3dp_precision_cif` (pins: 7.925 × 100,000 = 7,925.00 not 7,930.00)

---

## BD-006: Redis DB Isolation (Cache/Broker/Results Separated)

**Decision**: Django cache, Celery broker, and Celery results use separate Redis DBs (/1, /2, /3).

**Why**:
- A `cache.clear()` call (e.g., for cache busting) would also wipe in-flight Celery task messages if they share a DB
- A Redis `FLUSHDB` for debugging would kill active worker queues
- Result key TTL and cache key TTL are different — mixing them in one keyspace causes accidental evictions

**Alternative**: Use separate Redis instances. Rejected as over-engineering for current scale.

**Enforced by**: `config/settings/base.py` — each URL explicitly appends `/1`, `/2`, `/3` to `REDIS_URL`.

---

## BD-007: `ooc_date` Must Remain CharField(255)

**Decision**: `BillOfEntryModel.ooc_date` is `CharField(255)`, not `DateField`.

**Why**:
- ICEGATE (the customs authority portal) returns `ooc_date` as raw text in various formats
- Formats include: "25-12-2024", "25/12/2024", "25 Dec 2024", "N/A", "PENDING", "" (empty)
- Attempting to parse this as `DateField` would cause `ValidationError` on import for non-date values
- This field is displayed verbatim to operators — they use it for reference only

**Consequence**: Date-based filtering on `ooc_date` is not possible. Operators must filter by `bill_of_entry_date` instead.

**Future Enhancement**: After all ICEGATE data is normalized, consider migrating to a nullable `DateField` with a `raw_ooc_date` fallback.

---

## BD-008: Celery Tasks Use `acks_late=True`

**Decision**: All financial Celery tasks use `acks_late=True, reject_on_worker_lost=True`.

**Why**:
- Default behavior: message is ACKed when picked up by worker. If worker crashes mid-execution, message is lost.
- With `acks_late=True`: message is ACKed only after task completes. If worker crashes, message returns to queue for retry.
- Balance recompute and report generation are both critical — silent drops are unacceptable.

**Trade-off**: Tasks may execute twice if they crash after completion but before ACK. Both are idempotent (balance recompute writes the same result regardless of how many times it runs).

---

## BD-009: `UserSerializer` Must Include `is_superuser`

**Decision**: The login endpoint response and `/me` endpoint must include `is_superuser: boolean`.

**Why**:
- Frontend `AuthContext.hasAnyRole()` checks `user?.is_superuser` to grant blanket access to superusers
- Without this field, superusers have `is_superuser = undefined` (falsy)
- All role-gated navigation items (Licenses, Allotments, BOE, Trade, Reports) are hidden
- This was a production bug fixed in commit 362cc9ac

**Symptom if removed**: Superusers see only 3 items in sidebar (Dashboard, Masters, Tasks). No "New License" or other write buttons appear.

**This MUST have a regression test** (currently missing — see improvement register M-009/test gap).

---

## BD-010: BOE Row Scoping Prevents IDOR

**Decision**: All row-level operations (update, delete, resolve dispute) scope `RowDetails.objects.get(pk=row_id, bill_of_entry_id=boe_id)`.

**Why**:
- Without scoping, a `BOE_MANAGER` user can update or delete rows from ANY BOE by guessing row IDs
- This is an Insecure Direct Object Reference (IDOR) — a OWASP Top 10 vulnerability
- The BOE ID comes from the URL: `PATCH /api/v1/bill-of-entries/{boe_id}/rows/{row_id}/`

**Fixed in**: Security audit Phase 1, commit 743d37df.

---

## Open Questions

| # | Question | Context | Owner |
|---|---|---|---|
| OQ-1 | Who owns DDL after final cutover? | Currently legacy backend owns all tables | TBD at cutover |
| OQ-2 | Should planning be mandatory for new licenses? | Currently optional for backward compat | Product decision |
| OQ-3 | Should balance report use `balance_service._compute_*`? | Currently reimplements — missing trade component | Engineering |
| OQ-4 | When should `generate_license_pdf_task` be implemented? | Currently a stub | Engineering priority |
| OQ-5 | JWT RS256 migration (post-cutover)? | ADR-006: HS256 during transition, RS256 after | ADR-006 |
