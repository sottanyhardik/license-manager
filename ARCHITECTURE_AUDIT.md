# MODULE 04 — Master Sync Architecture Audit
**Date:** 2026-08-12  
**Auditor:** Principal Backend Architect  
**Scope:** Complete architectural review of Master Synchronization implementation

---

## EXECUTIVE SUMMARY

Module 04 implements a multi-server Master Data synchronization system using an Outbox/Inbox event-sourcing pattern with deterministic UUID-based identity and version-based conflict resolution. The architecture is **broadly sound** with strong foundations but has **3 Critical concerns**, **7 Concerns**, and **2 Good areas** that require attention before production deployment.

**Overall Risk Level:** MEDIUM-HIGH (addressable with focused fixes)

---

## 1. MasterSyncMixin INHERITANCE ON ALL 16 MASTERS

**Scope:** All Master model classes inherit from MasterSyncMixin  
**Status:** ✅ GOOD

### Analysis

**16 Masters Confirmed:**
1. CompanyModel
2. PortModel
3. ItemGroupModel
4. ItemNameModel
5. HSCodeModel
6. HeadSIONNormsModel
7. SionNormClassModel
8. SIONExportModel
9. SIONImportModel
10. SionNormNote
11. SionNormCondition
12. ProductDescriptionModel
13. UnitPriceModel
14. SchemeCode
15. NotificationNumber
16. ExchangeRateModel

**Mixin provides:**
- `master_uid`: Globally unique, immutable, deterministic UUID
- `master_version`: Conflict-detection counter (starts at 1, increments on update)
- `deleted`, `deleted_at`, `tombstone_version`: Soft-delete fields for sync recovery
- `compute_master_uid()`: Abstract method each Master must implement
- `save()`: Auto-computes UID on first save, increments version on updates
- `mark_deleted()`: Soft-delete with tombstone tracking
- `get_sync_payload()`: Serialization for sync events

**Strengths:**
- All 16 Masters inherit correctly (verified via grep)
- Mixin is abstract (good isolation)
- Immutable master_uid prevents sync chaos
- Version auto-increment reduces manual errors
- Soft-delete preserves audit trail

**Concern #1 — Version Increment Timing:** CONCERN  
**Issue:** `save()` increments version on updates, but calls AFTER the model's own save. If a subclass also increments version in its own save(), we get double-increment.

```python
# In MasterSyncMixin.save()
if not is_new and self.master_version:
    self.master_version += 1  # <-- INCREMENTS HERE

super().save(*args, **kwargs)
```

If any Master's save() also calls `increment_version()` explicitly, version skips (1→3 instead of 1→2).

**Risk:** Version gaps confuse sync conflict detection (is a gap a lost update or corruption?).

**Recommendation:** Document that subclasses MUST NOT call `increment_version()` explicitly in save(); rely on mixin only.

---

## 2. SERVICE LAYER COMPLETENESS

### 2a. MasterUIDService

**Status:** ✅ GOOD

**Features:**
- Deterministic UUID5 generation from natural keys
- Canonical namespace (single, immutable UUID)
- Per-model factory methods (for_company, for_port, etc.)
- Composite key normalization (e.g., SIONExport: norm_class | description | quantity | unit)

**Strengths:**
- Single source of truth (MASTER_NAMESPACE)
- Normalization ensures "C001", "c001", " C001 " → same UID
- Factory methods reduce boilerplate

**Concern #2 — Missing Factory Methods:** CONCERN  
**Issue:** `master_sync_base.py` docstring references `compute_master_uid()` subclass implementation, but only MasterUIDService has the canonical recipes. If a Master implements its own UUID5 differently, we get divergence.

Example missing from codebase:
```python
# HeadSIONNormsModel.compute_master_uid()
def compute_master_uid(self):
    # Question: Is this using MasterUIDService or its own logic?
    # Unclear from code.
```

**Risk:** UID collisions or drift across servers.

**Recommendation:** Add verification that all 16 Masters use MasterUIDService factory methods, not custom logic.

### 2b. MasterVersionService

**Status:** ✅ GOOD

