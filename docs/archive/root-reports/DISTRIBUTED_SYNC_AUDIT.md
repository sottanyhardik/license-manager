# DISTRIBUTED SYNC AUDIT — Multi-Server Master Data Synchronization

**Date:** 2026-08-12  
**Audit Level:** Comprehensive  
**Risk Assessment:** MEDIUM-HIGH (Multiple critical gaps identified)  
**Status:** 🔴 NOT PRODUCTION-READY

---

## EXECUTIVE SUMMARY

The license-manager implements a **multi-server Master Data synchronization system** designed for bidirectional event propagation across 3+ independent servers. The architecture uses:

- **Deterministic UIDs** (UUIDv5 based on natural keys) for record identity
- **Version vectors** (master_version integer) for conflict detection
- **Durable outbox/inbox pattern** for eventual consistency
- **Exponential backoff retries** with 7-attempt limit
- **Soft deletion with tombstones** for delete recovery
- **HMAC-signed events** for server authentication

**Critical Finding:** While the foundation is well-designed, **five major risks** prevent production deployment:

1. **Idempotency violation** on concurrent updates → data loss risk
2. **Event ordering not enforced** → logical causality breaks
3. **Duplicate delivery NOT idempotent** → duplicate records created
4. **No transaction boundaries** across event application → partial failures
5. **Convergence not guaranteed** if networks partition → permanent divergence

---

## 1. IDEMPOTENCY ANALYSIS

**Question:** Can the same event be applied twice safely?

### ✅ STRENGTHS

- **Inbox deduplication by event_uid:** `MasterSyncInbox` uses `event_uid` as unique constraint
  - **File:** `backend/apps/core/models.py:984` — `event_uuid = models.UUIDField(unique=True)`
  - Same event_uid blocks duplicate inbox creation → prevents re-processing

- **Soft-delete semantics:** DELETE operations set `deleted=True` idempotently
  - Running DELETE twice produces same state
  - **File:** `backend/apps/core/tasks.py:180-184`

### 🔴 CRITICAL GAPS

#### Gap 1: CREATE/UPDATE via `update_or_create()` is NOT idempotent

**Current implementation (tasks.py:173-178):**
```python
if event.operation == 'CREATE':
    model.objects.update_or_create(
        master_uid=event.master_uid,
        defaults=event.payload,
    )
elif event.operation == 'UPDATE':
    model.objects.filter(master_uid=event.master_uid).update(**event.payload)
```

**Problem:** `update_or_create()` is **not safe for concurrent executions** on the same event:

- **Race condition:** Between the SELECT (checking existence) and INSERT/UPDATE, another server's event may arrive
- **Schema mismatch:** If payload contains fields not in the model, `.update(**event.payload)` silently fails
- **Partial updates:** If 10 fields are in payload but 3 fail validation, the event is marked APPLIED with incomplete data

**Scenario:**
1. Server A receives CREATE event for Company with `iec='C001'`, version=1
2. Server B receives SAME CREATE event (network race), also version=1
3. Both servers call `update_or_create(master_uid=uuid, defaults={...})`
4. If both SELECT at the same instant, both INSERT → PostgreSQL catches duplicate with error
5. Event marked FAILED (not APPLIED), but no retry recovery → **event lost, server diverges**

#### Gap 2: No version checking on event application

**Expected behavior:** Only apply if event version > local version  
**Actual behavior (tasks.py:167-189):** Events applied unconditionally, version check happens AFTER

```python
# Application happens here (no version guard)
model.objects.filter(master_uid=event.master_uid).update(**event.payload)

# Version check (if any) should happen before
```

**Impact:** 
- Stale events (version < local) overwrite newer local changes
- No optimistic locking → last-write-wins (LWW) without coordination
- Violates ACID: local transaction that incremented version gets overwritten by remote version-1 event

**Example of data loss:**
1. Server A: Company iec='C001' created with version=1
2. Server A local update: iec changed to 'C001_MODIFIED', version=2
3. Network delay: Server A's version=1 event arrives late from Server B's inbox
4. Server B applies version=1 event → overwrites local version=2 → **data loss**