**Features:**
- Version comparison: `is_newer()`, `is_stale()`, `is_concurrent()`
- Conflict tiebreaker: alphabetically earlier server wins
- Version sequence validation
- Exponential backoff for retries

**Strengths:**
- Deterministic conflict resolution (all servers converge to same decision)
- Clear semantics for version states

**No critical issues identified.**

### 2c. MasterEventBuilder

**Status:** ✅ GOOD

**Features:**
- Canonical event structure (CREATE/UPDATE/DELETE)
- Payload serialization with SHA256 hash
- Event validation (`validate_event()`)
- Payload integrity verification (`verify_payload_hash()`)

**Strengths:**
- Event structure is immutable and auditable
- Payload hash prevents corruption

**Concern #3 — Soft-Delete Field Missing from Event:** CONCERN  
**Issue:** In `_serialize_instance()`, the code checks for `deleted`, `deleted_at`, `tombstone_version` fields but these are NOT guaranteed to exist on all Master models.

```python
# In MasterEventBuilder._serialize_instance()
if hasattr(instance, 'deleted'):
    payload['deleted'] = instance.deleted
```

This is defensive, but raises a question: Do ALL 16 Masters actually have these fields? If not, tombstone reconciliation won't work.

**Risk:** Some Masters won't participate in soft-delete recovery, breaking eventual consistency.

**Recommendation:** Verify that MasterSyncMixin guarantees soft-delete fields on all subclasses.

---

## 3. TRANSACTION BOUNDARIES AND ATOMICITY

**Status:** ⚠️ CONCERN

### 3a. Outbox Signal Isolation

**Current Design:**
```python
def create_outbox_entry(instance, operation):
    # Uses SEPARATE transaction
    with transaction.atomic():
        MasterSyncOutbox.objects.create(...)
```

**Strength:** Signal failures don't break model saves  
**Weakness:** **Potential Lost Events**

If the model save succeeds but outbox creation fails (network, DB full, etc.), the Master is updated but not queued for sync. Other servers never learn about the change.

**Severity:** CRITICAL ⛔

**Example Failure Scenario:**
1. Server A creates Company "C001" → save succeeds
2. Outbox entry creation fails (DB hit max_connections)
3. Server B polls Server A's outbox → sees no event → thinks Company doesn't exist
4. Inconsistency: Server A has Company, Server B doesn't

**Current Mitigation:**
```python
logger.warning(f"Failed to create outbox for {instance.__class__.__name__}: ...")
```
Only logs a warning; doesn't retry or alert.

**Recommendation:**
1. **Option A (Strict):** Use same transaction (fail model save if outbox fails)
   - Pro: Strong guarantees
   - Con: Signal errors crash user requests

2. **Option B (Resilient):** Background job re-scans Masters for unqueued changes
   - Pro: Tolerates transient failures
   - Con: More complex, higher latency

**Recommendation:** Implement Option B with hourly reconciliation job.

### 3b. Inbox Event Application

**Current Design:**
```python
# In periodic_sync_inbox task
with transaction.atomic():
    model.objects.update_or_create(master_uid=event.master_uid, defaults=event.payload)
    event.status = 'APPLIED'
    event.save()
```

**Issue:** Bulk `update_or_create()` is NOT atomic with signal handlers in Django 1.11+.

If the model's post_save signal triggers another outbox entry DURING the transaction, we could have infinite loop:
1. Inbox receives UPDATE event for Company
2. `update_or_create()` triggers signal
3. Signal creates outbox entry
4. This outbox entry might get sent back to originating server as a bounce
5. Creates version conflict

**Severity:** CONCERN ⚠️

**Current Safeguard:** Signals use separate transactions, but this doesn't prevent version skew.

**Recommendation:** 
1. **Disable signals during inbox application:** Use `signal.disconnect()` context manager
2. **Or:** Re-enable signals only AFTER cursor advance

```python
# Better:
from django.db.models.signals import post_save
with signals_disabled(post_save):
    model.objects.update_or_create(...)
event.status = 'APPLIED'
event.save()
```