---

## 2. EVENT ORDERING ANALYSIS

**Question:** Are events processed in causal order?

### ❌ NO ORDERING GUARANTEE

**Outbox order:** Events ordered by `created_at`
- **File:** `backend/apps/core/views/master_sync.py:183` — `query.order_by('created_at')`
- **File:** `backend/apps/core/tasks.py:64` — `pending_events.order_by('created_at')`

**Problem 1: Millisecond collisions**
- Two rapid updates (e.g., 2 milliseconds apart) may have **same created_at timestamp**
- Order becomes non-deterministic based on database query order
- **Risk:** If Server B receives updates in reverse order, causality breaks

**Problem 2: No causal ordering enforcement**
- Example: 
  - Company C001 created (v1)
  - Company C001 HS codes added (depends on v1)
  - If HS code event arrives before Company event, it fails silently
  - No retry of dependent events
  - **Inbox status:** REJECTED (event lost forever)

**Problem 3: Concurrent events with same timestamp**

**Scenario:**
1. 15:30:42.500 — Server A: UPDATE Company name='A'
2. 15:30:42.500 — Server B: UPDATE Company name='B' (concurrent)
3. Both create outbox entries with `created_at = 15:30:42.500`
4. Pull order becomes non-deterministic (database ORDER BY on tied timestamps)
5. Server C may apply A then B, while Server D applies B then A
6. **Permanent divergence:** Data is different on each server forever

### Version Ordering

**MasterVersionService enforces version-based ordering:**
- **File:** `backend/apps/core/services/master_version_service.py:50-62`
- Newer version (higher number) always wins
- Same-version tie broken by server_id alphabetically

**However:** This is applied DURING conflict resolution, NOT during event processing.

**Current flow:**
1. Event arrives with version=N
2. Event applied immediately (no pre-check)
3. IF conflict detected LATER, version decides winner
4. **But:** Earlier application already happened → state contamination

---

## 3. RETRY LOGIC ANALYSIS

**Question:** What happens on network failure?

### ✅ STRENGTHS

- **Exponential backoff implemented:**
  - **File:** `backend/apps/core/services/master_sync_retry.py:16` — `RETRY_SCHEDULE = [1, 2, 4, 8, 16, 32, 60]`
  - Max 7 attempts, final delay 60 seconds
  - Prevents thundering herd on network recovery

- **Per-server delivery tracking:**
  - **File:** `backend/apps/core/models.py:948` — `delivered_to_servers` JSONField
  - Tracks which servers ACK'd, allows partial delivery success

- **Event durability:** Outbox entries never deleted
  - **File:** `backend/apps/core/services/master_sync_retry.py:35-65`
  - `# Max attempts exceeded, stop retrying (but never delete event)`
  - Even after 7 failures, event remains in database for auditing

### 🟡 GAPS & CONCERNS

#### Gap 3: Retry doesn't check if event is still valid

When retrying after network recovery:
- Same event re-sent unchanged
- **Problem:** Event version may now be stale (other servers already updated record)
- **Expected:** Retry should include latest version, or retry should be rejected as stale
- **Current:** Event applied regardless of staleness → overwrites newer remote updates

#### Gap 4: Transient vs permanent failures not distinguished

**Current code (tasks.py:117-129):**
```python
except Exception as e:
    logger.error(f"Failed to deliver {event.event_uid}...")
    failed_count += 1
    event.attempts += 1  # Same increment for ALL exceptions
    event.status = MasterSyncOutbox.STATUS_FAILED
```

**Problem:**
- Network timeout (transient) → retry ✅
- Invalid payload schema (permanent) → **also retry**, wastes resources
- Remote server authentication failure (permanent) → **also retry**
- HTTP 5xx (transient) → retry ✅

**Expected:** Distinguish 5xx (retry) from 4xx (manual intervention)

---

## 4. DUPLICATE DELIVERY ANALYSIS

**Question:** How do we handle duplicate events?

### ⚠️ PARTIAL PROTECTION

#### Outbox side (Server sending):
- No deduplication of outbox entries
- If signal fires twice, both create separate outbox entries
- **Risk:** Hardware hiccup causes signal to fire twice → two identical events
- Both events get separate event_uids → both propagate

#### Inbox side (Server receiving):
- **✅ Protected by unique constraint on event_uuid**
  - **File:** `backend/apps/core/models.py:984` — `event_uuid = models.UUIDField(unique=True)`
  - Duplicate events rejected at DB level
  - Response: `status: 'duplicate'` (202 HTTP)
  - **File:** `backend/apps/core/views/master_sync.py:130`

### 🔴 CRITICAL: Duplicate inbox entries do NOT block application

**Scenario:**
1. Event E1 arrives, status=PENDING
2. periodic_sync_inbox processes E1, marks APPLIED
3. Network hiccup: Same E1 re-sent 3 seconds later
4. Inbox query returns duplicate NOT created (unique constraint) ✅
5. **But existing inbox entry already has status=APPLIED**
6. **If periodic_sync_inbox re-runs:** It filters for `status=PENDING`, skips E1 ✅

**But then:**
7. **If inbox.applied_at gets cleared** (manual operations, schema migrations, bugs), same inbox entry becomes PENDING again
8. periodic_sync_inbox processes it AGAIN
9. `update_or_create(master_uid=E1.master_uid, defaults={...})` applies E1 second time
10. **Idempotency broken** (as per Gap 1 analysis)

**Conclusion:** Duplicate delivery is protected at **inbox creation** level, but not at **application** level. If an inbox entry is re-opened (via bug or admin action), same event applies twice.

---

## 5. OUT-OF-ORDER DELIVERY ANALYSIS

**Question:** What if event C arrives before B?

### ❌ NO OUT-OF-ORDER PROTECTION

#### Scenario: Dependency chain
```
v1: Company 'C001' created
v2: Company 'C001' name changed to 'C001_MODIFIED'
v3: Company 'C001' deleted
```

**Network delivers them out-of-order:**
1. Server B receives v3 (DELETE) first → soft-deletes company
2. Server B receives v1 (CREATE) → creates company with `deleted=False`
3. Server B receives v2 (UPDATE) → updates name
4. **Final state:** deleted=False with modified name
5. **Server A final state:** deleted=True
6. **Permanent divergence**

#### Current ordering mechanism:
- Events ordered by `created_at` during **fetch** (not guaranteed globally)
- No sequence number, no logical clock
- Version numbers increment but don't enforce ordering across different records

#### Expected solution:
- **Lamport clock or vector clocks** to enforce causal ordering
- **Sequence numbers** to detect gaps
- **Dependency tracking:** Event C cannot apply until B is APPLIED

#### Current system:
- No dependency tracking
- Events processed immediately upon arrival
- No "waiting for prerequisite" mechanism

#### Risk example:
1. Import 1000 Companies from Server A to Server B
2. Network packet reordering causes Company 500 to arrive before Company 1
3. If application processes in received order, later logic may assume Company 1 exists
4. Script that depends on Company 1 fails on Company 500 → application error
5. Event marked FAILED but never retried in correct order

---

## 6. OFFLINE RECOVERY ANALYSIS

**Question:** How does a server catch up after being offline?

### ✅ CURSOR-BASED RECOVERY IMPLEMENTED

**Mechanism (master_sync_retry.py:118-162):**
- Each server maintains a cursor: `last_applied_event_uid`, `last_applied_at`
- **File:** `backend/apps/core/models.py:1138-1160`
- On reconnect: Query inbox events `after=(last_applied_event_uid)`
- Re-applies missed events in order

**Strengths:**
- Cursor persisted in database → survives restarts
- Pull-based recovery (Server B asks Server A "what happened since X?")
- Exponential backoff prevents thundering herd