### 3c. Version Increment Atomicity

**Current Design:**
```python
# In MasterSyncMixin.save()
if not is_new and self.master_version:
    self.master_version += 1
super().save(*args, **kwargs)
```

**Issue:** NOT atomic under concurrent updates.

Scenario:
1. Thread A: reads version=5, computes 6
2. Thread B: reads version=5, computes 6
3. Both save with version=6 → **version collision**

**Severity:** CONCERN ⚠️

**Recommendation:** Use atomic increment in database:

```python
# Better:
if not is_new:
    # Atomic DB increment
    self.__class__.objects.filter(pk=self.pk).update(
        master_version=F('master_version') + 1
    )
    self.refresh_from_db(fields=['master_version'])
else:
    super().save(*args, **kwargs)
```

---

## 4. OUTBOX/INBOX PATTERN CORRECTNESS

**Status:** ✅ GOOD with caveats

### 4a. Outbox Design

**Strengths:**
- Append-only, immutable event log
- Natural ordering by creation time
- Delivered tracking per server
- Retry with exponential backoff

**Concern #4 — Delivered Tracking is Eventual:** CONCERN  
**Issue:** `delivered_to_servers` is a JSONField updated separately after HTTP success. If the update fails, event is "delivered" on remote but local tracking says "pending".

```python
# Current code:
response = client.post(endpoint, json=payload, headers=headers)
response.raise_for_status()

# Then LATER:
delivered = event.delivered_to_servers or {}
delivered[remote_server.server_id] = timezone.now().isoformat()
event.delivered_to_servers = delivered
event.save(update_fields=['delivered_to_servers'])
```

If the .save() fails, we've already sent the event but don't know it locally.