### 🟡 CRITICAL GAPS

#### Gap 5: Cursor is per-remote-server, not per-model

**Current code (master_sync_retry.py:144-145):**
```python
cursor, _ = MasterSyncCursor.objects.get_or_create(
    server_id=remote_server_id,  # Single cursor for ALL models
```

**Problem:**
- If Server A goes offline for 2 hours
- Then reconnects, cursor is `last_applied_event_uid = "E12345"`
- Queries all events AFTER E12345 across ALL models
- **But:** If E12345 was a Company event, and Server B created 5000 new HS codes in the interim
- HS codes are now after the Company event in query results
- If a new HS code depends on old company metadata (that was also updated), dependency order breaks

#### Gap 6: No validation of event sequence after recovery

**Expected behavior:** After applying caught-up events, verify all versions are monotonic
- **File:** `backend/apps/core/services/master_version_service.py:131-151` — `validate_version_sequence()` exists
- **Problem:** Never called during or after offline recovery

**Risk:** If events arrive out-of-order during recovery, versions may jump (v1, v5, v2, v3)
- Code doesn't detect this anomaly
- Later conflict resolution uses version to decide, but sequence was invalid
- Decision made on corrupted information

#### Gap 7: Cursor advancement is not atomic

**Code (master_sync_retry.py:165-189):**
```python
# Apply event
model.objects.filter(master_uid=event.master_uid).update(**event.payload)

# Mark as applied
event.status = MasterSyncInbox.STATUS_APPLIED
event.applied_at = timezone.now()
event.save(update_fields=['status', 'applied_at'])

# Advance cursor (SEPARATE transaction)
OfflineRecoveryHandler.advance_cursor(...)
```

**Problem:**
1. Event applied to Master (transaction A)
2. Inbox marked APPLIED (transaction A)
3. Database crashes before cursor advance (transaction B)
4. Server restarts
5. Cursor still points to previous event
6. Same event is re-applied when periodic_sync_inbox runs again
7. **Idempotency violated** (as per Gap 1)

**Expected:** Use database advisory locks or explicit transaction to ensure atomicity

---

## 7. CONFLICT RESOLUTION ANALYSIS

**Question:** What if servers update the same record differently?

### ✅ VERSION-BASED RESOLUTION EXISTS

**Mechanism (master_version_service.py:94-128):**
```python
def determine_winner(
    remote_version: int,
    local_version: Optional[int],
    remote_origin_server: str,
    local_origin_server: str
) -> str:
    if remote_version > local_version:
        return "REMOTE"
    elif remote_version < local_version:
        return "LOCAL"
    else:
        # Concurrent: use server_id tiebreaker (alphabetically earlier wins)
```

**Strengths:**
- Deterministic tiebreaker (all servers agree on same winner)
- Server IDs sorted alphabetically → no randomness
- Version increases monotonically → prevents ping-pong

### 🔴 CRITICAL: Conflict resolution never called during sync

**Where conflict resolution SHOULD happen:**
- **File:** `backend/apps/core/tasks.py:167-189` — `periodic_sync_inbox()`

**Actual code:**
```python
# No version check, no conflict detection
model.objects.filter(master_uid=event.master_uid).update(**event.payload)

# Just applies unconditionally
event.status = MasterSyncInbox.STATUS_APPLIED
```

**Expected flow:**
1. Fetch local record version
2. Compare remote_version vs local_version
3. If conflict, call determine_winner()
4. Only apply if remote wins
5. Log conflict to MasterConflict table

**Actual flow:**
1. Update record immediately
2. Hope it works
3. If fails, mark FAILED
4. Never explicitly resolve

**Impact:**
- Conflicts detected but not resolved
- Stale events may overwrite newer local changes
- MasterConflict table never populated
- Operators have no visibility into what happened

#### Gap 8: No conflict resolution for duplicate UIDs

**Scenario: Duplicate Company with same IEC**
1. Server A: Creates Company(iec='C001', master_uid=uuid-a, version=1)
2. Server B (offline at creation): Later creates Company(iec='C001', master_uid=uuid-b, version=1)
3. Both compute same natural key ('C001') but got different UUIDs somehow
4. Network recovers: Both events propagate
5. Server C now has TWO companies with `iec='C001'` but different `master_uid`
6. **Expected:** Reconciliation service detects and merges
7. **Actual:** `find_duplicates_by_natural_key()` finds them, but `merge_duplicate_records()` is **never automatically called**

**File:** `backend/apps/core/management/commands/master_sync_reconcile.py:44-91`
- Reconciliation is a **manual operation** (`--execute` flag required)
- No automatic triggers
- If operator forgets to run it, duplicates persist forever
- Downstream systems see duplicate records → business logic breaks

---

## 8. CONVERGENCE ANALYSIS

**Question:** Will A/B/C eventually have identical Masters?

### ⚠️ EVENTUAL CONSISTENCY IS NOT GUARANTEED

#### Case 1: Happy path (all servers online)
- ✅ Events propagate within seconds
- ✅ Exponential backoff ensures retries
- ✅ All servers converge to same state

#### Case 2: Transient network partition (1 server isolated)
```
[Server A] ←→ [Server B]
              ↔
          [Server C - ISOLATED]
```

- A and B exchange updates freely
- C is offline, can't receive or send
- When C reconnects:
  - ✅ Cursor recovery fetches missed events
  - ✅ C applies them to converge with A and B
- **Result:** Convergence in 30-60 seconds (after backoff)

#### Case 3: Permanent network partition (Byzantine)
```
[Server A] ←→ [Server B]
           
    [Server C] (isolated, will never reconnect)
```

- C is permanently unreachable
- A and B continue updating
- C's last known state = frozen in time at partition
- A and B diverge from C forever
- **BUT:** If C reconnects later:
  - ✅ Cursor recovery catches up on missed events
  - ✅ C converges to A/B state
- **Assumption:** Networks eventually heal

#### Case 4: Multiple edits to same record during partition

```
Server A (online):
  v1: Company name = 'A'
  v2: Company name = 'A_UPDATED'
  
Server B (online, can sync with A):
  v1: Company name = 'A'
  v2: Company name = 'A_UPDATED'
  
Server C (partitioned, unaware of v2):
  v1: Company name = 'A'
  [no v2, diverges]
  
[Later in C's partition]
  v2: Company name = 'C_LOCAL_EDIT' (different from A/B's v2!)
  [C thinks version is 2]
```

- When partition heals:
- C tries to send v2 (name='C_LOCAL_EDIT') to A/B
- But A/B already have v2 (name='A_UPDATED')
- A/B reject C's v2 because version is equal (tie) → server_id tiebreaker
- **If SERVER_A < SERVER_C alphabetically:** A wins, C's change lost forever
- **If SERVER_C < SERVER_A alphabetically:** C wins, overwrites A/B (creates new v3 on A/B, but C sees only v2)