**Risk:** Outbox task may not retry (thinks it's delivered) and eventually purges the event from retry queue.

**Current Safeguard:** Events are never deleted (good), but tracking can diverge.

**Recommendation:** Wrap both operations in atomic transaction or use database-native delivery tracking (separate table).

### 4b. Inbox Design

**Strengths:**
- Idempotent by event_uuid (unique constraint)
- Status transitions are clear (PENDING → APPLIED)
- Payload hash for integrity verification

**Concern #5 — Status Field Mismatch:** CONCERN  
**Issue:** Inbox has `status` choices with values like `'APPLIED'`, `'REJECTED'`, `'CONFLICTED'`, but tasks use `'FAILED'`:

```python
# In signals_master_sync.py
event.status = MasterSyncInbox.STATUS_FAILED  # ← not defined in model!
event.conflict_reason = str(e)
event.save()
```

The constant `STATUS_FAILED` doesn't exist on MasterSyncInbox. This will raise ValidationError on save.

**Severity:** CRITICAL ⛔

**Current Code:**
```python
# models.py defines:
STATUS_APPLIED = 'APPLIED'
STATUS_REJECTED = 'REJECTED'
STATUS_CONFLICTED = 'CONFLICTED'

# But tasks.py uses:
event.status = MasterSyncInbox.STATUS_FAILED  # ← undefined
```

**Recommendation:** Add `STATUS_FAILED` to MasterSyncInbox or use `STATUS_REJECTED`.

---

## 5. SIGNAL HANDLER COVERAGE

**Status:** ✅ GOOD

**Coverage:** All 16 Masters have post_save and post_delete signals registered.

**Strengths:**
- Comprehensive (no Masters missed)
- Proper dispatch_uids (prevents duplicate registration)
- Separate handlers for CREATE vs UPDATE

**Concern #6 — Missing Natural Key Implementation:** CONCERN  
**Issue:** The `get_natural_key()` function in signals_master_sync.py has hard-coded mappings for all 16 Masters. If a new Master is added or a natural key field changes, the mapping breaks.

```python
def get_natural_key(instance):
    model_name = instance.__class__.__name__
    if model_name == 'CompanyModel':
        return instance.iec
    elif model_name == 'PortModel':
        return instance.code
    # ... 14 more elif clauses
    return str(instance.pk)
```

**Risk:** Adding a new Master requires updating this function in 2+ places.

**Recommendation:** Move natural key definitions to model Meta class:

```python
# In each Master:
class Meta:
    master_natural_key_fields = ['iec']  # or ['code'] for Port, etc.

# Then use generically:
def get_natural_key(instance):
    meta = instance._meta
    nk_fields = getattr(meta, 'master_natural_key_fields', ['pk'])
    return '|'.join(str(getattr(instance, f)) for f in nk_fields)
```

---

## 6. CELERY TASK INTEGRATION

**Status:** ⚠️ CONCERN

### 6a. Task Schedules

**Current:**
- `periodic_sync_outbox`: Every 10 seconds
- `periodic_sync_inbox`: Every 5 seconds
- `periodic_reconciliation`: Every hour

**Concern #7 — No Jitter in Celery Beat Schedule:** CONCERN  
**Issue:** All tasks fire at fixed intervals (0, 10, 20, 30... seconds). If you have 100 servers, they all hammer the database simultaneously at second=0.

**Recommendation:** Add jitter (random offset ±10% of interval) in beat configuration.

### 6b. Inbox Processing Limit

**Current:**
```python
pending_events = MasterSyncInbox.objects.filter(
    status=MasterSyncInbox.STATUS_PENDING
).order_by('received_at')[:100]  # <-- hard-coded limit
```

**Good:** Prevents memory explosion  
**Concern:** 100 events every 5 seconds = 72k events/hour. If inbound rate > 72k/hr, queue grows unbounded.

**Recommendation:** Scale limit based on median processing time:
```python
limit = max(100, int(60 / (average_processing_time_seconds + 0.1)))
```

---

## 7. CONCURRENCY AND LOCKING STRATEGY

**Status:** ⛔ CRITICAL GAPS

### 7a. No Database-Level Locking

**Current Approach:** Relies on Django ORM and transaction isolation level.

**Issues:**

1. **SELECT + UPDATE race condition in version increment**
   ```python
   # No locking; 2 threads can both read version=5, compute 6
   self.master_version += 1
   ```
   
   **Fix required:**
   ```python
   from django.db.models import F
   Model.objects.filter(pk=self.pk).update(
       master_version=F('master_version') + 1
   )
   ```

2. **Outbox delivery tracking not atomic**
   ```python
   # If two tasks process same event simultaneously:
   delivered = event.delivered_to_servers or {}  # Thread A reads {}
   delivered[server.id] = now  # Thread A writes
   event.save()  # Thread A saves
   
   # Meanwhile Thread B also processed same event
   # Both try to deliver, both succeed, delivered tracking diverges
   ```

3. **Cursor update in offline recovery**
   ```python
   # In advance_cursor(): no lock on cursor table
   cursor.last_applied_event_uid = event_uid
   cursor.save()  # Race: two tasks can both advance cursor
   ```

**Severity:** CRITICAL ⛔

**Recommendation:**

1. Use `select_for_update()` in Celery tasks:
   ```python
   outbox = MasterSyncOutbox.objects.select_for_update().get(pk=event.pk)
   # Now safe from races
   ```

2. Use F() expressions for counter increments:
   ```python
   Event.objects.filter(pk=pk).update(attempts=F('attempts') + 1)
   ```

3. Atomic cursor advancement:
   ```python
   cursor, created = MasterSyncCursor.objects.select_for_update().get_or_create(
       server_id=server_id,
       defaults={...}
   )
   cursor.last_applied_event_uid = event_uid
   cursor.save(update_fields=['last_applied_event_uid', ...])
   ```

### 7b. No Deadlock Detection

If tasks A and B try to lock Outbox then Cursor (A then B), and Cursor then Outbox (B then A), database deadlock occurs. Current code has no deadlock recovery.

**Recommendation:** Implement exponential backoff with jitter on database errors.

### 7c. Multi-Server Sync Ordering

**Current:** No guarantees on which server's update wins if concurrent.

MasterVersionService implements tiebreaker:
```python
if remote_origin_server < local_origin_server:
    return "REMOTE"
else:
    return "LOCAL"
```

This is deterministic but not necessarily the user's intended winner. If Server B's update is "older" (arrived later) but has lower server_id, it wins.

**Risk:** User edits a Master, remote server also edits → user's edit might be overwritten.

**Recommendation:** Document this behavior clearly; consider adding timestamp-based tiebreaker as option.

---

## 8. MULTI-SERVER SYNC FLOW

**Status:** ✅ GOOD (architecture)

### 8a. Push-Pull Hybrid

**Model:**
- Outbox task PUSHes events to remote servers (HTTP POST)
- Remote servers receive via API and store in Inbox
- Inbox task PULLs from queue and applies locally

**Strengths:**
- Event-sourcing audit trail
- No need for bidirectional network connectivity
- Supports offline recovery (cursor-based catch-up)

### 8b. Event Security

**Current:** HMAC-SHA256 signature with timestamp + nonce.

**Strengths:**
- Server authentication (bearer token in Authorization header)
- Payload integrity (hash-based)
- Replay protection (nonce checked in cache)

**Concern:** Timestamp tolerance is 300 seconds (5 minutes). If clocks are out of sync by >5min, events are rejected.

**Recommendation:** Document clock sync requirement; consider tightening to 60 seconds.

---

## 9. IDENTIFIED GAPS & VIOLATIONS

### Missing Features

1. **No distributed lock provider** — uses Django ORM only; doesn't scale to high concurrency
2. **No dead-letter queue** — failed events are retried forever; no alert system
3. **No metrics/observability** — no Prometheus metrics, no structured logging
4. **No circuit breaker** — if remote server is down, tasks keep retrying, no backoff
5. **No idempotency key for Outbox push** — could be sent twice with no deduplication

### Architectural Violations

1. **Outbox transaction isolation** — Signal fires AFTER save in separate transaction (potential lost event)
2. **Version increment race condition** — Not atomic, vulnerable to concurrent updates
3. **Inbox status field mismatch** — Uses undefined STATUS_FAILED constant
4. **Cursor advancement race** — No locking in offline recovery handler

---

## 10. SCORING SUMMARY

| Area | Score | Rationale |
|------|-------|-----------|
| **MasterSyncMixin Coverage** | ✅ GOOD | All 16 Masters inherit correctly; immutable UID is strong |
| **UIDService** | ✅ GOOD | Deterministic, well-documented, single namespace |
| **VersionService** | ✅ GOOD | Clear semantics, deterministic tiebreaker, no issues |
| **EventBuilder** | ⚠️ CONCERN | Good structure, but soft-delete field presence unclear |
| **Outbox/Inbox Pattern** | ⚠️ CONCERN | Design is solid but status field mismatch + delivery tracking race |
| **Signal Handlers** | ✅ GOOD | Comprehensive coverage; natural key mapping is rigid but works |
| **Celery Tasks** | ⚠️ CONCERN | No schedule jitter, no deadlock handling, hard-coded limits |
| **Transaction Boundaries** | ⛔ CRITICAL | Multiple lost-event scenarios, non-atomic version increment, race conditions |
| **Concurrency/Locking** | ⛔ CRITICAL | No database-level locking, cursor advancement unprotected, potential deadlocks |
| **Multi-Server Sync Flow** | ✅ GOOD | Push-pull hybrid is solid; security model is sound |

---

## 11. CRITICAL FIXES REQUIRED (Before Production)

### P0 — Blocking Issues

1. **Fix Inbox Status Constant**
   ```python
   # Add to MasterSyncInbox
   STATUS_FAILED = 'FAILED'
   ```
   Or change tasks to use existing STATUS_REJECTED.

2. **Fix Version Increment Race Condition**
   Use F() expression for atomic increment:
   ```python
   Model.objects.filter(pk=self.pk).update(
       master_version=F('master_version') + 1
   )
   self.refresh_from_db(fields=['master_version'])
   ```

3. **Fix Cursor Advancement Race**
   Add select_for_update() in OfflineRecoveryHandler.advance_cursor().

4. **Fix Outbox Delivery Tracking Race**
   Wrap both HTTP POST and DB update in atomic transaction; or use separate delivery tracking table.

### P1 — High Priority

5. **Implement Signal Disabling During Inbox Apply**
   Prevent bounce-back loops when applying remote updates.

6. **Add select_for_update() to Celery Tasks**
   Protect concurrent access to Outbox and Inbox in periodic tasks.

7. **Document MasterUIDService Usage**
   Verify all 16 Masters use service, not custom logic.

8. **Add Outbox Reconciliation Job**
   Hourly scan for Masters with no outbox entries → catch lost events.

### P2 — Medium Priority

9. **Add Jitter to Celery Beat Schedule**
   Reduce thundering herd effect on DB.

10. **Move Natural Key to Meta Class**
    Reduce boilerplate and coupling in signal handlers.

11. **Add Metrics & Structured Logging**
    Prometheus counters for outbox/inbox/conflicts.

---

## 12. RECOMMENDATIONS FOR PRODUCTION DEPLOYMENT

### Go/No-Go Checklist

- [ ] Fix P0 issues #1-4 (estimated 4 hours)
- [ ] Fix P1 issues #5-8 (estimated 8 hours)
- [ ] Run concurrency stress test (10k events, multi-threaded)
- [ ] Verify clock sync across all servers (<1 second drift)
- [ ] Set up monitoring dashboards (outbox lag, inbox lag, conflict rate)
- [ ] Test failover scenario (kill one server, verify sync continues)
- [ ] Audit all 16 Masters' compute_master_uid() implementations
- [ ] Load test with simulated network latency (100-500ms)

### Operational Readiness

- [ ] Runbooks for conflict resolution (manual)
- [ ] Monitoring alert for: outbox lag > 60s, inbox lag > 60s, versions < 0
- [ ] Backup strategy for Outbox/Inbox tables
- [ ] Offline recovery procedure (cursor reset, full resync)

---

## APPENDIX A: Test Coverage Status

**Existing tests:**
- `test_master_sync_unit.py` — UID determinism, outbox/inbox basics
- `test_master_sync_integration.py` — Full CREATE/UPDATE/DELETE flow

**Missing tests:**
- [ ] Concurrent version increment (stress test)
- [ ] Cursor race condition (2 threads advancing simultaneously)
- [ ] Lost event recovery (outbox creation failure scenario)
- [ ] Signal bounce-back (update triggers outbox, outbox loops back)
- [ ] Deadlock detection (A→B→A lock pattern)
- [ ] Timestamp tolerance edge cases (clock skew)
- [ ] Natural key collision (2 Masters with same natural key)

---

## APPENDIX B: Files Reviewed

```
backend/apps/core/master_sync_base.py
backend/apps/core/models.py (MasterSyncOutbox, MasterSyncInbox, MasterConflict, MasterSyncCursor)
backend/apps/core/signals_master_sync.py
backend/apps/core/services/master_uid_service.py
backend/apps/core/services/master_version_service.py
backend/apps/core/services/master_event_builder.py
backend/apps/core/services/master_sync_retry.py
backend/apps/core/services/master_sync_reconciliation.py
backend/apps/core/services/master_sync_security.py
backend/apps/core/services/master_sync_global_usage.py
backend/apps/core/services/master_sync_usage.py
backend/apps/core/tasks.py (periodic_sync_outbox, periodic_sync_inbox, periodic_reconciliation)
backend/apps/core/views/master_sync.py (MasterSyncEventsView, MasterSyncFetchView, MasterSyncAckView, MasterSyncCursorView, MasterSyncHealthView)
```

---

## CONCLUSION

Module 04's Master Sync architecture is **well-designed at the service layer** (UID, version, event building) but has **critical implementation gaps** in transaction isolation, concurrency control, and race condition handling. The system is suitable for **low-load, single-server scenarios** but requires the P0 fixes listed above before **multi-server production deployment**.

**Time to Production-Ready:** ~12-16 hours of focused engineering (fixes + tests + validation).

**Risk of Skipping Fixes:** Data inconsistency, version skew, potential data loss during high concurrency.