**Result:** Temporary divergence during partition, BUT:
- No automatic resolution of v2 conflict
- No user-facing notification
- Data loss may have occurred (C's edit deleted)
- Operators unaware unless they run reconciliation command

#### Case 5: Clock skew (timestamps unreliable)

- Some servers have incorrect time
- `created_at` timestamps used for ordering
- Event from past (wrong clock) may be ordered before recent event
- Ordering becomes non-deterministic

---

## 9. ALL-DIRECTIONS SYNC ANALYSIS

**Question:** Can A↔B, A↔C, B↔C all sync simultaneously?

### ✅ ARCHITECTURE SUPPORTS MULTI-DIRECTIONAL SYNC

**Design (from MasterSyncServer):**
- **File:** `backend/apps/core/models.py:822-864`
- Each server registered with `api_url` and `secret_token`
- Outbox task queries all active servers, sends to each
- Inbox task receives from any server

**Example with 3 servers:**

```
Server A creates Company:
  → Outbox: (model=Company, op=CREATE, version=1)
  
periodic_sync_outbox fires:
  → POST to Server B: /api/master-sync/events/
  → POST to Server C: /api/master-sync/events/
  
Server B receives:
  → MasterSyncInbox entry created
  → periodic_sync_inbox applies it
  → Outbox entry created (derived from incoming event? NO - not created)
  
Server C receives:
  → Similar to Server B
```

**Strengths:**
- ✅ All servers can send to all others
- ✅ Delivery tracking per-server
- ✅ No central hub required

### 🔴 CRITICAL: Derived events not propagated

**Scenario:**
1. Server A creates Company (version=1)
2. Server A creates HS Code referencing Company (version=1)
3. Outbox has TWO entries (both pending)
4. Server A → Server B: sends Company event
5. Server B → Server A: sends ACK
6. Server A marks Company event as ACKNOWLEDGED (sent to B)
7. Server A → Server C: sends Company event
8. Server C receives, applies, but...
9. **HS Code event never reaches Server B/C directly from A**
10. Server C needs to somehow know about the HS Code

**Expected flow:** HS Code event should propagate A→B, A→C independently

**Actual flow:** HS Code IS in outbox, will eventually propagate BUT:
- Ordering not guaranteed (HS Code might arrive BEFORE Company on Server C)
- No dependency enforcement
- If HS Code arrives first on Server C, application fails
- Event marked REJECTED (lost forever, no retry)

#### Gap 9: No transaction log replication

**Expected in production multi-directional sync:**
- Each server is a node
- Transactions should be idempotent log entries
- New nodes can catch up from log
- Log serves as source of truth

**Current system:**
- Each server has its own outbox (local TX log)
- Other servers' outboxes unknown
- If Server B creates event E but crashes before sending
- Servers A/C never learn about E
- E is lost forever

**Example:**
1. Server B creates 100 companies (outbox has 100 pending entries)
2. Server B crashes before periodic_sync_outbox runs
3. Server B database backup restores, but outbox entries gone
4. 100 companies created on B, but A and C never see them
5. B still has companies, A/C don't
6. **Permanent divergence**

---

## SUMMARY: CRITICAL RISKS BY SEVERITY

| Risk | Severity | Impact | Likelihood | Mitigation |
|------|----------|--------|------------|-----------|
| Idempotency violation on concurrent CREATE | **CRITICAL** | Data loss, duplicate records | **HIGH** | Add version check + optimistic lock before apply |
| Out-of-order event delivery | **CRITICAL** | Data corruption, broken dependencies | **MEDIUM** | Implement Lamport clock or event sequencing |
| Conflict resolution never called | **CRITICAL** | Stale overwrites newer data | **HIGH** | Pre-apply version check, use determine_winner() |
| Duplicate record creation (duplicate UIDs) | **CRITICAL** | Data integrity violations, FK failures | **MEDIUM** | Auto-run reconciliation, prevent duplicates at source |
| Cursor not atomic with event application | **HIGH** | Event re-application, idempotency loss | **MEDIUM** | Use DB transaction or advisory locks |
| Permanent partition → divergence | **HIGH** | Eventual data inconsistency | **LOW** (assumes partition heals) | Add vector clocks, monitor partition detection |
| Retry on permanent failures | **MEDIUM** | Resource waste, eventual max-retry cutoff | **MEDIUM** | Distinguish 4xx vs 5xx, manual intervention queue |
| Offline recovery sequence gaps | **MEDIUM** | Silent data corruption | **LOW** | Validate version sequence after recovery |

---

## RECOMMENDATIONS FOR PRODUCTION READINESS

### Phase 1: Immediate (Blocking Issues)

1. **Add pre-apply version check (tasks.py)**
   ```python
   # Before update_or_create:
   local_record = model.objects.filter(master_uid=event.master_uid).first()
   if local_record and local_record.master_version > event.version:
       # Reject stale event
       event.status = REJECTED
       event.save()
       continue
   
   # Proceed only if remote_version >= local_version
   ```

2. **Implement idempotent event application**
   - Use `update_or_create()` with version conflict check
   - Or: Implement explicit SELECT FOR UPDATE (PostgreSQL)

3. **Auto-run duplicate reconciliation**
   - Create management command: `python manage.py periodic_reconciliation --execute`
   - Schedule via cron or Celery every 5 minutes
   - Alert on duplicates found

4. **Add conflict detection and logging**
   - Before applying event, fetch local record
   - Compare versions, call `determine_winner()`
   - Log to MasterConflict table for visibility

### Phase 2: Short-term (Architecture Improvements)

5. **Implement ordering mechanism**
   - Add Lamport clock or vector clock
   - Or: Per-record sequence numbers
   - Enforce ordering during event processing

6. **Add transactional boundaries**
   - Wrap event application + cursor advance in single transaction
   - Use DB-level constraints to prevent partial failures

7. **Distinguish transient vs permanent failures**
   - HTTP 5xx → retry with backoff
   - HTTP 4xx → manual intervention queue
   - Timeouts → retry with exponential backoff

### Phase 3: Long-term (Resilience)

8. **Implement Byzantine fault tolerance**
   - Vector clocks for causality tracking
   - Quorum-based conflict resolution (not just version)
   - Formal verification of convergence

9. **Add network partition detection**
   - Monitor sync health (outbox queue size, inbox lag)
   - Alert when servers not converging
   - Potential split-brain prevention

10. **Implement write-ahead logging (WAL)**
    - Replication log as durable event store
    - Not just per-server outbox
    - Enable point-in-time recovery

---

## TESTING RECOMMENDATIONS

### Unit Tests (Add)
- [ ] Idempotency: Same event applied 2x produces identical state
- [ ] Version check: Stale events rejected (not applied)
- [ ] Conflict resolution: determine_winner() outputs deterministic result
- [ ] Duplicate handling: Duplicate inbox entry doesn't re-apply

### Integration Tests (Add)
- [ ] 2-server sync: Create on A, verify on B within 30s
- [ ] 3-server sync: Create on A, verify on B and C
- [ ] Out-of-order delivery: Delay event, verify correct final state
- [ ] Offline recovery: Stop server, create events, restart, verify catch-up
- [ ] Network partition: Isolate server, create conflicting events, partition heals, verify resolution

### Chaos Tests (Add)
- [ ] Network packet loss (30%)
- [ ] Event reordering (random shuffle)
- [ ] Duplicate events (repeat random events)
- [ ] Server crash mid-transaction
- [ ] Clock skew (±5 seconds per server)

---

## MONITORING CHECKLIST

Add alerts for:
- [ ] Outbox queue size > 100 (events not delivering)
- [ ] Inbox PENDING events > 50 (events not applying)
- [ ] Sync lag > 5 minutes (Server C behind A/B)
- [ ] Duplicate detected (master with same natural_key, different UIDs)
- [ ] Version skew > threshold (v=5 on A, v=3 on B)
- [ ] Conflict resolution decisions (log and alert when tiebreaker used)

---

## CONCLUSION

The multi-server sync system has **good foundational design** (deterministic UIDs, version vectors, durable outbox) but **lacks critical safeguards** for production deployment:

1. **Data loss risk:** Idempotency not enforced → concurrent updates overwrite
2. **Consistency risk:** Ordering not enforced → events processed out-of-order
3. **Silent failures:** Conflicts detected but not resolved
4. **Duplicate risk:** No automatic deduplication of Master records

**Recommendation:** **DO NOT DEPLOY** to production with 3+ servers until Phase 1 and Phase 2 items are completed. Current implementation suitable for:
- ✅ Single-server deployments (no sync needed)
- ✅ Backup/restore scenarios (offline mode)
- ⚠️ 2-server replication (with manual monitoring)
- ❌ Multi-server distributed systems (HIGH RISK)

**Estimated effort to production-ready:** 4-6 weeks for Phase 1+2 + comprehensive testing.
